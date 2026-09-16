"""ClickCenter device — click-to-center goniometer alignment.

Covers all 11 ``{ClkCtr}`` descriptors from both DB files.

Instantiation::

    cc = ClickCenter("XF:17IDC-ES:FMX{ClkCtr}", name="click_center")  # FMX
    cc = ClickCenter("XF:17IDB-ES:AMX{ClkCtr}", name="click_center")  # AMX
"""

from ophyd import Component as Cpt, Device, EpicsSignal, EpicsSignalRO


class ClickCenter(Device):
    """Click-to-center alignment controller."""

    # --- image scale calibration ---
    image_x_scale_pix  = Cpt(EpicsSignal, "image_X_scale.B")   # image_X_scalePix
    image_x_scale_mm   = Cpt(EpicsSignal, "image_X_scale.C")   # image_X_scaleMM
    image_y_scale_pix  = Cpt(EpicsSignal, "image_Y_scale.B")   # image_Y_scalePix
    image_y_scale_mm   = Cpt(EpicsSignal, "image_Y_scale.C")   # image_Y_scaleMM

    # --- image center (pixels) ---
    image_x_center_pix = Cpt(EpicsSignal, "image_X_center.A")  # image_X_centerPix
    image_y_center_pix = Cpt(EpicsSignal, "image_Y_center.A")  # image_Y_centerPix

    # --- click target coordinates ---
    target_x           = Cpt(EpicsSignal, "image_X_target.A")  # C2C_TargetX
    target_y           = Cpt(EpicsSignal, "image_Y_target.A")  # C2C_TargetY
    omega              = Cpt(EpicsSignal, "OmegaPos.A")         # C2C_Omega

    # --- execution ---
    go                 = Cpt(EpicsSignal, "click_center.PROC")  # C2C_Go
    gonio_done         = Cpt(EpicsSignalRO, "gonioDone")        # gonioDone
