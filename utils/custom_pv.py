from typing import Callable, Optional, Type

from epics import PV
from qtpy.QtCore import QObject, Signal


class MountedPinPV(PV):

    def get(self, *args, **kwargs):
        value = str(super().get(*args, **kwargs))
        return value.split(",")[0]

    def get_pin_state(self):
        value = str(super().get()).split(",")
        if len(value) == 2:
            return value[1]
        return None


class EpicsQtBridge(QObject):
    """
    Bridges an EPICS PV change callback to a Qt slot via a thread-safe signal.

    Eliminates the repetitive boilerplate of declaring a unique Signal subclass
    attribute, writing a one-liner ``pv.add_callback`` wrapper that emits it,
    and then connecting the signal to the real slot in ``initCallbacks``.

    A single ``Signal(object)`` is used for the thread hop; the *slot* receives
    whatever the *transform* returns (or *value* / *char_value* by default).

    Parameters
    ----------
    pv_or_name : PV | str
        Existing PV instance (a callback is added to it) **or** a PV name
        string (a new PV is created internally with ``auto_monitor=True``).
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
        PV subclass to instantiate when *pv_or_name* is a string.
    **callback_kwargs
        Extra keyword arguments forwarded verbatim to ``pv.add_callback()``.
        They are accessible inside *transform* / *predicate* via ``**kw``.

    Examples
    --------
    Simple scalar (float):

    >>> bridge = EpicsQtBridge(
    ...     "MY:ENERGY:RBV", self.processEnergyChange,
    ...     transform=lambda v, cv, **kw: float(v),
    ... )

    String PV:

    >>> bridge = EpicsQtBridge(
    ...     my_existing_pv, self.printServerMessage, use_char=True
    ... )

    Conditional emission:

    >>> bridge = EpicsQtBridge(
    ...     flag_pv, self.handleResult,
    ...     use_char=True,
    ...     predicate=lambda v, cv, **kw: cv != "0",
    ... )

    Multi-argument slot (emit a tuple, unpack in lambda):

    >>> bridge = EpicsQtBridge(
    ...     samp_pv,
    ...     lambda t: self.processSampMove(*t),
    ...     transform=lambda v, cv, _mid="x", **kw: (int(v), _mid),
    ... )
    """

    signal = Signal(object)

    def __init__(
        self,
        pv_or_name,
        slot: Callable,
        *,
        use_char: bool = False,
        transform: Optional[Callable] = None,
        predicate: Optional[Callable] = None,
        custom_pv_class: Optional[Type[PV]] = None,
        **callback_kwargs,
    ):
        super().__init__()
        self.use_char = use_char
        self.transform = transform
        self.predicate = predicate

        self.signal.connect(slot)

        if isinstance(pv_or_name, str):
            pv_class = custom_pv_class if custom_pv_class is not None else PV
            if not issubclass(pv_class, PV):
                raise TypeError("custom_pv_class must be PV or a subclass of PV")
            self.pv = pv_class(pv_or_name, auto_monitor=True)
        else:
            self.pv = pv_or_name

        self.pv.add_callback(self._on_pv_changed, **callback_kwargs)

    # ------------------------------------------------------------------
    # EPICS callback (runs in a CA background thread)
    # ------------------------------------------------------------------

    def _on_pv_changed(self, value=None, char_value=None, **kw):
        if self.predicate is not None and not self.predicate(value, char_value, **kw):
            return

        if self.transform is not None:
            result = self.transform(value, char_value, **kw)
        elif self.use_char:
            result = char_value
        else:
            result = value

        # Signal.emit() is thread-safe in Qt; this queued cross-thread call
        # delivers the value to the slot on the main GUI thread.
        self.signal.emit(result)

    # ------------------------------------------------------------------
    # Convenience pass-throughs so callers can still do bridge.get() /
    # bridge.put() without reaching into bridge.pv directly.
    # ------------------------------------------------------------------

    def get(self, *args, **kwargs):
        return self.pv.get(*args, **kwargs)

    def put(self, *args, **kwargs):
        self.pv.put(*args, **kwargs)
