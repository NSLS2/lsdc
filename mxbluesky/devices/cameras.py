"""Camera devices — low-mag, high-mag, and top-view cameras.

Each class takes the full camera PV base as prefix.

FMX camera assignments:
  low-mag   → Cam:7   (XF:17IDC-ES:FMX{Cam:7})
  high-mag  → Cam:8   (XF:17IDC-ES:FMX{Cam:8})
  top-view  → Cam:11  (XF:17IDC-ES:FMX{Cam:11})

AMX camera assignments:
  low-mag   → Cam:6   (XF:17IDB-ES:AMX{Cam:6})
  high-mag  → Cam:7   (XF:17IDB-ES:AMX{Cam:7})
  top-view  → Cam:9   (XF:17IDB-ES:AMX{Cam:9})

The zoom ROI number differs between beamlines for LowMagCamera:
  FMX: zoom=ROI3, full=ROI2
  AMX: zoom=ROI1, full=ROI2
Pass zoom_roi=3 (FMX, default) or zoom_roi=1 (AMX) at instantiation.
HighMagCamera uses ROI1 (zoom) and ROI2 (full) on both beamlines.

Note on FormattedComponent (FCpt):
  FCpt produces the FULL PV string (device prefix is NOT auto-prepended).
  Full PV strings are therefore pre-computed in __init__ and stored as
  instance attributes so the FCpt template is a simple attribute lookup.
"""

from ophyd import Component as Cpt, FormattedComponent as FCpt, Device
from ophyd import EpicsSignal, EpicsSignalRO


