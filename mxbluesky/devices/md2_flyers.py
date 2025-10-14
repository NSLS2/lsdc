import logging
import os
from collections import deque
import getpass
import grp
from ophyd.sim import NullStatus
from ophyd.status import SubscriptionStatus
from ophyd.utils import WaitTimeoutError

logger = logging.getLogger(__name__)

DEFAULT_DATUM_DICT = {"data": None, "omega": None}

INTERNAL_SERIES = 0
INTERNAL_ENABLE = 1
EXTERNAL_SERIES = 2
EXTERNAL_ENABLE = 3

class MD2StandardFlyer():
    def __init__(self, md2, detector=None) -> None:
        self.name = "MD2StandardFlyer"
        self.detector = detector
        self.md2 = md2
        self.collection_params = {}

        self._asset_docs_cache = deque()
        self._resource_uids = []
        self._datum_counter = None
        self._datum_ids = DEFAULT_DATUM_DICT
        self._master_file = None
        self._master_metadata = []

        self._collection_dictionary = None

    def kickoff(self):
        md2_msg = self.md2.standard_scan(num_images=self.collection_params["total_num_images"],
                               start_angle=self.collection_params["start_angle"],
                               scan_range=self.collection_params["scan_range"],
                               exposure_time=self.collection_params["exposure_time"])
        logger.info(f"md2 KICKOFF msg: {md2_msg}")
        return NullStatus()

    def update_parameters(self, total_num_images, start_angle, scan_range, exposure_time):
        self.collection_params = {
            "total_num_images": total_num_images,
            "start_angle": start_angle,
            "scan_range": scan_range,
            "exposure_time": exposure_time,
        }

    def configure_detector(self, file_prefix, data_directory_name):
        self.detector.file.external_name.put(file_prefix)
        self.detector.file.write_path_template = data_directory_name

    def detector_arm(self, angle_start, img_width, total_num_images, exposure_per_image, 
                     file_prefix, data_directory_name, file_number_start, x_beam, y_beam, 
                     wavelength, det_distance_m):
        self.detector.cam.save_files.put(1)
        self.detector.cam.sequence_id.put(file_number_start)
        self.detector.cam.det_distance.put(det_distance_m)
        self.detector.cam.file_owner.put(getpass.getuser())
        self.detector.cam.file_owner_grp.put(grp.getgrgid(os.getgid())[0])
        self.detector.cam.file_perms.put(420)
        file_prefix_minus_directory = str(file_prefix)
        file_prefix_minus_directory = file_prefix_minus_directory.split("/")[-1]
        self.detector.cam.acquire_time.put(exposure_per_image)
        self.detector.cam.acquire_period.put(exposure_per_image)
        self.detector.cam.num_triggers.put(1)
        self.detector.cam.num_images.put(total_num_images)
        self.detector.cam.trigger_mode.put(
            EXTERNAL_SERIES
        )  # must be external_enable to get the correct number of triggers and stop acquire
        self.detector.cam.file_path.put(data_directory_name)
        self.detector.cam.fw_name_pattern.put(f"{file_prefix_minus_directory}_$id")
        self.detector.cam.beam_center_x.put(x_beam)
        self.detector.cam.beam_center_y.put(y_beam)
        self.detector.cam.omega_incr.put(img_width)
        self.detector.cam.omega_start.put(angle_start)
        self.detector.cam.wavelength.put(wavelength)
        self.detector.file.file_write_images_per_file.put(500)

        #def armed_callback(value, old_value, **kwargs):
        #   if old_value == 0 and value == 1:
        #       return True
        #   return False

        #status = SubscriptionStatus(self.detector.cam.armed, armed_callback, run=False)
        #self.detector.cam.acquire.put(1)
        #yield status

    def complete(self):
        # monitor md2 status, wait for ready or timeout and then return
        #ready_status = self.md2.ready_status()
        
        #logger.info(f"TASK INFO[6]: {self.md2.task_info[6]}")
        #logger.info(f"TASK OUTPUT: {self.md2.task_output}")
        logger.debug(f"FLYER COMPLETE FUNCTION")
        task_status = self.md2.task_status()
        logger.debug(f"assigning task status")
        timeout = (self.collection_params["exposure_time"] * 3) + 80
        logger.info(f"TASK TIMEOUT: {timeout}")
        #ready_status.wait(timeout=timeout)
        try:
            task_status.wait(timeout=timeout)
        except WaitTimeoutError:
            logger.info("reached task timeout")
            logger.info(f"TASK INFO: {self.md2.task_info}")
            logger.info(f"TASK OUTPUT: {self.md2.task_output}")
            return
        return task_status

    def describe_collect(self):
        return {"stream_name": {}}
        #return {self.name: self._collection_dictionary}

    def collect(self):
        logger.debug("raster_flyer.collect(): going to unstage now")
        yield {"data": {}, "timestamps": {}, "time": 0, "seq_num": 0}
        #return self._collection_dictionary

    def unstage(self):
        logger.debug("flyer unstaging")
        self.collection_params = {}

    def read_configuration(self):
        return {}

    def describe_configuration(self):
        return {}

   # def collect_asset_docs(self):
   #     for _ in ():
   #         yield _

    def collect_asset_docs(self):
        asset_docs_cache = []

        # Get the Resource which was produced when the detector was staged.
        ((name, resource),) = self.detector.file.collect_asset_docs()

        asset_docs_cache.append(("resource", resource))
        self._datum_ids = DEFAULT_DATUM_DICT
        # Generate Datum documents from scratch here, because the detector was
        # triggered externally by the DeltaTau, never by ophyd.
        resource_uid = resource["uid"]
        # num_points = int(math.ceil(self.detector.cam.num_images.get() /
        #                 self.detector.cam.fw_num_images_per_file.get()))

        # We are currently generating only one datum document for all frames, that's why
        #   we use the 0th index below.
        #
        # Uncomment & update the line below if more datum documents are needed:
        # for i in range(num_points):

        seq_id = self.detector.cam.sequence_id.get()

        self._master_file = f"{resource['root']}/{resource['resource_path']}_{seq_id}_master.h5"
        if not os.path.isfile(self._master_file):
            raise RuntimeError(f"File {self._master_file} does not exist")

        # The pseudocode below is from Tom Caswell explaining the relationship between resource, datum, and events.
        #
        # resource = {
        #     "resource_id": "RES",
        #     "resource_kwargs": {},  # this goes to __init__
        #     "spec": "AD-EIGER-MX",
        #     ...: ...,
        # }
        # datum = {
        #     "datum_id": "a",
        #     "datum_kwargs": {"data_key": "data"},  # this goes to __call__
        #     "resource": "RES",
        #     ...: ...,
        # }
        # datum = {
        #     "datum_id": "b",
        #     "datum_kwargs": {"data_key": "omega"},
        #     "resource": "RES",
        #     ...: ...,
        # }

        # event = {...: ..., "data": {"detector_img": "a", "omega": "b"}}

        for data_key in self._datum_ids.keys():
            datum_id = f"{resource_uid}/{data_key}"
            self._datum_ids[data_key] = datum_id
            datum = {
                "resource": resource_uid,
                "datum_id": datum_id,
                "datum_kwargs": {"data_key": data_key},
            }
            asset_docs_cache.append(("datum", datum))
        return tuple(asset_docs_cache)

    def _extract_metadata(self, field="omega"):
        with h5py.File(self._master_file, "r") as hf:
            return hf.get(f"entry/sample/goniometer/{field}")[()]

