"""Detector device — Eiger detector, cover, mercury MCA, and detector Z axis.

The Eiger model token (e.g. ``{Det:Eig16M}``) and cover token
(e.g. ``{Det:FMX-Cover}``) differ between beamlines and are injected
at instantiation via keyword arguments.

Photon energy signals exist only on FMX; pass ``photon_energy_suffix``
and ``photon_energy_rbv_suffix`` for FMX, omit (empty string) for AMX.
Those two components carry ``lazy=True`` so AMX instantiation succeeds.

Note on FormattedComponent (FCpt):
  FCpt produces the FULL PV string — the device prefix is NOT auto-prepended.
  Full PV strings are therefore pre-computed in ``__init__`` from the supplied
  prefix + token arguments and stored as instance attributes.

Instantiation examples::

    # FMX
    det = Detector(
        "XF:17IDC-ES:FMX",
        eig_token="{Det:Eig16M}",
        cover_token="{Det:FMX-Cover}",
        photon_energy_suffix="{Det:Eig16M}cam1:PhotonEnergy",
        photon_energy_rbv_suffix="{Det:Eig16M}cam1:PhotonEnergy_RBV",
        name="detector",
    )

    # AMX
    det = Detector(
        "XF:17IDB-ES:AMX",
        eig_token="{Det:Eig9M}",
        cover_token="{Det:AMX-Cover}",
        name="detector",
    )
"""

from ophyd import Component as Cpt, FormattedComponent as FCpt, Device
from ophyd import EpicsMotor, EpicsSignal, EpicsSignalRO


class Detector(Device):
    """Eiger detector + detector-Z motor + cover + mercury MCA."""

    # --- detector Z motor (same token on both beamlines) ---
    dist              = Cpt(EpicsMotor,    "{Det-Ax:Z}Mtr")         # detectorDist

    # --- Eiger control / status (full PVs pre-computed in __init__) ---
    acquire           = FCpt(EpicsSignal,   "{self._acquire_pv}")
    status_message    = FCpt(EpicsSignalRO, "{self._status_message_pv}",  string=True)
    nx                = FCpt(EpicsSignalRO, "{self._nx_pv}")
    ny                = FCpt(EpicsSignalRO, "{self._ny_pv}")
    description       = FCpt(EpicsSignalRO, "{self._description_pv}",     string=True)
    roi_mode          = FCpt(EpicsSignal,   "{self._roi_mode_pv}")

    # --- photon energy (FMX only; lazy so AMX instantiation succeeds) ---
    photon_energy     = FCpt(EpicsSignal,   "{self._photon_energy_pv}",     lazy=True)
    photon_energy_rbv = FCpt(EpicsSignalRO, "{self._photon_energy_rbv_pv}", lazy=True)

    # --- detector cover (full PVs pre-computed in __init__) ---
    cover_status      = FCpt(EpicsSignalRO, "{self._cover_status_pv}")
    cover_open        = FCpt(EpicsSignal,   "{self._cover_open_pv}")

    # --- Mercury MCA (same token on both beamlines) ---
    mercury_erase     = Cpt(EpicsSignal,   "{Det:Mer}mca1.ERST")    # mercuryEraseStart
    mercury_spectrum  = Cpt(EpicsSignalRO, "{Det:Mer}mca1.VAL")     # mercurySpectrum
    mercury_read_stat = Cpt(EpicsSignalRO, "{Det:Mer}mca1.READ")    # mercuryReadStat
    mca_roi_lo        = Cpt(EpicsSignal,   "{Det:Mer}mca1.R0LO")    # mcaRoiLo
    mca_roi_hi        = Cpt(EpicsSignal,   "{Det:Mer}mca1.R0HI")    # mcaRoiHi

    def __init__(self, prefix, *args,
                 eig_token,
                 cover_token,
                 photon_energy_suffix="",
                 photon_energy_rbv_suffix="",
                 **kwargs):
        # Pre-compute full PV strings before super().__init__ triggers FCpt resolution.
        # (FCpt produces the FULL PV; device prefix is NOT auto-prepended.)
        self._acquire_pv        = f"{prefix}{eig_token}cam1:Acquire"
        self._status_message_pv = f"{prefix}{eig_token}cam1:StatusMessage_RBV"
        self._nx_pv             = f"{prefix}{eig_token}cam1:ArraySizeX_RBV"
        self._ny_pv             = f"{prefix}{eig_token}cam1:ArraySizeY_RBV"
        self._description_pv    = f"{prefix}{eig_token}cam1:Description_RBV"
        self._roi_mode_pv       = f"{prefix}{eig_token}cam1:ROIMode"
        self._cover_status_pv   = f"{prefix}{cover_token}Pos-Sts"
        self._cover_open_pv     = f"{prefix}{cover_token}Cmd:Opn-Cmd"
        # Photon energy: FMX only; suffix already includes the eig_token
        self._photon_energy_pv     = f"{prefix}{photon_energy_suffix}"
        self._photon_energy_rbv_pv = f"{prefix}{photon_energy_rbv_suffix}"
        super().__init__(prefix, *args, **kwargs)
