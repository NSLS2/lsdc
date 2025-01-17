from ophyd import (DeviceStatus, Component as Cpt, Signal, EpicsSignal, Device)

from PIL import Image
import logging
import subprocess
import numpy
import urllib.request
from io import BytesIO
logger = logging.getLogger(__name__)


class URLCamera(Device):
    url = Cpt(Signal, value='http://10.67.147.26:3908/video_feed2')
    filename = Cpt(Signal, value='auto-center.jpg')
    delay = Cpt(Signal, value=1000)
    cam_mode = Cpt(Signal, value='auto-center')
    cam = Cpt(Signal, value=0) # placeholder signals
    cam.acquire = Cpt(Signal, value=0)
    reset_signal = Cpt(Signal, value=0)

    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs)

    def getImageFromURL(self):
        image_file = BytesIO(urllib.request.urlopen(self.url.get(), timeout=self.delay.get()/1000).read())
        sample_image = Image.open(image_file)
        numpy_image = numpy.asarray(sample_image)
        return numpy_image
    
    def trigger(self):
        self.image=self.getImageFromURL()
        try:
            Image.fromarray(self.image).save(self.filename.get())
        except IOError as e:
            logger.error(f"Failed to save image: {e}")
            raise
        status = DeviceStatus(self, timeout=10)
        status.set_finished()
        return status

    def getRasterBox(self): # not used, here for reference
        self.image=self.getImageFromURL()
        Image.fromarray(self.image).save('CurrentSample.jpg')
        result = subprocess.run(self.raster_box_subprocess_call, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if 'Connection refused' in result.stderr.decode():
            logger.warning(result.stderr.decode())
            return None
        result_dict = eval(result.stdout.decode())
        box = result_dict['pred_boxes'][0]['box']
        #returns box as x1,y1,x2,y2
        bottom_left = (box[0],box[1])
        top_right = (box[2], box[3])
        return bottom_left, top_right