class MD2VectorFlyer(MD2StandardFlyer):
    def __init__(self, md2, detector=None) -> None:
        super().__init__(md2, detector)
        self.name = "MD2VectorFlyer"

    def kickoff(self):
        # params used are start_angle, scan_range, exposure_time, start_y, start_z, stop_y, stop_z
        md2_msg = self.md2.vector_scan(start_angle=self.collection_params["start_angle"],
                             scan_range=self.collection_params["scan_range"],
                             exposure_time=self.collection_params["exposure_time"],
                             start_cx=self.collection_params["start_cx"],
                             start_cy=self.collection_params["start_cy"],
                             start_y=self.collection_params["start_y"],
                             start_z=self.collection_params["start_z"],
                             stop_cx=self.collection_params["stop_cx"],
                             stop_cy=self.collection_params["stop_cy"],
                             stop_y=self.collection_params["stop_y"],
                             stop_z=self.collection_params["stop_z"],)
        logger.info(f"md2 VEC KICKOFF msg: {md2_msg}")
        return NullStatus()
    
    def update_parameters(self, start_angle, scan_range, exposure_time, start_y, start_z, stop_y, stop_z, start_cx, start_cy, stop_cx, stop_cy):
        self.collection_params = {
            "start_angle": start_angle,
            "scan_range": scan_range,
            "exposure_time": exposure_time,
            "start_cx": start_cx,
            "start_cy": start_cy,
            "start_y": start_y,
            "start_z": start_z,
            "stop_cx": stop_cx,
            "stop_cy": stop_cy,
            "stop_y": stop_y,
            "stop_z": stop_z,
        }

