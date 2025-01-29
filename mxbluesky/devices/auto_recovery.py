from ophyd import Device, EpicsSignalRO, EpicsSignal, Component as Cpt
from ophyd.status import SubscriptionStatus


class PYZHomer(Device):

    status = Cpt(EpicsSignalRO, "XF:17IDB-ES:AMX{Sentinel}Homing_Sts")
    home_actuate = Cpt(EpicsSignal, "XF:17ID:AMX{Sentinel}pin_home")

    kill_home = Cpt(EpicsSignal, "XF:17IDB-ES:AMX{Sentinel}Homing_Kill")
    kill_py = Cpt(EpicsSignal, "XF:17IDB-ES:AMX{Gon:1-Ax:PY}Cmd:Kill-Cmd")
    kill_pz = Cpt(EpicsSignal, "XF:17IDB-ES:AMX{Gon:1-Ax:PZ}Cmd:Kill-Cmd")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
