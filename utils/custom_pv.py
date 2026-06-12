import logging
import time
from threading import Lock
from typing import Any, Callable, Optional, Type

from epics import PV
from qtpy import QtCore


_NOTHING = object()
logger = logging.getLogger()


class SignalQtBridge(QtCore.QObject):
    """
    Bridges an EPICS PV or ophyd Signal callback to a Qt slot.

    Eliminates the repetitive boilerplate of declaring a unique Signal subclass
    attribute, writing a one-liner ``pv.add_callback`` wrapper that emits it,
    and then connecting the signal to the real slot in ``initCallbacks``.

    A single ``Signal(object)`` is used for the thread hop; the *slot* receives
    whatever the *transform* returns (or *value* / *char_value* by default).

    Parameters
    ----------
    signal_or_name : object | str
        Existing EPICS PV object, ophyd Signal-like object, or a PV name
        string (creates an EPICS PV with ``auto_monitor=True``).
    slot : callable
        Qt slot or any callable invoked on the main thread when the PV
        changes.  It receives exactly one argument – the emitted value.
        For no-arg or multi-arg slots wrap with a lambda, e.g.
        ``lambda _: my_slot()`` or ``lambda t: my_slot(*t)``.
    use_char : bool, default False
        Emit ``char_value`` (EPICS string representation) instead of the raw
        ``value``.  Ignored when *transform* is provided.
    transform : callable, optional
        ``transform(value, char_value, **kw) -> Any`` called inside the EPICS
        callback thread.  Its return value is emitted.  Overrides *use_char*.
    predicate : callable, optional
        ``predicate(value, char_value, **kw) -> bool`` evaluated before
        emitting.  The signal is suppressed when this returns ``False``.
    custom_pv_class : type[PV], optional
        PV subclass to instantiate when *signal_or_name* is a string.
    label : str, default ""
        Optional label used in periodic rate logs. When empty, no per-bridge
        rate logging is performed.
    rate_log_interval_s : float, default 5.0
        Logging interval for incoming/outgoing callback rates when *label* is
        provided.
    coalesce_interval_ms : int, default 200
        Callback coalescing period in milliseconds. At each period the latest
        value (if any) is emitted to the slot.
    **callback_kwargs
        Extra keyword arguments forwarded verbatim to ``pv.add_callback()``.
        They are accessible inside *transform* / *predicate* via ``**kw``.

    Examples
    --------
    Simple scalar (float):

    >>> bridge = SignalQtBridge(
    ...     "MY:ENERGY:RBV", self.processEnergyChange,
    ...     transform=lambda v, cv, **kw: float(v),
    ... )

    String PV:

    >>> bridge = SignalQtBridge(
    ...     my_existing_pv, self.printServerMessage, use_char=True
    ... )

    Conditional emission:

    >>> bridge = SignalQtBridge(
    ...     flag_pv, self.handleResult,
    ...     use_char=True,
    ...     predicate=lambda v, cv, **kw: cv != "0",
    ... )

    Multi-argument slot (emit a tuple, unpack in lambda):

    >>> bridge = SignalQtBridge(
    ...     samp_pv,
    ...     lambda t: self.processSampMove(*t),
    ...     transform=lambda v, cv, _mid="x", **kw: (int(v), _mid),
    ... )
    """

    signal = QtCore.Signal(object)

    def __init__(
        self,
        signal_or_name,
        slot: Callable,
        *,
        use_char: bool = False,
        transform: Optional[Callable] = None,
        predicate: Optional[Callable] = None,
        custom_pv_class: Optional[Type[PV]] = None,
        label: str = "",
        rate_log_interval_s: float = 5.0,
        coalesce_interval_ms: int = 200,
        **callback_kwargs,
    ):
        super().__init__()
        self.use_char = use_char
        self.transform = transform
        self.predicate = predicate
        self._subscription_token: Any = None
        self._epics_callback_index: Any = None
        self._rate_label = label
        self._rate_logging_enabled = bool(label)
        self._rate_log_interval_s = rate_log_interval_s
        self._rate_window_start = time.monotonic()
        self._incoming_count = 0
        self._outgoing_count = 0
        self._rate_lock = Lock()

        self.signal.connect(slot)

        if isinstance(signal_or_name, str):
            pv_class = custom_pv_class if custom_pv_class is not None else PV
            if not issubclass(pv_class, PV):
                raise TypeError("custom_pv_class must be PV or a subclass of PV")
            self.source = pv_class(signal_or_name, auto_monitor=True)
        else:
            self.source = signal_or_name

        if hasattr(self.source, "add_callback"):
            self._epics_callback_index = self.source.add_callback(
                self._on_epics_changed,
                **callback_kwargs,
            )
        elif hasattr(self.source, "subscribe"):
            event_type = callback_kwargs.pop("event_type", "value")
            run = callback_kwargs.pop("run", False)
            if callback_kwargs:
                unknown = ", ".join(sorted(callback_kwargs))
                raise TypeError(f"Unsupported ophyd subscribe kwargs: {unknown}")
            self._subscription_token = self.source.subscribe(
                self._on_ophyd_changed,
                event_type=event_type,
                run=run,
            )
        else:
            raise TypeError(
                "signal_or_name must be EPICS PV name, EPICS PV object, or ophyd Signal-like object"
            )

        self._pending_value: Any = _NOTHING
        self._coalesce_timer = QtCore.QTimer(self)
        self._coalesce_timer.setInterval(coalesce_interval_ms)
        self._coalesce_timer.timeout.connect(self._flush_coalesced)
        self._coalesce_timer.start()

    # ------------------------------------------------------------------
    # EPICS callback (runs in a CA background thread)
    # ------------------------------------------------------------------

    def _emit_if_allowed(self, value=None, char_value=None, **kw):
        if self.predicate is not None and not self.predicate(value, char_value, **kw):
            return

        if self.transform is not None:
            result = self.transform(value, char_value, **kw)
        elif self.use_char:
            result = char_value
        else:
            result = value

        if self._rate_logging_enabled:
            with self._rate_lock:
                self._incoming_count += 1

        self._pending_value = result

    def _flush_coalesced(self):
        """Main-thread QTimer slot. Emits latest pending value if one exists."""
        if self._pending_value is not _NOTHING:
            val = self._pending_value
            self._pending_value = _NOTHING
            if self._rate_logging_enabled:
                with self._rate_lock:
                    self._outgoing_count += 1
            # Signal.emit() is thread-safe in Qt; this queued cross-thread call
            # delivers the value to the slot on the main GUI thread.
            self.signal.emit(val)

        if self._rate_logging_enabled:
            now = time.monotonic()
            elapsed = now - self._rate_window_start
            if elapsed >= self._rate_log_interval_s:
                with self._rate_lock:
                    incoming_count = self._incoming_count
                    outgoing_count = self._outgoing_count
                    self._incoming_count = 0
                    self._outgoing_count = 0
                self._rate_window_start = now

                incoming_hz = incoming_count / elapsed if elapsed > 0 else 0.0
                outgoing_hz = outgoing_count / elapsed if elapsed > 0 else 0.0
                reduction_pct = 0.0
                if incoming_count > 0:
                    reduction_pct = 100.0 * (1.0 - (outgoing_count / incoming_count))

                logger.info(
                    "BRIDGE_RATE label=%s incoming_hz=%.2f outgoing_hz=%.2f "
                    "reduction_pct=%.1f incoming_count=%d outgoing_count=%d window_s=%.2f",
                    self._rate_label,
                    incoming_hz,
                    outgoing_hz,
                    reduction_pct,
                    incoming_count,
                    outgoing_count,
                    elapsed,
                )

    def _on_epics_changed(self, value=None, char_value=None, **kw):
        self._emit_if_allowed(value=value, char_value=char_value, **kw)

    def _on_ophyd_changed(self, value=None, old_value=None, obj=None, **kw):
        self._emit_if_allowed(value=value, char_value=str(value), old_value=old_value, obj=obj, **kw)

    # ------------------------------------------------------------------
    # Convenience pass-throughs so callers can still do bridge.get() /
    # bridge.put() without reaching into bridge.pv directly.
    # ------------------------------------------------------------------

    def get(self, *args, **kwargs):
        return self.source.get(*args, **kwargs)

    def put(self, *args, **kwargs):
        self.source.put(*args, **kwargs)

    def close(self):
        if self._coalesce_timer.isActive():
            self._coalesce_timer.stop()
        if self._subscription_token is not None and hasattr(self.source, "unsubscribe"):
            self.source.unsubscribe(self._subscription_token)
            self._subscription_token = None
        if self._epics_callback_index is not None and hasattr(self.source, "remove_callback"):
            self.source.remove_callback(self._epics_callback_index)
            self._epics_callback_index = None