class MD2RasterFlyer(MD2StandardFlyer):
        # List of scan parameters values, "/t" separated. The axes start values define the beginning
        # of the exposure, that is when all the axes have a steady speed and when the shutter/detector
        # are triggered.
        # The axes stop values are for the end of detector exposure and define the position at the
        # beginning of the deceleration.
        # Inputs names: "omega_range", "line_range", "total_uturn_range", "start_omega", "start_y",
        # "start_z", "start_cx", "start_cy", "number_of_lines", "frames_per_lines", "exposure_time",
        # "invert_direction", "use_centring_table", "use_fast_mesh_scans"

    def __init__(self, md2, detector=None) -> None:
        super().__init__(md2, detector)
        self.name = "MD2RasterFlyer"

    def kickoff(self):
        # params used are start_angle, scan_range, exposure_time, start_y, start_z, stop_y, stop_z
        md2_msg = self.md2.raster_scan(omega_range=self.collection_params["omega_range"],
                             line_range=self.collection_params["line_range"],
                             total_uturn_range=self.collection_params["total_uturn_range"],
                             start_omega=self.collection_params["start_omega"],
                             start_y=self.collection_params["start_y"],
                             start_z=self.collection_params["start_z"],
                             start_cx=self.collection_params["start_cx"],
                             start_cy=self.collection_params["start_cy"],
                             number_of_lines=self.collection_params["number_of_lines"],
                             frames_per_line=self.collection_params["frames_per_line"],
                             exposure_time=self.collection_params["exposure_time"],
                             invert_direction=self.collection_params["invert_direction"],
                             use_centring_table=self.collection_params["use_centring_table"],
                             use_fast_mesh_scans=self.collection_params["use_fast_mesh_scans"])
        logger.info(f"md2 RASTER KICKOFF msg: {md2_msg}")
        return NullStatus()
    
    def update_parameters(self, omega_range, line_range, total_uturn_range, start_omega, start_y, start_z, start_cx, start_cy, number_of_lines, frames_per_line, exposure_time, invert_direction, use_centring_table, use_fast_mesh_scans):
        self.collection_params = {
            "omega_range": omega_range,
            "line_range": line_range,
            "total_uturn_range": total_uturn_range,
            "start_omega": start_omega,
            "start_y": start_y,
            "start_z": start_z,
            "start_cx": start_cx,
            "start_cy": start_cy,
            "number_of_lines": number_of_lines,
            "frames_per_line": frames_per_line,
            "exposure_time": exposure_time,
            "invert_direction": invert_direction,
            "use_centring_table": use_centring_table,
            "use_fast_mesh_scans": use_fast_mesh_scans,
        }
