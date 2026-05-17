"""BeamlineDevices — single-entry-point container for all beamline ophyd devices.

Usage::

    bl = BeamlineDevices.from_beamline("fmx", comm_prefix="XF:17IDC-ES:FMX{Comm}", name="bl")
    bl = BeamlineDevices.from_beamline("amx", comm_prefix="XF:17IDB-ES:AMX{Comm}", name="bl")

After construction every subsystem is accessible as an attribute, e.g.::

    bl.governor.robot_status.get()
    bl.goniometer.omega.move(45)
    bl.attenuation.transmission_set.put(0.5)
    bl.misc.beam_available.get()
    bl.flux.get()            # beamline-specific PV, always at bl.flux
    bl.optics.energy.move(12.7)

Sub-devices
-----------
  governor      : Governor
  goniometer    : Goniometer
  vector        : VectorProgram
  low_mag       : LowMagCamera
  high_mag      : HighMagCamera
  top_view      : TopViewCamera
  detector      : Detector
  attenuation   : Attenuation
  optics        : Optics
  cryostream    : CryoStream
  sample_env    : SampleEnvironment
  click_center  : ClickCenter
  misc          : Misc
  ioc_control   : IOCControl
  diagnostics   : Diagnostics
  zebra         : Zebra
  comm          : CommIOC

Top-level signals (beamline-specific PVs that don't fit a single prefix):
  flux            : EpicsSignalRO  — instantaneous photon flux
  sample_lifetime : EpicsSignalRO  — AMX only (None on FMX)
"""

from ophyd import EpicsSignal, EpicsSignalRO

from mxbluesky.devices.governor         import Governor
from mxbluesky.devices.goniometer       import Goniometer
from mxbluesky.devices.vector_program   import VectorProgram
from mxbluesky.devices.cameras          import LowMagCamera, HighMagCamera, TopViewCamera
from mxbluesky.devices.detector         import Detector
from mxbluesky.devices.attenuation      import Attenuation
from mxbluesky.devices.optics           import Optics
from mxbluesky.devices.cryostream       import CryoStream
from mxbluesky.devices.sample_environment import SampleEnvironment
from mxbluesky.devices.click_center     import ClickCenter
from mxbluesky.devices.misc             import Misc
from mxbluesky.devices.ioc_control      import IOCControl
from mxbluesky.devices.diagnostics      import Diagnostics
from mxbluesky.devices.zebra            import Zebra
from mxbluesky.devices.comm             import CommIOC


class BeamlineDevices:
    """Plain-Python container for all ophyd device instances on one beamline.

    Not an ophyd Device — use ``from_beamline`` to construct.
    """

    def __init__(self) -> None:
        self._beamline = ""

    # Sub-device type hints (for IDE support)
    _beamline:      str
    governor:      Governor
    goniometer:    Goniometer
    vector:        VectorProgram
    low_mag:       LowMagCamera
    high_mag:      HighMagCamera
    top_view:      TopViewCamera
    detector:      Detector
    attenuation:   Attenuation
    optics:        Optics
    cryostream:    CryoStream
    sample_env:    SampleEnvironment
    click_center:  ClickCenter
    misc:          Misc
    ioc_control:   IOCControl
    diagnostics:   Diagnostics
    zebra:         Zebra
    comm:          CommIOC
    flux:          EpicsSignalRO
    sample_lifetime: "EpicsSignalRO | None"

    # ------------------------------------------------------------------
    @classmethod
    def from_beamline(
        cls,
        beamline: str,
        comm_prefix: str,
        name: str = "bl",
    ) -> "BeamlineDevices":
        """Instantiate every sub-device for the given beamline.

        Parameters
        ----------
        beamline : {"fmx", "amx"}
        comm_prefix : beamline communication IOC prefix (daq_utils.beamlineComm)
        name     : prefix used when constructing ophyd device names.
        """
        bl = beamline.lower()
        if bl not in ("fmx", "amx"):
            raise ValueError(f"Unknown beamline {beamline!r}; expected 'fmx' or 'amx'.")

        obj = cls()
        obj._beamline = bl

        if bl == "fmx":
            _build_fmx(obj, name, comm_prefix)
        else:
            _build_amx(obj, name, comm_prefix)

        return obj

    def __repr__(self):
        return f"<BeamlineDevices beamline={self._beamline!r}>"


# ---------------------------------------------------------------------------
# Private builders
# ---------------------------------------------------------------------------

