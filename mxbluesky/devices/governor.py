"""Governor device — robot and human governor state machines.

Instantiate with the C-ES (or B-ES) beamline prefix, e.g.::

    gov = Governor("XF:17IDC-ES:FMX", name="governor")
    gov = Governor("XF:17IDB-ES:AMX", name="governor")

All 38 governor PV descriptors from the DB are covered.
"""

from ophyd import Component as Cpt, Device, EpicsSignal, EpicsSignalRO


class Governor(Device):
    """Robot and human governor state-machine signals."""

    # Governor top-level
    reboot          = Cpt(EpicsSignal,   "{Gov}Cmd:Kill-Cmd")       # rebootGovernor
    config          = Cpt(EpicsSignal,   "{Gov}Config-Sel")          # robotGovConfig
    active          = Cpt(EpicsSignal,   "{Gov}Active-Sel")          # robotGovActive

    # Robot governor
    robot_status    = Cpt(EpicsSignalRO, "{Gov:Robot}Sts:Status-Sts")  # robotGovStatus
    robot_go        = Cpt(EpicsSignal,   "{Gov:Robot}Cmd:Go-Cmd")       # robotGovGo
    message         = Cpt(EpicsSignalRO, "{Gov:Robot}Sts:Msg-Sts",
                          string=True)                                   # governorMessage

    # Human governor
    human_status    = Cpt(EpicsSignalRO, "{Gov:Human}Sts:Status-Sts")  # humanGovStatus
    human_go        = Cpt(EpicsSignal,   "{Gov:Human}Cmd:Go-Cmd")       # humanGovGo

    # Robot governor — state active flags
    robot_se_active = Cpt(EpicsSignalRO, "{Gov:Robot-St:SE}Sts:Active-Sts")  # robotSeActive
    robot_xf_active = Cpt(EpicsSignalRO, "{Gov:Robot-St:XF}Sts:Active-Sts")  # robotXfActive
    robot_bl_active = Cpt(EpicsSignalRO, "{Gov:Robot-St:BL}Sts:Active-Sts")  # robotBlActive
    robot_sa_active = Cpt(EpicsSignalRO, "{Gov:Robot-St:SA}Sts:Active-Sts")  # robotSaActive
    robot_da_active = Cpt(EpicsSignalRO, "{Gov:Robot-St:DA}Sts:Active-Sts")  # robotDaActive
    robot_di_active = Cpt(EpicsSignalRO, "{Gov:Robot-St:DI}Sts:Active-Sts")  # robotDiActive
    robot_m_active  = Cpt(EpicsSignalRO, "{Gov:Robot-St:M}Sts:Active-Sts")   # robotMActive

    # Human governor — state active flags
    human_se_active = Cpt(EpicsSignalRO, "{Gov:Human-St:SE}Sts:Active-Sts")  # humanSeActive
    human_xf_active = Cpt(EpicsSignalRO, "{Gov:Human-St:XF}Sts:Active-Sts")  # humanXfActive
    human_bl_active = Cpt(EpicsSignalRO, "{Gov:Human-St:BL}Sts:Active-Sts")  # humanBlActive
    human_sa_active = Cpt(EpicsSignalRO, "{Gov:Human-St:SA}Sts:Active-Sts")  # humanSaActive
    human_da_active = Cpt(EpicsSignalRO, "{Gov:Human-St:DA}Sts:Active-Sts")  # humanDaActive
    human_m_active  = Cpt(EpicsSignalRO, "{Gov:Human-St:M}Sts:Active-Sts")   # humanMActive

    # Robot governor — state reach flags (SA state)
    robot_se_reach  = Cpt(EpicsSignalRO, "{Gov:Robot-St:SE}Sts:Reach-Sts")   # govRobotSeReach
    robot_sa_reach  = Cpt(EpicsSignalRO, "{Gov:Robot-St:SA}Sts:Reach-Sts")   # govRobotSaReach
    robot_bl_reach  = Cpt(EpicsSignalRO, "{Gov:Robot-St:BL}Sts:Reach-Sts")   # govRobotBlReach
    robot_da_reach  = Cpt(EpicsSignalRO, "{Gov:Robot-St:DA}Sts:Reach-Sts")   # govRobotDaReach

    # Robot governor — SA state goniometer limits
    robot_x_mount_low_lim = Cpt(EpicsSignalRO, "{Gov:Robot-St:SA}LLim:gx-Pos")  # robotXMountLowLim
    robot_x_mount_hi_lim  = Cpt(EpicsSignalRO, "{Gov:Robot-St:SA}HLim:gx-Pos")  # robotXMountHiLim

    # Robot governor — device positions
    robot_x_mount_pos    = Cpt(EpicsSignal, "{Gov:Robot-Dev:gx}Pos:Mount-Pos")   # robotXMountPos
    robot_x_work_pos     = Cpt(EpicsSignal, "{Gov:Robot-Dev:gx}Pos:Work-Pos")    # robotXWorkPos
    robot_y_mount_pos    = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpy}Pos:Mount-Pos")  # robotYMountPos
    robot_y_work_pos     = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpy}Pos:Work-Pos")   # robotYWorkPos
    robot_z_mount_pos    = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpz}Pos:Mount-Pos")  # robotZMountPos
    robot_z_work_pos     = Cpt(EpicsSignal, "{Gov:Robot-Dev:gpz}Pos:Work-Pos")   # robotZWorkPos
    robot_omega_work_pos = Cpt(EpicsSignal, "{Gov:Robot-Dev:go}Pos:Work-Pos")    # robotOmegaWorkPos

    # Detector distance positions (human and robot)
    human_det_dist     = Cpt(EpicsSignal, "{Gov:Human-Dev:dz}Pos:In-Pos")   # govHumanDetDist
    human_det_dist_out = Cpt(EpicsSignal, "{Gov:Human-Dev:dz}Pos:Out-Pos")  # govHumanDetDistOut
    robot_det_dist     = Cpt(EpicsSignal, "{Gov:Robot-Dev:dz}Pos:In-Pos")   # govRobotDetDist
    robot_det_dist_out = Cpt(EpicsSignal, "{Gov:Robot-Dev:dz}Pos:Out-Pos")  # govRobotDetDistOut
