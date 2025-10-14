
from ophyd.areadetector.filestore_mixins import FileStorePluginBase
from ophyd.areadetector.plugins import JPEGPlugin, register_plugin, PluginBase
from ophyd import (DeviceStatus, Component as Cpt, Signal, EpicsSignal, Device, 
                    DDC_EpicsSignal, DDC_EpicsSignalRO, ADComponent as ADCpt, ImagePlugin,
                      ROIPlugin, TransformPlugin, StatsPlugin, ProcessPlugin, SingleTrigger, ProsilicaDetector)
from ophyd.utils.errors import WaitTimeoutError
from pathlib import Path
import requests
from bluesky.utils import FailedStatus
import daq_utils
import os


@register_plugin
class CVPlugin(PluginBase):
    _default_suffix = "CV1:"
    _suffix_re = "CV1\d:"
    _default_read_attrs = ["outputs"]
    func_sets = DDC_EpicsSignal(
        *[(f"func_set{k}", f"CompVisionFunction{k}") for k in range(1, 4)]
    )
    inputs = DDC_EpicsSignal(
        *[(f"input{k}", f"Input{k}") for k in range(1, 11)]
    )
    outputs = DDC_EpicsSignalRO(
        *[(f"output{k}", f"Output{k}_RBV") for k in range(1, 11)]
    )
    cam_depth = ADCpt(EpicsSignal, "CompVisionCamDepth", kind="config")


class StandardProsilica(SingleTrigger, ProsilicaDetector):
    image = Cpt(ImagePlugin, "image1:")
    roi1 = Cpt(ROIPlugin, "ROI1:")
    roi2 = Cpt(ROIPlugin, "ROI2:")
    roi3 = Cpt(ROIPlugin, "ROI3:")
    roi4 = Cpt(ROIPlugin, "ROI4:")
    trans1 = Cpt(TransformPlugin, "Trans1:")
    proc1 = Cpt(ProcessPlugin, "Proc1:")
    stats1 = Cpt(StatsPlugin, "Stats1:")
    stats2 = Cpt(StatsPlugin, "Stats2:")
    stats3 = Cpt(StatsPlugin, "Stats3:")
    stats4 = Cpt(StatsPlugin, "Stats4:")
    stats5 = Cpt(StatsPlugin, "Stats5:")

