"""Misc device — miscellaneous beamline-wide signals spanning multiple IOC
prefixes.

Because these PVs live across several different IOC prefix domains, the
device uses ``FormattedComponent`` with ``prefix=""`` and accepts fully-
qualified PV strings at instantiation.  The ``BeamlineDevices.from_beamline``
factory provides the correct PV strings.

Direct instantiation (example, FMX)::

    from mxbluesky.devices.misc import Misc
    misc = Misc(
        "",
        beam_available_pv   ="XF:17ID-OP:FMX{BeamAvail}",
        exposing_pv         ="XF:17ID-OP:FMX{Exposing}",
        still_mode_pv       ="XF:17IDC-ES:FMX{Stills}",
        still_mode_status_pv="XF:17IDC-ES:FMX{Stills}-Stat",
        standard_mode_pv    ="XF:17IDC-ES:FMX{Standard}",
        beam_center_x_pv    ="XF:17ID-ES:FMX{Misc-BeamCenter:X}Pos-I",
        beam_center_y_pv    ="XF:17ID-ES:FMX{Misc-BeamCenter:Y}Pos-I",
        low_mag_cursor_x_pv ="XF:17ID-ES:FMX{Misc-AuxCursor2:X}Pos-SP",
        low_mag_cursor_y_pv ="XF:17ID-ES:FMX{Misc-AuxCursor2:Y}Pos-SP",
        high_mag_cursor_x_pv="XF:17ID-ES:FMX{Misc-AuxCursor3:X}Pos-SP",
        high_mag_cursor_y_pv="XF:17ID-ES:FMX{Misc-AuxCursor3:Y}Pos-SP",
        vector_delay_pv     ="XF:17ID-ES:FMX{Misc-Vector:Delay}Pos-SP",
        photon_shutter_open_pv ="XF:17IDA-PPS:FMX{PSh}Cmd:Opn-Cmd",
        photon_shutter_close_pv="XF:17IDA-PPS:FMX{PSh}Cmd:Cls-Cmd",
        name="misc",
    )
"""

from ophyd import FormattedComponent as FCpt, Device
from ophyd import EpicsSignal, EpicsSignalRO


class Misc(Device):
    """Miscellaneous beamline-wide signals (beam status, cursors, shutters)."""

    # --- beam availability / exposure state ---
    beam_available    = FCpt(EpicsSignalRO, "{self._beam_available_pv}")    # beamAvailable
    exposing          = FCpt(EpicsSignalRO, "{self._exposing_pv}")          # exposing

    # --- still / standard mode toggle ---
    still_mode        = FCpt(EpicsSignal,   "{self._still_mode_pv}")        # stillMode
    still_mode_status = FCpt(EpicsSignalRO, "{self._still_mode_status_pv}") # stillModeStatus
    standard_mode     = FCpt(EpicsSignal,   "{self._standard_mode_pv}")     # standardMode

    # --- beam centre (detector geometry) ---
    beam_center_x     = FCpt(EpicsSignalRO, "{self._beam_center_x_pv}")     # beamCenterX
    beam_center_y     = FCpt(EpicsSignalRO, "{self._beam_center_y_pv}")     # beamCenterY

    # --- on-screen cursor positions ---
    low_mag_cursor_x  = FCpt(EpicsSignal,   "{self._low_mag_cursor_x_pv}")  # lowMagCursorX
    low_mag_cursor_y  = FCpt(EpicsSignal,   "{self._low_mag_cursor_y_pv}")  # lowMagCursorY
    high_mag_cursor_x = FCpt(EpicsSignal,   "{self._high_mag_cursor_x_pv}") # highMagCursorX
    high_mag_cursor_y = FCpt(EpicsSignal,   "{self._high_mag_cursor_y_pv}") # highMagCursorY

    # --- vector scan trigger delay ---
    vector_delay      = FCpt(EpicsSignal,   "{self._vector_delay_pv}")      # vectorDelay

    # --- photon shutter ---
    photon_shutter_open  = FCpt(EpicsSignal, "{self._photon_shutter_open_pv}")   # photonShutterOpen
    photon_shutter_close = FCpt(EpicsSignal, "{self._photon_shutter_close_pv}")  # photonShutterClose

    def __init__(self, *args,
                 beam_available_pv,
                 exposing_pv,
                 still_mode_pv,
                 still_mode_status_pv,
                 standard_mode_pv,
                 beam_center_x_pv,
                 beam_center_y_pv,
                 low_mag_cursor_x_pv,
                 low_mag_cursor_y_pv,
                 high_mag_cursor_x_pv,
                 high_mag_cursor_y_pv,
                 vector_delay_pv,
                 photon_shutter_open_pv,
                 photon_shutter_close_pv,
                 **kwargs):
        self._beam_available_pv      = beam_available_pv
        self._exposing_pv            = exposing_pv
        self._still_mode_pv          = still_mode_pv
        self._still_mode_status_pv   = still_mode_status_pv
        self._standard_mode_pv       = standard_mode_pv
        self._beam_center_x_pv       = beam_center_x_pv
        self._beam_center_y_pv       = beam_center_y_pv
        self._low_mag_cursor_x_pv    = low_mag_cursor_x_pv
        self._low_mag_cursor_y_pv    = low_mag_cursor_y_pv
        self._high_mag_cursor_x_pv   = high_mag_cursor_x_pv
        self._high_mag_cursor_y_pv   = high_mag_cursor_y_pv
        self._vector_delay_pv        = vector_delay_pv
        self._photon_shutter_open_pv = photon_shutter_open_pv
        self._photon_shutter_close_pv = photon_shutter_close_pv
        super().__init__(*args, **kwargs)
