import grp
import os
from enum import Enum

# BlConfig parameter variable names

# rastering parameters
RASTER_TUNE_LOW_RES = "rasterTuneLowRes"
RASTER_TUNE_HIGH_RES = "rasterTuneHighRes"
RASTER_TUNE_ICE_RING_FLAG = "rasterTuneIceRingFlag"
RASTER_TUNE_RESO_FLAG = "rasterTuneResoFlag"
RASTER_TUNE_ICE_RING_WIDTH = "rasterTuneIceRingWidth"
RASTER_DOZOR_SPOT_LEVEL = "rasterDozorSpotLevel"
RASTER_NUM_CELLS_DELAY_THRESHOLD = "rasterNumCellsThresholdDelay"

# timing delays
ISPYB_RESULT_ENTRY_DELAY = "ispybResultEntryDelay"
RASTER_LONG_SNAPSHOT_DELAY = "rasterLongSnapshotDelay"
RASTER_SHORT_SNAPSHOT_DELAY = "rasterShortSnapshotDelay"
RASTER_POST_SNAPSHOT_DELAY = "rasterPostSnapshotDelay"
RASTER_GUI_XREC_FILL_DELAY = "rasterGuiXrecFillDelay"

# governor transition gain/exposure times
LOW_MAG_GAIN_DA = "lowMagGainDA"
LOW_MAG_GAIN = "lowMagGain"
LOW_MAG_EXP_TIME_DA = "lowMagExptimeDA"
LOW_MAG_EXP_TIME = "lowMagExptime"

# top view
TOP_VIEW_CHECK = "topViewCheck"

CRYOSTREAM_ONLINE = (
    "cryostream_online"  # consistent naming with hardware, such as robot_online
)

# constant values below
# GUI default configuration
BEAM_CHECK = "beamCheck"
UNMOUNT_COLD_CHECK = "unmountColdCheck"
ON_MOUNT_OPTION = "onMountOption"
SET_ENERGY_CHECK = "setEnergyCheck"


# raster request status updates
class RasterStatus(Enum):
    """The lsdc server can keep GUI clients updated on the status of
    of raster macros by updating raster request objects in the request
    database. The GUI can process raster data, e.g. filling heat maps,
    in parallel to the server moving motors and adjusting low mag cam.
    """

    NEW = 0
    DRAWN = 1
    READY_FOR_FILL = 2
    READY_FOR_SNAPSHOT = 3
    READY_FOR_REPROCESS = 4

class OnMountAvailOptions(Enum):
    """
    This enumerates the options available to the user on mounting a sample
    """
    DO_NOTHING = 0 # Only mounts sample
    CENTER_SAMPLE = 1 # Mounts and centers sample
    AUTO_RASTER = 2 # Mounts, centers and takes 2 orthogonal rasters

HUTCH_TIMER_DELAY = 500
SAMPLE_TIMER_DELAY = 40
SERVER_CHECK_DELAY = 2000

FAST_DP_MIN_NODES = 4
SPOT_MIN_NODES = 8
MOUNT_SUCCESSFUL = 1
MOUNT_FAILURE = 0
MOUNT_UNRECOVERABLE_ERROR = 2
MOUNT_STEP_SUCCESSFUL = 3

UNMOUNT_FAILURE = 0
UNMOUNT_SUCCESSFUL = 1
UNMOUNT_STEP_SUCCESSFUL = 2

PINS_PER_PUCK = 16

DETECTOR_OBJECT_TYPE_LSDC = "lsdc"  # using det_lib
DETECTOR_OBJECT_TYPE_NO_INIT = "no init" # skip epics detector init
DETECTOR_OBJECT_TYPE_OPHYD = "ophyd"  # instantiated in start_bs, using Bluesky scans
DETECTOR_OBJECT_TYPE = "detectorObjectType"

DETECTOR_SAFE_DISTANCE = {"fmx": 200.0, "amx": 180.0, "nyx": 200.0}
GOVERNOR_TIMEOUT = 120  # seconds for a governor move

DEWAR_SECTORS = {'amx':8, 'fmx':8, 'nyx':8}
PUCKS_PER_DEWAR_SECTOR = {'amx':3, 'fmx':3, 'nyx':3}

cryostreamTempPV = {"amx": "XF:17ID1:CS700:TEMP", "fmx": "XF:17ID2:CS700:TEMP", "nyx":"XF:19ID2:CS700:TEMP"}

VALID_EXP_TIMES = {
    "amx": {"min": 0.005, "max": 1, "digits": 3},
    "fmx": {"min": 0.01, "max": 10, "digits": 3},
    "nyx": {"min": 0.002, "max": 10, "digits": 4},
}
VALID_DET_DIST = {
    "amx": {"min": 100, "max": 500, "digits": 3},
    "fmx": {"min": 137, "max": 2000, "digits": 2},
    "nyx": {"min": 100, "max": 500, "digits": 3},
}
VALID_TOTAL_EXP_TIMES = {
    "amx": {"min": 0.005, "max": 300, "digits": 3},
    "fmx": {"min": 0.01, "max": 300, "digits": 3},
    "nyx": {"min": 0.01, "max": 1000, "digits": 3},
}
VALID_PREFIX_LENGTH = 25  # TODO centralize with spreadsheet validation?
VALID_PREFIX_NAME = "[0-9a-zA-Z-_]{0,%s}" % VALID_PREFIX_LENGTH
VALID_TRANSMISSION = {
    "amx": {"min": 0.001, "max": 1.0, "digits": 3},
    "fmx": {"min": 0.001, "max": 1.0, "digits": 3},
    "nyx": {"min": 0.001, "max": 0.999, "digits": 3},
}

MINIMUM_RASTER_SIZE = {"amx": 6, "fmx": 6, "nyx": 2}

LSDC_SERVICE_USERS = ("lsdc-amx", "lsdc-fmx", "lsdc-nyx")
IS_STAFF = (
    True
    if os.environ.get("STAFF_GROUP") is not None and os.environ["STAFF_GROUP"] in [grp.getgrgid(g).gr_name for g in os.getgroups()]
    else False
)

EMBL_SERVER_PV_BASE = {
    "amx": "XF:17IDB-ES:AMX{EMBL}",
    "fmx": "XF:17IDC-ES:FMX{EMBL}"
}

BEAMSIZE_OPTIONS = {
    "S": ["V0", "H0"],
    "L": ["V1", "H1"]
}


class MountState(Enum):
    CURRENTLY_MOUNTING = "cm"
    FAILED_MOUNTING = "fm"
    MOUNTED = "m"
    CURRENTLY_UNMOUNTING = "cu"
    FAILED_UNMOUNTING = "fu"

    @classmethod
    def get_text(cls, enum_value):
        text_values = {
            cls.CURRENTLY_MOUNTING: "\n(Currently Mounting)",
            cls.FAILED_MOUNTING: "\n(Failed Mounting)",
            cls.MOUNTED: "\n(Mounted)",
            cls.CURRENTLY_UNMOUNTING: "\n(Currently Unmounting)",
            cls.FAILED_UNMOUNTING: "\n(Failed Unmounting)"
        }
        return text_values.get(enum_value, "\n(Unknown State)")

OPHYD_COLLECTIONS = {"amx": False, "fmx": False, "nyx": True}

