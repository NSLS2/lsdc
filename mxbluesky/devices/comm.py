"""CommIOC device — beamline communication IOC channels.

This device models PVs under ``daq_utils.beamlineComm`` so GUI/server code can
use ophyd signals directly instead of ad-hoc ``epics.PV`` objects.

The signal list is split into:
1) channels actively referenced in current code paths, and
2) channels declared in ``daq_lib.var_list`` but currently unused.
"""

from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal


# --- actively referenced comm channels ---
ACTIVE_COMM_SIGNAL_SPECS = {
    # Explicit beamlineComm + "..." usages
    "command_s": ("command_s", {"string": True}),
    "immediate_command_s": ("immediate_command_s", {"string": True}),
    "live_q_change_flag": ("live_q_change_flag", {}),
    "zinger_flag": ("zinger_flag", {}),
    "message_string": ("message_string", {"string": True}),
    "gui_popup_message_string": ("gui_popup_message_string", {"string": True}),
    "restart_server_signal": ("RestartServerSignal", {}),
    # daq_lib.set_field/get_field usages
    "beam_check_flag": ("beam_check_flag", {}),
    "beamline_merit": ("beamline_merit", {}),
    "chooch_result_flag": ("choochResultFlag", {"string": True}),
    "datum_kappa": ("datum_kappa", {}),
    "datum_omega": ("datum_omega", {}),
    "datum_phi": ("datum_phi", {}),
    "distance": ("distance", {}),
    "group_name": ("group_name", {"string": True}),
    "kappa": ("kappa", {}),
    "mounted_pin": ("mounted_pin", {"string": True}),
    "omega": ("omega", {}),
    "overwrite_check_flag": ("overwrite_check_flag", {}),
    "pause_button_state": ("pause_button_state", {"string": True}),
    "phi": ("phi", {}),
    "program_state": ("program_state", {"string": True}),
    "size_mode": ("size_mode", {}),
    "spcgrp": ("spcgrp", {}),
    "state": ("state", {"string": True}),
    "xrec_raster_flag": ("xrecRasterFlag", {"string": True}),
    "xtal_id": ("xtal_id", {"string": True}),
}


# --- declared in daq_lib.var_list, currently unused in code ---
CURRENTLY_UNUSED_COMM_SIGNAL_SPECS = {
    "active_sweep": ("active_sweep", {}),
    "col_end0": ("col_end0", {}),
    "col_start0": ("col_start0", {}),
    "current_pinpos": ("current_pinpos", {}),
    "datafilename": ("datafilename", {"string": True}),
    "edna_aimed_isig": ("edna_aimed_ISig", {}),
    "edna_aimed_completeness": ("edna_aimed_completeness", {}),
    "edna_aimed_multiplicity": ("edna_aimed_multiplicity", {"string": True}),
    "edna_aimed_resolution": ("edna_aimed_resolution", {"string": True}),
    "energy_fall": ("energy_fall", {}),
    "energy_inflection": ("energy_inflection", {}),
    "energy_peak": ("energy_peak", {}),
    "exptime0": ("exptime0", {}),
    "f2prime_infl": ("f2prime_infl", {}),
    "f2prime_peak": ("f2prime_peak", {}),
    "file_prefix0": ("file_prefix0", {"string": True}),
    "filter": ("filter", {}),
    "fprime_infl": ("fprime_infl", {}),
    "fprime_peak": ("fprime_peak", {}),
    "grid_exptime": ("grid_exptime", {}),
    "grid_imwidth": ("grid_imwidth", {}),
    "html_logging": ("html_logging", {}),
    "inc0": ("inc0", {}),
    "mono_energy_current": ("mono_energy_current", {}),
    "mono_energy_scan_step": ("mono_energy_scan_step", {}),
    "mono_energy_target": ("mono_energy_target", {}),
    "mono_scan_points": ("mono_scan_points", {}),
    "mono_wave_current": ("mono_wave_current", {}),
    "mono_wave_target": ("mono_wave_target", {}),
    "numstart0": ("numstart0", {}),
    "px_id": ("px_id", {"string": True}),
    "rot_dist0": ("rot_dist0", {}),
    "scan_axis": ("scan_axis", {"string": True}),
    "state_percent": ("state_percent", {}),
    "sweep_count": ("sweep_count", {}),
    "take_xtal_pics": ("take_xtal_pics", {}),
    "theta": ("theta", {}),
    "vector_fpp": ("vector_fpp", {}),
    "vector_on": ("vector_on", {}),
    "vector_step": ("vector_step", {}),
    "vector_translation": ("vector_translation", {}),
    "wave_fall": ("wave_fall", {}),
    "wave_inflection": ("wave_inflection", {}),
    "wave_peak": ("wave_peak", {}),
    "wavelength0": ("wavelength0", {}),
    "xia2_on": ("xia2_on", {}),
}


ALL_COMM_SIGNAL_SPECS = {
    **ACTIVE_COMM_SIGNAL_SPECS,
    **CURRENTLY_UNUSED_COMM_SIGNAL_SPECS,
}

COMM_SUFFIX_BY_ATTR = {
    attr: suffix for attr, (suffix, _kwargs) in ALL_COMM_SIGNAL_SPECS.items()
}


class CommIOC(Device):
    """Beamline communication IOC channels (prefix == beamlineComm)."""

    for _attr, (_suffix, _kwargs) in ACTIVE_COMM_SIGNAL_SPECS.items():
        locals()[_attr] = Cpt(EpicsSignal, _suffix, **_kwargs)

    for _attr, (_suffix, _kwargs) in CURRENTLY_UNUSED_COMM_SIGNAL_SPECS.items():
        locals()[_attr] = Cpt(EpicsSignal, _suffix, **_kwargs)

    del _attr, _suffix, _kwargs
