from qtpy.QtCore import QThread, QTimer, QEventLoop, Signal, QPoint, Qt, QObject
from qtpy import QtGui
from PIL import Image, ImageQt
import os
import sys
import urllib
from io import BytesIO
import logging
from config_params import SERVER_CHECK_DELAY
import raddoseLib
from pathlib import Path
import cv2
import time
import numpy as np
import requests

logger = logging.getLogger()


class VideoThread(QThread):
    frame_ready = Signal(object)
    def camera_refresh(self):
        pixmap_orig = QtGui.QPixmap(320, 180)
        if self.url:
            try:
                file = BytesIO(urllib.request.urlopen(self.url, timeout=self.delay/1000).read())
                img = Image.open(file)
                qimage = ImageQt.ImageQt(img)
                pixmap_orig = QtGui.QPixmap.fromImage(qimage)
                self.showing_error = False
            except Exception as e:
                if not self.showing_error:
                    painter = QtGui.QPainter(pixmap_orig)
                    painter.setPen(QtGui.QPen(Qt.white))
                    painter.drawText( QPoint(10, 10), "No image obtained from: " )
                    painter.drawText( QPoint(10, 30), f"{self.url}")
                    painter.end()
                    self.frame_ready.emit(pixmap_orig)
                    self.showing_error = True

        if self.video_capture:
            if self.new_mjpg_url != self.old_mjpg_url:
                self.video_capture.open(self.new_mjpg_url)
                self.old_mjpg_url = self.new_mjpg_url 
            retval,self.currentFrame = self.video_capture.read()

            if self.currentFrame is None:
                #logger.debug('no frame read from stream URL - ensure the URL does not end with newline and that the filename is correct')
                return

            height,width=self.currentFrame.shape[:2]
            qimage= QtGui.QImage(self.currentFrame,width,height,3*width,QtGui.QImage.Format_RGB888)
            qimage = qimage.rgbSwapped()
            pixmap_orig = QtGui.QPixmap.fromImage(qimage)
            if self.width and self.height:
                pixmap_orig = pixmap_orig.scaled(self.width, self.height)

            
        if not self.showing_error:
            self.frame_ready.emit(pixmap_orig)
            
        
    def __init__(self, *args, delay=1000, url='', mjpg_url=None, width=None, height=None,**kwargs):
        self.delay = delay
        self.width = width
        self.height = height
        self.url = url
        self.mjpg_url = mjpg_url
        self.old_mjpg_url = None
        self.new_mjpg_url = None
        self.video_capture = None
        if self.mjpg_url and self.mjpg_url.lower().endswith(".mjpg"):
            self.video_capture = cv2.VideoCapture(self.mjpg_url)
            self.old_mjpg_url = self.mjpg_url
            self.new_mjpg_url = self.mjpg_url
            self.mjpg_url = None
        self.showing_error = False
        self.is_running = True
        QThread.__init__(self, *args, **kwargs)
    
    def updateCam(self, url):
        if url.lower().endswith(".mjpg"):
            self.new_mjpg_url = url
        
    def run(self):
        while self.is_running:
            self.camera_refresh()
            self.msleep(self.delay)

    
    def stop(self):
        self.is_running = False
        self.wait()


class RaddoseThread(QThread):
    lifetime = Signal(float)
    def __init__(self, *args, avg_dwd = 10, #Default of 10MGy 
                beamsizeV = 1.0, beamsizeH = 2.0,
                vectorL = 0.0,
                energy = 12.66,
                flux = -1.0,
                wedge = 180.0,
                verbose = False, **kwargs):
        self.avg_dwd = avg_dwd
        self.beamsizeV = beamsizeV
        self.beamsizeH = beamsizeH
        self.vectorL = vectorL
        self.energy = energy
        self.flux = flux
        self.wedge = wedge
        self.verbose = verbose
        QThread.__init__(self, *args, **kwargs)

    def run(self):
        lifetime_value = raddoseLib.fmx_expTime(self.avg_dwd, self.beamsizeV, self.beamsizeH, self.vectorL, self.energy, self.flux, self.wedge, self.verbose)
        self.lifetime.emit(lifetime_value)


class ServerCheckThread(QThread):
    visit_dir_changed = Signal()
    def __init__(self, *args, delay=SERVER_CHECK_DELAY, **kwargs):
        self.delay = delay
        QThread.__init__(self, *args, **kwargs)

    def run(self):
        import db_lib
        beamline = os.environ["BEAMLINE_ID"]
        while True:
            if Path(db_lib.getBeamlineConfigParam(beamline, "visitDirectory")).resolve() != Path.cwd():
                message = "The server visit directory has changed, stopping!"
                logger.error(message)
                print(message)
                self.visit_dir_changed.emit()
                break
            self.msleep(self.delay)
