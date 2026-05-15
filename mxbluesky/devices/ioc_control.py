"""IOCControl device — IOC reboot commands for Eiger and Zebra.

The IOC names differ between beamlines so they are injected at instantiation.

Note on FormattedComponent (FCpt):
  FCpt produces the FULL PV string — the device prefix is NOT auto-prepended.
  Full PV strings are therefore pre-computed in ``__init__``.

Instantiation::

    ioc = IOCControl(
        "XF:17IDC-CT:FMX",
        eiger_ioc_suffix="{IOC:DET01}:SysReset",
        zebra_ioc_suffix="{IOC:Zeb3}:SysReset",
        name="ioc_control",
    )  # FMX

    ioc = IOCControl(
        "XF:17IDB-CT:AMX",
        eiger_ioc_suffix="{IOC:DET02}:SysReset.VAL",
        zebra_ioc_suffix="{IOC:Zeb2}:SysReset",
        name="ioc_control",
    )  # AMX
"""

from ophyd import FormattedComponent as FCpt, Device, EpicsSignal


class IOCControl(Device):
    """IOC soft-reboot commands."""

    eiger_ioc_reboot = FCpt(EpicsSignal, "{self._eiger_ioc_pv}")   # eigerIOC_reboot
    zebra_ioc_reboot = FCpt(EpicsSignal, "{self._zebra_ioc_pv}")   # zebraRebootIOC

    def __init__(self, prefix, *args, eiger_ioc_suffix, zebra_ioc_suffix, **kwargs):
        # Pre-compute full PV strings (FCpt does NOT auto-prepend device prefix).
        self._eiger_ioc_pv = f"{prefix}{eiger_ioc_suffix}"
        self._zebra_ioc_pv = f"{prefix}{zebra_ioc_suffix}"
        super().__init__(prefix, *args, **kwargs)