class LowMagCamera(Device):
    """Low-magnification sample camera.

    Parameters
    ----------
    zoom_roi : int
        ROI plugin number used for the zoom (cropped) view.
        Default 3 (FMX).  Use 1 for AMX.
    """

    # --- acquisition ---
    acquire                = Cpt(EpicsSignal,   "cam1:Acquire")
    acquire_time           = Cpt(EpicsSignal,   "cam1:AcquireTime")
    gain                   = Cpt(EpicsSignal,   "cam1:Gain")
    image_mode             = Cpt(EpicsSignal,   "cam1:ImageMode")
    trigger_mode           = Cpt(EpicsSignal,   "cam1:TriggerMode")
    num_images             = Cpt(EpicsSignal,   "cam1:NumImages")
    det_state              = Cpt(EpicsSignalRO, "cam1:DetectorState_RBV")

    # --- JPEG writer ---
    jpeg_num_images        = Cpt(EpicsSignal,   "JPEG1:NumCapture")
    jpeg_file_number       = Cpt(EpicsSignal,   "JPEG1:FileNumber")
    jpeg_capture           = Cpt(EpicsSignal,   "JPEG1:Capture")
    jpeg_file_path         = Cpt(EpicsSignal,   "JPEG1:FilePath",   string=True)
    jpeg_file_name         = Cpt(EpicsSignal,   "JPEG1:FileName",   string=True)
    jpeg_enable_callbacks  = Cpt(EpicsSignal,   "JPEG1:EnableCallbacks")

    # --- MJPG stream frame rates ---
    zoom_frame_rate        = Cpt(EpicsSignalRO, "MJPG1:ArrayRate_RBV")  # zoom2FrameRate
    full_frame_rate        = Cpt(EpicsSignalRO, "MJPG2:ArrayRate_RBV")  # zoom1FrameRate

    # --- zoom ROI (full PV pre-computed in __init__; ROI3 FMX, ROI1 AMX) ---
    zoom_roi_min_x_rbv     = FCpt(EpicsSignalRO, "{self._zoom_roi_min_x_rbv}")
    zoom_roi_min_y_rbv     = FCpt(EpicsSignalRO, "{self._zoom_roi_min_y_rbv}")
    zoom_roi_min_x         = FCpt(EpicsSignal,   "{self._zoom_roi_min_x}")
    zoom_roi_min_y         = FCpt(EpicsSignal,   "{self._zoom_roi_min_y}")
    zoom_roi_size_x_rbv    = FCpt(EpicsSignalRO, "{self._zoom_roi_size_x_rbv}")
    zoom_roi_size_y_rbv    = FCpt(EpicsSignalRO, "{self._zoom_roi_size_y_rbv}")
    zoom_roi_max_size_x    = FCpt(EpicsSignalRO, "{self._zoom_roi_max_size_x}")
    zoom_roi_max_size_y    = FCpt(EpicsSignalRO, "{self._zoom_roi_max_size_y}")
    zoom_roi_array_size_x  = FCpt(EpicsSignalRO, "{self._zoom_roi_array_size_x}")
    zoom_roi_array_size_y  = FCpt(EpicsSignalRO, "{self._zoom_roi_array_size_y}")
    zoom_roi_bin_x         = FCpt(EpicsSignalRO, "{self._zoom_roi_bin_x}")
    zoom_roi_bin_y         = FCpt(EpicsSignalRO, "{self._zoom_roi_bin_y}")

    # --- full ROI (ROI2 on both beamlines — regular Cpt, no ROI ambiguity) ---
    full_roi_min_x         = Cpt(EpicsSignal,   "ROI2:MinX")
    full_roi_min_y         = Cpt(EpicsSignal,   "ROI2:MinY")
    full_roi_min_x_rbv     = Cpt(EpicsSignalRO, "ROI2:MinX_RBV")
    full_roi_min_y_rbv     = Cpt(EpicsSignalRO, "ROI2:MinY_RBV")
    full_roi_size_x_rbv    = Cpt(EpicsSignalRO, "ROI2:SizeX_RBV")
    full_roi_size_y_rbv    = Cpt(EpicsSignalRO, "ROI2:SizeY_RBV")
    full_roi_max_size_x    = Cpt(EpicsSignalRO, "ROI2:MaxSizeX_RBV")
    full_roi_max_size_y    = Cpt(EpicsSignalRO, "ROI2:MaxSizeY_RBV")
    full_roi_array_size_x  = Cpt(EpicsSignalRO, "ROI2:ArraySizeX_RBV")
    full_roi_array_size_y  = Cpt(EpicsSignalRO, "ROI2:ArraySizeY_RBV")
    full_roi_bin_x         = Cpt(EpicsSignalRO, "ROI2:BinX_RBV")
    full_roi_bin_y         = Cpt(EpicsSignalRO, "ROI2:BinY_RBV")

    def __init__(self, prefix, *args, zoom_roi=3, **kwargs):
        self._zoom_roi = zoom_roi
        r = f"ROI{zoom_roi}"
        # Pre-compute full PV strings so FCpt templates need only a simple attr lookup.
        # (FCpt produces the FULL PV — the device prefix is NOT auto-prepended.)
        self._zoom_roi_min_x_rbv    = f"{prefix}{r}:MinX_RBV"
        self._zoom_roi_min_y_rbv    = f"{prefix}{r}:MinY_RBV"
        self._zoom_roi_min_x        = f"{prefix}{r}:MinX"
        self._zoom_roi_min_y        = f"{prefix}{r}:MinY"
        self._zoom_roi_size_x_rbv   = f"{prefix}{r}:SizeX_RBV"
        self._zoom_roi_size_y_rbv   = f"{prefix}{r}:SizeY_RBV"
        self._zoom_roi_max_size_x   = f"{prefix}{r}:MaxSizeX_RBV"
        self._zoom_roi_max_size_y   = f"{prefix}{r}:MaxSizeY_RBV"
        self._zoom_roi_array_size_x = f"{prefix}{r}:ArraySizeX_RBV"
        self._zoom_roi_array_size_y = f"{prefix}{r}:ArraySizeY_RBV"
        self._zoom_roi_bin_x        = f"{prefix}{r}:BinX_RBV"
        self._zoom_roi_bin_y        = f"{prefix}{r}:BinY_RBV"
        super().__init__(prefix, *args, **kwargs)


