from time import sleep
import h5py
from pathlib import Path
import json
import time
import threading
import numpy
import requests, json
import logging
from logging import handlers
from epics import PV
from enum import Enum
import platform
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import os

try:
    import dectris.albula
except ImportError as e:
    print("albula library import error: %s" % e)


class HostnameFilter(logging.Filter):
    hostname = platform.node().split(".")[0]

    def filter(self, record):
        record.hostname = HostnameFilter.hostname
        return True


logging_file = "albulaLog.txt"
logger = logging.getLogger()
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)
handler1 = handlers.RotatingFileHandler(logging_file, maxBytes=5000000, backupCount=100)
handler1.addFilter(HostnameFilter())
myformat = logging.Formatter(
    "%(asctime)s %(hostname)s: %(name)-8s %(levelname)-8s %(message)s"
)
handler1.setFormatter(myformat)
logger.addHandler(handler1)


class GovState(Enum):
    SA = "state SA"
    DA = "state DA"


class AlbulaController:
    def __init__(
        self,
    ):
        self.albulaFrame = None
        self.albulaSubFrame = None
        self.monitorSubFrame = None
        self.currentMasterH5 = None
        self.pause = 0.1

    def setup_monitor(self, ip, gov_message_pv_name):
        self.ip = ip
        self.api_version = os.environ.get("DCU_API_VERSION", "1.8.0")
        self.gov_message_pv = PV(
            gov_message_pv_name,
        )
        self.gov_message_pv.add_callback(self.handle_monitor)
        self._stop = threading.Event()
        self._stop.clear()
        self.startup()
        return json.dumps({"message": "monitor setup complete"})

    def handle_monitor(self, char_value, **kwargs):
        if char_value == GovState.DA.value:
            self._stop.clear()
            self.imageDaemon = threading.Thread(target=self.update_image, args=())
            if not self.imageDaemon.is_alive():
                self.imageDaemon.start()
        else:
            self._stop.set()

    def startup(self):
        if self.albulaFrame is None:
            logger.debug("starting up albula")
            self.albulaFrame = dectris.albula.openMainFrame()
            self.albulaFrame.disableClose()

        if self.albulaSubFrame is None:
            self.albulaSubFrame = self.albulaFrame.openSubFrame()
            self.set_current_monitor_image()
            self.albulaSubFrame.setContrast(15, 0)
            self.albulaSubFrame.setColorMode("Heat")

    def disp_image(self, dimage):
        self.startup()
        if not self.albulaSubFrame:
            self.albulaFrame = dectris.albula.openMainFrame()
            self.albulaSubFrame = self.albulaFrame.openSubFrame()
            self.albulaSubFrame.loadImage(dimage)
        self.albulaSubFrame.loadImage(dimage)

    def disp_file(self, filename, index=None):
        self.startup()
        try:
            if not (self.currentMasterH5 == filename) and self.albulaSubFrame:
                logger.info("reading file: %s" % filename)
                self.albulaSubFrame.loadFile(filename)
                self.currentMasterH5 = filename
                # Sleep to allow Albula to load file. Otherwise the following goTo() is ignored
                sleep(0.5)
            if index is not None and self.albulaSubFrame:
                logger.debug("reading image number %s" % filename[1])
                self.albulaSubFrame.goTo(index)
            return json.dumps({"message": f"Loaded file {filename}"})
        except Exception as e:
            logger.error(f"Albula exception: {e}")
            return json.dumps(
                {"message": f"Could not load file {filename} of type {type(filename)}"}
            )

    def run(self):
        """
        Run an endless loop, stopped by keyboard interrupt or exception
        """

        while not self._stop.is_set():
            try:
                self.albulaFrame.enableClose()  # check if main frame is alive
                time.sleep(self.pause)
            except KeyboardInterrupt:
                logging.info("Monitor stopped")
                self._stop.set()
            except Exception as e:
                logging.error("Monitor closed")
                logging.error("main exception: {}".format(e))
                self._stop.set()

    def update_image(self):
        """
        Endless loop polling for monitor images
        """
        logging.info("polling {} for monitor image".format(self.ip))
        while not self._stop.is_set():  # stop flag
            try:
                self.set_current_monitor_image()
                self.albulaSubFrame.setTitle("MONITOR")
            except Exception as e:
                logging.error("updateImage exception: {}".format(e))
                time.sleep(self.pause)
        self.albulaSubFrame.unsetTitle()

    def set_current_monitor_image(self):
        data = self.get_eiger_monitor_image()
        dimage = dectris.albula.DImage(data)
        self.albulaSubFrame.loadImage(dimage)

    def get_eiger_monitor_image(self):  # for EIGER1
        try:
            urlData = "http://{}/monitor/api/{}/images/monitor".format(
                self.ip, self.api_version
            )
            replyData = requests.get(urlData)
            img_bytes = BytesIO(replyData.content)
            img = Image.open(img_bytes)
            array = numpy.array(img)
            array[array == 65535] = 0
        except UnidentifiedImageError:
            logger.error("Could not get image from EIGER")
            array = numpy.zeros((3110, 3269))

        return array


albulaController = AlbulaController()
