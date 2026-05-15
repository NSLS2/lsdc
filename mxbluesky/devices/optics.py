"""Optics device — DCM energy/wavelength motors, sample flux.

All signals share the ``A-OP:FMX`` / ``A-OP:AMX`` prefix.

Slit motors (slit1_x_gap, slit1_y_gap) are FMX-only; they will be
disconnected on AMX.

The ``flux`` PV differs between beamlines (see BeamlineDevices) and is
NOT included here.  Access it as ``bl.flux`` on the top-level container.

``sample_lifetime`` (AMX-only) is similarly handled at the container level.

Instantiation::

    optics = Optics("XF:17IDA-OP:FMX", name="optics")   # FMX
    optics = Optics("XF:17IDA-OP:AMX", name="optics")   # AMX
"""

from ophyd import Component as Cpt, Device, EpicsMotor, EpicsSignalRO


class Optics(Device):
    """DCM energy/wavelength motors and beam flux readbacks."""

    # --- monochromator motors (both beamlines) ---
    wavelength  = Cpt(EpicsMotor,    "{Mono:DCM-Ax:W}Mtr")    # wavelength
    energy      = Cpt(EpicsMotor,    "{Mono:DCM-Ax:E}Mtr")    # energy

    # --- flux readbacks (both beamlines via DCM-dflux-MA) ---
    sample_flux = Cpt(EpicsSignalRO, "{Mono:DCM-dflux-MA}")   # sampleFlux

    # --- FMX-only: slits ---
    slit1_x_gap = Cpt(EpicsMotor,    "{Slt:1-Ax:XGap}Mtr")   # slit1XGap (FMX only)
    slit1_y_gap = Cpt(EpicsMotor,    "{Slt:1-Ax:YGap}Mtr")   # slit1YGap (FMX only)