class FileStoreJPEG(FileStorePluginBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filestore_spec = "AD_JPEG"  # spec name stored in resource doc
        self.stage_sigs.update(
            [
                ("file_template", "%s%s_%6.6d.jpg"),
                ("file_write_mode", "Single"),
            ]
        )
        # 'Single' file_write_mode means one image : one file.
        # It does NOT mean that 'num_images' is ignored.

    def get_frames_per_point(self):
        return self.parent.cam.num_images.get()

    def stage(self):
        super().stage()
        # this over-rides the behavior is the base stage
        self._fn = self._fp

        resource_kwargs = {
            "template": self.file_template.get(),
            "filename": self.file_name.get(),
            "frame_per_point": self.get_frames_per_point(),
        }
        self._generate_resource(resource_kwargs)


class JPEGPluginWithFileStore(JPEGPlugin, FileStoreJPEG):
    pass


class LoopDetector(Device):
    """
    The loop detector device sends the low mag cam image to a specified REST API URL.
    The URL accepts an image file as a post request with the key "image" in the form
    data. It returns a JSON response that provides the predicted box as well as the 
    thresholded box based on x_start and x_end 
    """
    url = Cpt(
        Signal, value=f'{os.environ["SAMPLE_DETECT_URL"]}/predict', kind='config'
    )
    filename = Cpt(Signal, value=None)
    box = Cpt(Signal, value=[])
    thresholded_box = Cpt(Signal, value=[])
    x_start = Cpt(Signal, value=0)
    x_end = Cpt(Signal, value=0)
    get_threshold = Cpt(Signal, value=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_attrs = ['box', 'thresholded_box']

    def trigger(self):

        filename_dict = {"file": Path(self.filename.get()).open('rb')}
        post_data = None
        if self.get_threshold.get():
            post_data = {"x_start": self.x_start.get(), "x_end": self.x_end.get()}
        response = requests.post(self.url.get(), files=filename_dict, data=post_data)
        response.raise_for_status()
        json_response = response.json()
        if json_response['pred_boxes']:
            self.box.put(response.json()['pred_boxes'][0]['box'])
        else:
            self.box.put([])
        if "threshold" in json_response:
            self.thresholded_box.put(response.json()["threshold"])
        else:
            self.thresholded_box.put([])
        
        self.get_threshold.set(False)
        response_status = DeviceStatus(self.box, timeout=10)
        response_status.set_finished()

        return response_status


class TwoClickLowMag(StandardProsilica):
    cv1 = Cpt(CVPlugin, "CV1:")
    cam_mode = Cpt(Signal, value=None, kind="config")
    pix_per_um = Cpt(Signal, value=1, kind="config")
    x_min = Cpt(Signal, value=0, doc="min horizontal pixel", kind="config")
    x_max = Cpt(Signal, value=640, doc="max horizontal pixel", kind="config")

    jpeg = Cpt(
        JPEGPluginWithFileStore,
        "JPEG1:",
        write_path_template=f"/nsls2/data/{daq_utils.beamline}/legacy/topcam",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_attrs = ["cv1", "jpeg"]
        self.jpeg.read_attrs = ['full_file_name', 'file_write_mode', 'file_template']
        self.cv1.read_attrs = ["outputs"]
        self.cv1.outputs.read_attrs = ["output1", "output2", "output3"]
        self.cam_mode.subscribe(self._update_stage_sigs, event_type="value")

    def _update_stage_sigs(self, *args, **kwargs):
        self.stage_sigs.clear()
        self.stage_sigs.update(
            [
                ("cam.acquire", 0),
                ("cam.image_mode", 1),
                ("cam.acquire_time", 0.0022),
                ("cam.acquire_period", 1),
            ]
        )
        if self.cam_mode.get() == "centroid":
            self.stage_sigs.update(
                [
                    ("cv1.enable", 1),
                    ("cv1.func_sets.func_set2", "Centroid Identification"),
                    ("cv1.inputs.input1", 1),
                    ("cv1.inputs.input2", 5),
                    ("cv1.inputs.input3", 30),
                    ("cv1.inputs.input4", 3000000),
                    ("cv1.inputs.input5", 5000),
                ]
            )
        elif self.cam_mode.get() == "edge_detection":
            self.stage_sigs.update(
                [
                    ("cv1.enable", 1),
                    ("cv1.nd_array_port", "ROI4"),
                    ("cv1.func_sets.func_set1", "Canny Edge Detection"),
                    ("cv1.inputs.input1", 20),
                    ("cv1.inputs.input2", 8),
                    ("cv1.inputs.input3", 9),
                    ("cv1.inputs.input4", 5),
                    ("roi4.min_xyz.min_y", self.roi1.min_xyz.min_y.get()),
                    (
                        "roi4.min_xyz.min_x",
                        self.roi1.min_xyz.min_x.get() + 245,
                    ),
                    ("roi4.size.x", 240),
                    ("roi4.size.y", self.roi1.size.y.get()),
                ]
            )
        elif self.cam_mode.get() == "two_click":
            self.stage_sigs.update(
                [
                    ("jpeg.nd_array_port", "ROI2"),
                    ("cv1.nd_array_port", "ROI2"),
                    ("cv1.enable", 1),
                    ("cv1.func_sets.func_set1", "Threshold"),
                    ("cv1.func_sets.func_set2", "None"),
                    ("cv1.func_sets.func_set3", "None"),
                    ("cv1.inputs.input1", 1),
                    # x_min; update in plan
                    ("cv1.inputs.input2", self.x_min.get()),
                    # x_max; update in plan
                    ("cv1.inputs.input3", self.x_max.get()),
                    ("cv1.inputs.input4", 0),  # y_min
                    ("cv1.inputs.input5", 512)  # y_max
                ]
            )

    def stage(self, *args, **kwargs):
        self._update_stage_sigs(*args, **kwargs)
        super().stage(*args, **kwargs)

    def trigger(self):
        try:
            status = super().trigger()
            status.wait(6)
        except (AttributeError, WaitTimeoutError) as e:
            raise FailedStatus
        return status

