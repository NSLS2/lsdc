"""Diagnostics device — BPM current, pin-homer, and PI commands.

Signals span the BI and CT IOC families, so fully-qualified PV strings
are injected at instantiation (prefix="").

``pi_commands`` is FMX-only; pass an empty string on AMX and the
component will simply remain disconnected.

Instantiation::

    diag = Diagnostics(
        "",
        total_current_pv="XF:17IDC-BI:FMX{BPM:4}SumAll:MeanValue_RBV",
        home_pin_y_pv   ="XF:17IDC-CT:FMX{SDC:04-Ax:5}StartHome",
        home_pin_z_pv   ="XF:17IDC-CT:FMX{SDC:04-Ax:6}StartHome",
        pi_commands_pv  ="XF:17IDC-CT:FMX{MC:21}Asyn.AOUT",
        name="diagnostics",
    )  # FMX

    diag = Diagnostics(
        "",
        total_current_pv="XF:17IDB-BI:AMX{BPM:3}SumAll:MeanValue_RBV",
        home_pin_y_pv   ="XF:17IDB-CT:AMX{SDC:04-Ax:5}StartHome",
        home_pin_z_pv   ="XF:17IDB-CT:AMX{SDC:04-Ax:6}StartHome",
        name="diagnostics",
    )  # AMX
"""

from ophyd import FormattedComponent as FCpt, Device, EpicsSignal, EpicsSignalRO


class Diagnostics(Device):
    """BPM total current, pin-homer triggers, and PI command channel."""

    total_current_bcu = FCpt(EpicsSignalRO, "{self._total_current_pv}")   # totalCurrentBCU
    home_pin_y        = FCpt(EpicsSignal,   "{self._home_pin_y_pv}")      # homePinY
    home_pin_z        = FCpt(EpicsSignal,   "{self._home_pin_z_pv}")      # homePinZ
    pi_commands       = FCpt(EpicsSignal,   "{self._pi_commands_pv}",  lazy=True)  # PIcommands (FMX only)

    def __init__(self, *args,
                 total_current_pv,
                 home_pin_y_pv,
                 home_pin_z_pv,
                 pi_commands_pv="",
                 **kwargs):
        self._total_current_pv = total_current_pv
        self._home_pin_y_pv    = home_pin_y_pv
        self._home_pin_z_pv    = home_pin_z_pv
        self._pi_commands_pv   = pi_commands_pv
        super().__init__(*args, **kwargs)