class HighMagCamera(Device):
    """High-magnification sample camera.

    Both beamlines use ROI1 (zoom) and ROI2 (full).
    """

    # --- acquisition ---
    acquire               = Cpt(EpicsSignal,   "cam1:Acquire")
    acquire_time          = Cpt(EpicsSignal,   "cam1:AcquireTime")
    gain                  = Cpt(EpicsSignal,   "cam1:Gain")
    image_mode            = Cpt(EpicsSignal,   "cam1:ImageMode")
    trigger_mode          = Cpt(EpicsSignal,   "cam1:TriggerMode")
    num_images            = Cpt(EpicsSignal,   "cam1:NumImages")
    det_state             = Cpt(EpicsSignalRO, "cam1:DetectorState_RBV")

    # --- JPEG writer ---
    jpeg_num_images       = Cpt(EpicsSignal,   "JPEG1:NumCapture")
    jpeg_file_number      = Cpt(EpicsSignal,   "JPEG1:FileNumber")
    jpeg_capture          = Cpt(EpicsSignal,   "JPEG1:Capture")
    jpeg_file_path        = Cpt(EpicsSignal,   "JPEG1:FilePath",  string=True)
    jpeg_file_name        = Cpt(EpicsSignal,   "JPEG1:FileName",  string=True)
    jpeg_enable_callbacks = Cpt(EpicsSignal,   "JPEG1:EnableCallbacks")

    # --- MJPG stream frame rates ---
    zoom_frame_rate       = Cpt(EpicsSignalRO, "MJPG1:ArrayRate_RBV")  # zoom4FrameRate
    full_frame_rate       = Cpt(EpicsSignalRO, "MJPG2:ArrayRate_RBV")  # zoom3FrameRate

    # --- zoom ROI (ROI1 on both beamlines) ---
    zoom_roi_min_x_rbv    = Cpt(EpicsSignalRO, "ROI1:MinX_RBV")
    zoom_roi_min_y_rbv    = Cpt(EpicsSignalRO, "ROI1:MinY_RBV")
    zoom_roi_min_x        = Cpt(EpicsSignal,   "ROI1:MinX")
    zoom_roi_min_y        = Cpt(EpicsSignal,   "ROI1:MinY")
    zoom_roi_size_x_rbv   = Cpt(EpicsSignalRO, "ROI1:SizeX_RBV")
    zoom_roi_size_y_rbv   = Cpt(EpicsSignalRO, "ROI1:SizeY_RBV")
    zoom_roi_max_size_x   = Cpt(EpicsSignalRO, "ROI1:MaxSizeX_RBV")
    zoom_roi_max_size_y   = Cpt(EpicsSignalRO, "ROI1:MaxSizeY_RBV")
    zoom_roi_array_size_x = Cpt(EpicsSignalRO, "ROI1:ArraySizeX_RBV")
    zoom_roi_array_size_y = Cpt(EpicsSignalRO, "ROI1:ArraySizeY_RBV")
    zoom_roi_bin_x        = Cpt(EpicsSignalRO, "ROI1:BinX_RBV")
    zoom_roi_bin_y        = Cpt(EpicsSignalRO, "ROI1:BinY_RBV")

    # --- full ROI (ROI2 on both beamlines) ---
    full_roi_min_x        = Cpt(EpicsSignal,   "ROI2:MinX")
    full_roi_min_y        = Cpt(EpicsSignal,   "ROI2:MinY")
    full_roi_min_x_rbv    = Cpt(EpicsSignalRO, "ROI2:MinX_RBV")
    full_roi_min_y_rbv    = Cpt(EpicsSignalRO, "ROI2:MinY_RBV")
    full_roi_size_x_rbv   = Cpt(EpicsSignalRO, "ROI2:SizeX_RBV")
    full_roi_size_y_rbv   = Cpt(EpicsSignalRO, "ROI2:SizeY_RBV")
    full_roi_max_size_x   = Cpt(EpicsSignalRO, "ROI2:MaxSizeX_RBV")
    full_roi_max_size_y   = Cpt(EpicsSignalRO, "ROI2:MaxSizeY_RBV")
    full_roi_array_size_x = Cpt(EpicsSignalRO, "ROI2:ArraySizeX_RBV")
    full_roi_array_size_y = Cpt(EpicsSignalRO, "ROI2:ArraySizeY_RBV")
    full_roi_bin_x        = Cpt(EpicsSignalRO, "ROI2:BinX_RBV")
    full_roi_bin_y        = Cpt(EpicsSignalRO, "ROI2:BinY_RBV")


class TopViewCamera(Device):
    """Top-view (overhead) sample camera."""

    # --- acquisition ---
    acquire               = Cpt(EpicsSignal,   "cam1:Acquire")
    acquire_time          = Cpt(EpicsSignal,   "cam1:AcquireTime")
    data_type             = Cpt(EpicsSignal,   "cam1:DataType")
    gain                  = Cpt(EpicsSignal,   "cam1:Gain")
    image_mode            = Cpt(EpicsSignal,   "cam1:ImageMode")
    trigger_mode          = Cpt(EpicsSignal,   "cam1:TriggerMode")
    num_images            = Cpt(EpicsSignal,   "cam1:NumImages")
    det_state             = Cpt(EpicsSignalRO, "cam1:DetectorState_RBV")

    # --- JPEG writer ---
    jpeg_num_images       = Cpt(EpicsSignal,   "JPEG1:NumCapture")
    jpeg_file_number      = Cpt(EpicsSignal,   "JPEG1:FileNumber")
    jpeg_capture          = Cpt(EpicsSignal,   "JPEG1:Capture")
    jpeg_file_path        = Cpt(EpicsSignal,   "JPEG1:FilePath",  string=True)
    jpeg_file_name        = Cpt(EpicsSignal,   "JPEG1:FileName",  string=True)
    jpeg_enable_callbacks = Cpt(EpicsSignal,   "JPEG1:EnableCallbacks")
    jpeg_write_file       = Cpt(EpicsSignal,   "JPEG1:WriteFile")
