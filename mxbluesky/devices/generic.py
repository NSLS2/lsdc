from ophyd import Component as Cpt, Device, EpicsMotor, EpicsSignal, EpicsSignalRO, DynamicDeviceComponent as DDC
from ophyd.status import SubscriptionStatus
from mxbluesky.devices import standardize_readback
from enum import IntEnum, unique

class WorkPositions(Device):
    gx = Cpt(EpicsSignal, "{Gov:Robot-Dev:gx}Pos:Work-Pos")
    gpy = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpy}Pos:Work-Pos")
    gpz = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpz}Pos:Work-Pos")
    o = Cpt(EpicsSignal, "{Gov:Robot-Dev:go}Pos:Work-Pos")


class MountPositions(Device):
    gx = Cpt(EpicsSignal, "{Gov:Robot-Dev:gx}Pos:Mount-Pos")
    py = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpy}Pos:Mount-Pos")
    pz = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpz}Pos:Mount-Pos")
    o = Cpt(EpicsSignal, "{Gov:Robot-Dev:go}Pos:Mount-Pos")

@standardize_readback
class GoniometerStack(Device):
    gx = Cpt(EpicsMotor, "-Ax:GX}Mtr")
    gy = Cpt(EpicsMotor, "-Ax:GY}Mtr")
    gz = Cpt(EpicsMotor, "-Ax:GZ}Mtr")
    o = Cpt(EpicsMotor, "-Ax:O}Mtr")
    py = Cpt(EpicsMotor, "-Ax:PY}Mtr")
    pz = Cpt(EpicsMotor, "-Ax:PZ}Mtr")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Renaming to match MD2 GonioDevice
        self.x = self.gx
        self.cx = self.gx
        self.y = self.py
        self.cy = self.py
        self.z = self.pz
        self.cz = self.pz
        self.omega = self.o

class Puck(Device):
    status = Cpt(EpicsSignalRO, "-Sts")

class Sector(Device):
    A = Cpt(Puck, "A", name="A")
    B = Cpt(Puck, "B", name="B")
    C = Cpt(Puck, "C", name="C")

class Dewar(Device):
    rotation = Cpt(EpicsSignal, "{Dew:1-Ax:R}Virtual")
    rotation_motor = Cpt(EpicsMotor, "{Dew:1-Ax:R}Mtr")
    sectors = DDC(
        {
            f"sector_{i}": (Sector, f"{{Wago:1}}Puck{i}", {"name": "sector_{i}"})
            for i in range(1, 9)
        }
    )
    num_sectors = 8

    def get_puck_status(self, puck_pos: str):
        # puck_pos assumed to be of the form "7A"
        sector = getattr(self.sectors, f"sector_{puck_pos[0]}")
        puck: Puck = getattr(sector, puck_pos[1])
        return puck.status.get()

    def rotate(self, rotation_angle, absolute=True):
        def check_value_sink(*, old_value, value, **kwargs):
            "Return True when the movement is complete, False otherwise."
            return old_value == 1 and value == 0

        def check_value_raise(*, old_value, value, **kwargs):
            "Return True when the movement is started, False otherwise."
            return old_value == 0 and value == 1

        status = SubscriptionStatus(
            self.rotation_motor.motor_done_move, check_value_sink
        )
        if not self.rotation_motor.motor_done_move.get():
            raise RuntimeError("Dewar rotation motor already moving.")
            ### Maybe don't raise an error here but rather do a timeout retry?
        if absolute:
            self.rotation.set(rotation_angle)
        else:
            current_angle = self.rotation.get()
            self.rotation.set(current_angle + rotation_angle)
        status.wait()
        status = SubscriptionStatus(
            self.rotation_motor.motor_done_move, check_value_raise
        )
        status.wait()


class RobotArm(Device):
    speed = Cpt(EpicsSignal, '{EMBL}:RobotSpeed')

    def is_full_speed(self):
        # Checks if the robot speed is 100%
        if self.speed.get() < 100:
            return False
        return True

