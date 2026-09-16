"""SampleEnvironment device — Wago I/O, FTS force sensor, CS8 cryo,
back light, and sample-handling motors.

All signals share the ``C-ES:FMX`` / ``B-ES:AMX`` ES prefix.

``sample_protect`` (FMX-only SPSEnable) will be disconnected on AMX.

Instantiation::

    env = SampleEnvironment("XF:17IDC-ES:FMX", name="sample_env")  # FMX
    env = SampleEnvironment("XF:17IDB-ES:AMX", name="sample_env")  # AMX
"""

from ophyd import Component as Cpt, Device, EpicsMotor, EpicsSignal, EpicsSignalRO


class SampleEnvironment(Device):
    """Wago I/O, FTS force sensor, CS8 cryo controller, back-light,
    and sample-handling motors (fast shutter, dewar rotation, cryo XY)."""

    # --- Wago I/O --- (both beamlines unless noted)
    anneal_in        = Cpt(EpicsSignal,   "{Wago:1}AnnealerAir-Sel")      # annealIn
    anneal_status    = Cpt(EpicsSignalRO, "{Wago:1}AnnealerIn-Sts")       # annealStatus
    gripper_closed   = Cpt(EpicsSignalRO, "{Wago:1}BimbaClosed-Sts")      # gripperClosed
    gripper_open     = Cpt(EpicsSignalRO, "{Wago:1}BimbaOpen-Sts")        # gripperOpen
    sample_detected  = Cpt(EpicsSignalRO, "{Wago:1}SampleDetected1-Sts")  # sampleDetected
    boost_select     = Cpt(EpicsSignal,   "{Wago:1}Boost-Sel")             # boostSelect
    boost_status     = Cpt(EpicsSignalRO, "{Wago:1}Boost-Sts")            # boostStatus
    grip_temp        = Cpt(EpicsSignalRO, "{Wago:1}GripperTemp-I")        # gripTemp

    # --- FTS force/torque sensor ---
    robot_force_x    = Cpt(EpicsSignalRO, "{FTS:1}ForceX-I")              # robotForceX
    robot_force_y    = Cpt(EpicsSignalRO, "{FTS:1}ForceY-I")              # robotForceY
    robot_force_z    = Cpt(EpicsSignalRO, "{FTS:1}ForceZ-I")              # robotForceZ
    robot_fts_status = Cpt(EpicsSignalRO, "{FTS:1}Status-I")              # robotFTSensorStat

    # --- CS8 cryo controller ---
    warmup_threshold_rbv = Cpt(EpicsSignalRO, "{CS8}WarmupThreshold_RBV") # warmupThresholdRBV
    warmup_threshold     = Cpt(EpicsSignal,   "{CS8}WarmupThreshold")     # warmupThreshold
    dewar_plate_pos      = Cpt(EpicsSignal,   "{CS8}PlatePosition")       # dewarPlatePos

    # --- back-light value ---
    back_light_val   = Cpt(EpicsSignal,   "{BL:1}Ch1Value")               # backLightVal

    # --- FMX-only: sample protection interlock ---
    sample_protect   = Cpt(EpicsSignal,   "{SPSEnable}")                  # sampleProtect

    # --- sample-handling motors (both beamlines) ---
    fast_shutter     = Cpt(EpicsMotor,    "{Sht:1-Ax:R}Mtr")             # fastShutter
    dewar_rot        = Cpt(EpicsMotor,    "{Dew:1-Ax:R}Mtr")             # dewarRot
    cryo_xy          = Cpt(EpicsMotor,    "{CS:1-Ax:XY}Mtr")             # cryoXY
