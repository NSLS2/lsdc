from ophyd import Device, EpicsSignalRO, EpicsSignal, FormattedComponent as FCpt
from ophyd.status import SubscriptionStatus


class PYZHomer(Device):
    """Pin Y/Z homer using the Sentinel IOC.

    All five signals span two PV roots, so fully-qualified PV strings are
    injected at instantiation (prefix="").  Use the factory::

        pyz_homer = PYZHomer.from_beamline("fmx", name="pyz_homer")
        pyz_homer = PYZHomer.from_beamline("amx", name="pyz_homer")

    The ``__init__`` kwarg PVs must be set before ``super().__init__`` because
    ophyd instantiates non-lazy components inside Device.__init__.
    """

    status       = FCpt(EpicsSignalRO, "{self._status_pv}")
    home_actuate = FCpt(EpicsSignal,   "{self._home_actuate_pv}")
    kill_home    = FCpt(EpicsSignal,   "{self._kill_home_pv}")
    kill_py      = FCpt(EpicsSignal,   "{self._kill_py_pv}")
    kill_pz      = FCpt(EpicsSignal,   "{self._kill_pz_pv}")

    def __init__(self, *args,
                 status_pv,
                 home_actuate_pv,
                 kill_home_pv,
                 kill_py_pv,
                 kill_pz_pv,
                 **kwargs):
        # Must be set before super().__init__ so FCpts can format themselves
        self._status_pv       = status_pv
        self._home_actuate_pv = home_actuate_pv
        self._kill_home_pv    = kill_home_pv
        self._kill_py_pv      = kill_py_pv
        self._kill_pz_pv      = kill_pz_pv
        super().__init__(*args, **kwargs)

    @classmethod
    def from_beamline(cls, beamline: str, name: str = "pyz_homer", **kwargs) -> "PYZHomer":
        """Construct a PYZHomer for the given beamline.

        Parameters
        ----------
        beamline : {"fmx", "amx"}
        name     : ophyd device name
        """
        bl = beamline.lower()
        if bl == "fmx":
            es = "XF:17IDC-ES:FMX"
            id_ = "XF:17ID:FMX"
        elif bl == "amx":
            es = "XF:17IDB-ES:AMX"
            id_ = "XF:17ID:AMX"
        else:
            raise ValueError(f"Unknown beamline {beamline!r}; expected 'fmx' or 'amx'.")

        return cls(
            "",
            name=name,
            status_pv       =f"{es}{{Sentinel}}Homing_Sts",
            home_actuate_pv =f"{id_}{{Sentinel}}pin_home",
            kill_home_pv    =f"{es}{{Sentinel}}Homing_Kill",
            kill_py_pv      =f"{es}{{Gon:1-Ax:PY}}Cmd:Kill-Cmd",
            kill_pz_pv      =f"{es}{{Gon:1-Ax:PZ}}Cmd:Kill-Cmd",
            **kwargs,
        )

    def trigger(self):

        def callback_homed(value, old_value, **kwargs):
            if old_value == 1 and value == 0:
                return True
            else:
                return False

        self.home_actuate.put(1)

        homing_status = SubscriptionStatus(
            self.status,
            callback_homed,
            run=False,
            timeout=180,
        )

        return homing_status