def _build_fmx(obj: BeamlineDevices, name: str, comm_prefix: str) -> None:
    """Populate *obj* with FMX devices."""
    _BL  = "XF:17ID"
    es   = f"{_BL}C-ES:FMX"    # XF:17IDC-ES:FMX
    a_op = f"{_BL}A-OP:FMX"    # XF:17IDA-OP:FMX
    c_op = f"{_BL}C-OP:FMX"    # XF:17IDC-OP:FMX
    ct   = f"{_BL}C-CT:FMX"    # XF:17IDC-CT:FMX
    bi   = f"{_BL}C-BI:FMX"    # XF:17IDC-BI:FMX
    pps  = f"{_BL}A-PPS:FMX"   # XF:17IDA-PPS:FMX
    id_op = f"{_BL}-OP:FMX"    # XF:17ID-OP:FMX
    id_es = f"{_BL}-ES:FMX"    # XF:17ID-ES:FMX

    obj.governor = Governor(
        es,
        name=f"{name}_governor",
    )

    obj.goniometer = Goniometer(
        f"{es}{{Gon:1",
        name=f"{name}_goniometer",
    )

    obj.vector = VectorProgram(
        f"{es}{{Gon:1-Vec}}",
        name=f"{name}_vector",
    )

    obj.low_mag = LowMagCamera(
        f"{es}{{Cam:7}}",
        zoom_roi=3,
        name=f"{name}_low_mag",
    )

    obj.high_mag = HighMagCamera(
        f"{es}{{Cam:8}}",
        name=f"{name}_high_mag",
    )

    obj.top_view = TopViewCamera(
        f"{es}{{Cam:11}}",
        name=f"{name}_top_view",
    )

    obj.detector = Detector(
        es,
        eig_token="{Det:Eig16M}",
        cover_token="{Det:FMX-Cover}",
        photon_energy_suffix="{Det:Eig16M}cam1:PhotonEnergy",
        photon_energy_rbv_suffix="{Det:Eig16M}cam1:PhotonEnergy_RBV",
        name=f"{name}_detector",
    )

    obj.attenuation = Attenuation(
        c_op,
        name=f"{name}_attenuation",
    )

    obj.optics = Optics(
        a_op,
        name=f"{name}_optics",
    )

    obj.cryostream = CryoStream(
        f"{es}{{CS:1}}",
        atol=0.1,
        name=f"{name}_cryostream",
    )

    obj.sample_env = SampleEnvironment(
        es,
        name=f"{name}_sample_env",
    )

    obj.click_center = ClickCenter(
        f"{es}{{ClkCtr}}",
        name=f"{name}_click_center",
    )

    obj.misc = Misc(
        "",
        beam_available_pv    =f"{id_op}{{BeamAvail}}",
        exposing_pv          =f"{id_op}{{Exposing}}",
        still_mode_pv        =f"{es}{{Stills}}",
        still_mode_status_pv =f"{es}{{Stills}}-Stat",
        standard_mode_pv     =f"{es}{{Standard}}",
        beam_center_x_pv     =f"{id_es}{{Misc-BeamCenter:X}}Pos-I",
        beam_center_y_pv     =f"{id_es}{{Misc-BeamCenter:Y}}Pos-I",
        low_mag_cursor_x_pv  =f"{id_es}{{Misc-AuxCursor2:X}}Pos-SP",
        low_mag_cursor_y_pv  =f"{id_es}{{Misc-AuxCursor2:Y}}Pos-SP",
        high_mag_cursor_x_pv =f"{id_es}{{Misc-AuxCursor3:X}}Pos-SP",
        high_mag_cursor_y_pv =f"{id_es}{{Misc-AuxCursor3:Y}}Pos-SP",
        vector_delay_pv      =f"{id_es}{{Misc-Vector:Delay}}Pos-SP",
        photon_shutter_open_pv  =f"{pps}{{PSh}}Cmd:Opn-Cmd",
        photon_shutter_close_pv =f"{pps}{{PSh}}Cmd:Cls-Cmd",
        name=f"{name}_misc",
    )

    obj.ioc_control = IOCControl(
        ct,
        eiger_ioc_suffix="{IOC:DET01}:SysReset",
        zebra_ioc_suffix="{IOC:Zeb3}:SysReset",
        name=f"{name}_ioc_control",
    )

    obj.diagnostics = Diagnostics(
        "",
        total_current_pv=f"{bi}{{BPM:4}}SumAll:MeanValue_RBV",
        ring_current_pv="SR:C03-BI{DCCT:1}I:Real-I",
        home_pin_y_pv   =f"{ct}{{SDC:04-Ax:5}}StartHome",
        home_pin_z_pv   =f"{ct}{{SDC:04-Ax:6}}StartHome",
        pi_commands_pv  =f"{ct}{{MC:21}}Asyn.AOUT",
        name=f"{name}_diagnostics",
    )

    obj.zebra = Zebra(
        f"{es}{{Zeb:3}}:",
        name=f"{name}_zebra",
    )

    obj.comm = CommIOC(
        comm_prefix,
        name=f"{name}_comm",
    )

    # Beamline-specific top-level signals
    obj.flux = EpicsSignalRO(
        f"{a_op}{{Mono:DCM-flux}}",
        name=f"{name}_flux",
    )
    obj.sample_lifetime = None  # not present on FMX


