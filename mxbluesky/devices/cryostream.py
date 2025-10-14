from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO, PVPositionerIsClose
from mxbluesky.devices import standardize_readback
from enum import IntEnum, unique
from ophyd import Component as Cpt

@unique
class CryoStreamCmd(IntEnum):
    START_RAMP = 1
    STOP_RAMP = 0


class CryoStream(PVPositionerIsClose):
    readback = Cpt(EpicsSignalRO, 'TEMP')
    setpoint = Cpt(EpicsSignal, 'RTEMP')
    actuate = Cpt(EpicsSignal, "RAMP.PROC")
    actuate_value = CryoStreamCmd.START_RAMP
    stop_signal = Cpt(EpicsSignal, "RAMP.PROC")
    stop_value = CryoStreamCmd.STOP_RAMP
