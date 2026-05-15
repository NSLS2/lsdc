"""Goniometer device — extends GoniometerStack with DB-mapped signals.

Instantiate with the ``{Gon:1`` prefix, e.g.::

    gonio = Goniometer("XF:17IDC-ES:FMX{Gon:1", name="gonio")   # FMX
    gonio = Goniometer("XF:17IDB-ES:AMX{Gon:1", name="gonio")   # AMX

Fine-axis motors (fine_x/y/z) and their waveform-control signals are
FMX-only; they will remain disconnected on AMX.
"""

from ophyd import Component as Cpt, EpicsMotor, EpicsSignal, EpicsSignalRO
from mxbluesky.devices.generic import GoniometerStack


class Goniometer(GoniometerStack):
    """GoniometerStack augmented with limit, sync-pin, shutter-pos, and
    FMX fine-axis signals."""

    # --- goniometer X limits (both beamlines) ---
    x_high_limit      = Cpt(EpicsSignalRO, "-Ax:GX}Mtr.HLM")   # gonXHiLim
    x_low_limit       = Cpt(EpicsSignalRO, "-Ax:GX}Mtr.LLM")   # gonXLoLim

    # --- pin-sync flags (both beamlines) ---
    sync_pin_y        = Cpt(EpicsSignal,   "-Ax:PY}Mtr.SYNC")   # syncPinY
    sync_pin_z        = Cpt(EpicsSignal,   "-Ax:PZ}Mtr.SYNC")   # syncPinZ

    # --- fast shutter calibrated positions (both beamlines) ---
    fast_shutter_open_pos  = Cpt(EpicsSignalRO, "-Sht}Pos:Opn-I")  # fastShutterOpenPos
    fast_shutter_close_pos = Cpt(EpicsSignalRO, "-Sht}Pos:Cls-I")  # fastShutterClosePos

    # --- FMX-only: fine axis motors ---
    fine_x = Cpt(EpicsMotor, "-Ax:Xf}Mtr")   # fineX
    fine_y = Cpt(EpicsMotor, "-Ax:Yf}Mtr")   # fineY
    fine_z = Cpt(EpicsMotor, "-Ax:Zf}Mtr")   # fineZ

    # --- FMX-only: fine axis waveform parameters ---
    fine_x_points    = Cpt(EpicsSignal, "-Ax:Xf}Vec.A")       # fineXPoints
    fine_x_amp       = Cpt(EpicsSignal, "-Ax:Xf}Vec.B")       # fineXAmp
    fine_x_offset    = Cpt(EpicsSignal, "-Ax:Xf}Vec.C")       # fineXOffset
    fine_y_points    = Cpt(EpicsSignal, "-Ax:Yf}Vec.A")       # fineYPoints
    fine_y_amp       = Cpt(EpicsSignal, "-Ax:Yf}Vec.B")       # fineYAmp
    fine_y_offset    = Cpt(EpicsSignal, "-Ax:Yf}Vec.C")       # fineYOffset
    fine_z_points    = Cpt(EpicsSignal, "-Ax:Zf}Vec.A")       # fineZPoints
    fine_z_amp       = Cpt(EpicsSignal, "-Ax:Zf}Vec.B")       # fineZAmp
    fine_z_offset    = Cpt(EpicsSignal, "-Ax:Zf}Vec.C")       # fineZOffset

    # --- FMX-only: fine axis waveform send / go triggers ---
    fine_x_send_wave = Cpt(EpicsSignal, "-Ax:Xf}Vec.PROC")    # fineXSendWave
    fine_y_send_wave = Cpt(EpicsSignal, "-Ax:Yf}Vec.PROC")    # fineYSendWave
    fine_z_send_wave = Cpt(EpicsSignal, "-Ax:Zf}Vec.PROC")    # fineZSendWave
    fine_x_vec_go    = Cpt(EpicsSignal, "-Ax:Xf}VecGo.PROC")  # fineXVecGo
    fine_y_vec_go    = Cpt(EpicsSignal, "-Ax:Yf}VecGo.PROC")  # fineYVecGo
    fine_z_vec_go    = Cpt(EpicsSignal, "-Ax:Zf}VecGo.PROC")  # fineZVecGo