def _build_amx(obj: BeamlineDevices, name: str, comm_prefix: str) -> None:
    """Populate *obj* with AMX devices."""
    _BL  = "XF:17ID"
    es   = f"{_BL}B-ES:AMX"    # XF:17IDB-ES:AMX
    a_op = f"{_BL}A-OP:AMX"    # XF:17IDA-OP:AMX
    b_op = f"{_BL}B-OP:AMX"    # XF:17IDB-OP:AMX
    ct   = f"{_BL}B-CT:AMX"    # XF:17IDB-CT:AMX
    bi   = f"{_BL}B-BI:AMX"    # XF:17IDB-BI:AMX
    pps  = f"{_BL}A-PPS:AMX"   # XF:17IDA-PPS:AMX
    id_op = f"{_BL}-OP:AMX"    # XF:17ID-OP:AMX
    id_es = f"{_BL}-ES:AMX"    # XF:17ID-ES:AMX

    obj.governor = Governor(
        es,
        name=f"{name}_governor",
    )

    obj.goniometer = Goniometer(
        f"{es}{{Gon:1",
        name=f"{name}_goniometer",
    )

    obj.vector = VectorProgram(
        f"{es}{{Gon:1-Vec}}",
        name=f"{name}_vector",
    )

    obj.low_mag = LowMagCamera(
        f"{es}{{Cam:6}}",
        zoom_roi=1,
        name=f"{name}_low_mag",
    )

    obj.high_mag = HighMagCamera(
        f"{es}{{Cam:7}}",
        name=f"{name}_high_mag",
    )

    obj.top_view = TopViewCamera(
        f"{es}{{Cam:9}}",
        name=f"{name}_top_view",
    )

    obj.detector = Detector(
        es,
        eig_token="{Det:Eig9M}",
        cover_token="{Det:AMX-Cover}",
        name=f"{name}_detector",
    )

    obj.attenuation = Attenuation(
        b_op,
        name=f"{name}_attenuation",
    )

    obj.optics = Optics(
        a_op,
        name=f"{name}_optics",
    )

    obj.cryostream = CryoStream(
        f"{es}{{CS:1}}",
        atol=0.1,
        name=f"{name}_cryostream",
    )

    obj.sample_env = SampleEnvironment(
        es,
        name=f"{name}_sample_env",
    )

    obj.click_center = ClickCenter(
        f"{es}{{ClkCtr}}",
        name=f"{name}_click_center",
    )

    obj.misc = Misc(
        "",
        beam_available_pv    =f"{id_op}{{BeamAvail}}",
        exposing_pv          =f"{id_op}{{Exposing}}",
        still_mode_pv        =f"{es}{{Stills}}",
        still_mode_status_pv =f"{es}{{Stills}}-Stat",
        standard_mode_pv     =f"{es}{{Standard}}",
        beam_center_x_pv     =f"{id_es}{{Misc-BeamCenter:X}}Pos-I",
        beam_center_y_pv     =f"{id_es}{{Misc-BeamCenter:Y}}Pos-I",
        low_mag_cursor_x_pv  =f"{id_es}{{Misc-AuxCursor2:X}}Pos-SP",
        low_mag_cursor_y_pv  =f"{id_es}{{Misc-AuxCursor2:Y}}Pos-SP",
        high_mag_cursor_x_pv =f"{id_es}{{Misc-AuxCursor3:X}}Pos-SP",
        high_mag_cursor_y_pv =f"{id_es}{{Misc-AuxCursor3:Y}}Pos-SP",
        vector_delay_pv      =f"{id_es}{{Misc-Vector:Delay}}Pos-SP",
        photon_shutter_open_pv  =f"{pps}{{PSh}}Cmd:Opn-Cmd",
        photon_shutter_close_pv =f"{pps}{{PSh}}Cmd:Cls-Cmd",
        name=f"{name}_misc",
    )

    obj.ioc_control = IOCControl(
        ct,
        eiger_ioc_suffix="{IOC:DET02}:SysReset.VAL",
        zebra_ioc_suffix="{IOC:Zeb2}:SysReset",
        name=f"{name}_ioc_control",
    )

    obj.diagnostics = Diagnostics(
        "",
        total_current_pv=f"{bi}{{BPM:3}}SumAll:MeanValue_RBV",
        ring_current_pv="SR:C03-BI{DCCT:1}I:Real-I",
        home_pin_y_pv   =f"{ct}{{SDC:04-Ax:5}}StartHome",
        home_pin_z_pv   =f"{ct}{{SDC:04-Ax:6}}StartHome",
        # pi_commands_pv intentionally omitted (AMX has no PIcommands)
        name=f"{name}_diagnostics",
    )

    obj.zebra = Zebra(
        f"{es}{{Zeb:2}}:",
        name=f"{name}_zebra",
    )

    obj.comm = CommIOC(
        comm_prefix,
        name=f"{name}_comm",
    )

    # Beamline-specific top-level signals
    obj.flux = EpicsSignalRO(
        f"{id_es}{{Misc-BeamFlux}}Pos-SP",
        name=f"{name}_flux",
    )
    obj.sample_lifetime = EpicsSignalRO(
        f"{a_op}{{Mono:DCM-life}}",
        name=f"{name}_sample_lifetime",
    )
