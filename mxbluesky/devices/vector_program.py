"""VectorProgram device — vector-scan motion controller signals.

Covers all 19 ``{Gon:1-Vec}`` descriptors from both DB files.

Instantiate with the full ``{Gon:1-Vec}`` PV base, e.g.::

    vector = VectorProgram("XF:17IDC-ES:FMX{Gon:1-Vec}", name="vector")  # FMX
    vector = VectorProgram("XF:17IDB-ES:AMX{Gon:1-Vec}", name="vector")  # AMX
"""

from ophyd import Component as Cpt, Device, EpicsSignal, EpicsSignalRO


class VectorProgram(Device):
    """Vector-scan motion controller."""

    # --- timing ---
    buffer_time   = Cpt(EpicsSignal,   "Val:BufferTime-SP")    # vectorBufferTime

    # --- control commands ---
    hold          = Cpt(EpicsSignal,   "Hold-Sel")              # vectorHold
    expose        = Cpt(EpicsSignal,   "Expose-Sel")            # vectorExpose
    go            = Cpt(EpicsSignal,   "Cmd:Go-Cmd")            # vectorGo
    proceed       = Cpt(EpicsSignal,   "Cmd:Proceed-Cmd")       # vectorProceed
    abort         = Cpt(EpicsSignal,   "Cmd:Abort-Cmd")         # vectorAbort
    sync          = Cpt(EpicsSignal,   "Cmd:Sync-Cmd")          # vectorSync

    # --- start / end positions ---
    start_x       = Cpt(EpicsSignal,   "Pos:XStart-SP")         # vectorStartX
    start_y       = Cpt(EpicsSignal,   "Pos:YStart-SP")         # vectorStartY
    start_z       = Cpt(EpicsSignal,   "Pos:ZStart-SP")         # vectorStartZ
    end_x         = Cpt(EpicsSignal,   "Pos:XEnd-SP")           # vectorEndX
    end_y         = Cpt(EpicsSignal,   "Pos:YEnd-SP")           # vectorEndY
    end_z         = Cpt(EpicsSignal,   "Pos:ZEnd-SP")           # vectorEndZ
    start_omega   = Cpt(EpicsSignal,   "Pos:OStart-SP")         # vectorStartOmega
    end_omega     = Cpt(EpicsSignal,   "Pos:OEnd-SP")           # vectorEndOmega

    # --- collection parameters ---
    frame_exp_time = Cpt(EpicsSignal,  "Val:Exposure-SP")       # vectorframeExptime
    num_frames     = Cpt(EpicsSignal,  "Val:NumSamples-SP")     # vectorNumFrames

    # --- status readbacks ---
    active        = Cpt(EpicsSignalRO, "Sts:Running-Sts")       # VectorActive
    state         = Cpt(EpicsSignalRO, "Sts:State-Sts")         # VectorState
