from qtpy.QtCore import QThread, Signal, QObject, QRunnable
from qtpy import QtGui
import os
import logging
import requests
from config_params import SERVER_CHECK_DELAY
import raddoseLib
from pathlib import Path
import cv2
import time
from summarytable.summarytable import DataDirectory, BaseName, FileObserver

logger = logging.getLogger()

# Sample-cam single-image (requests) fetch tuning.
CAM_CONNECT_TIMEOUT = 1.0    # seconds: TCP connect timeout
CAM_READ_TIMEOUT = 2.0       # seconds: between-bytes read-inactivity timeout
CAM_TOTAL_DEADLINE = 2.0     # seconds: hard wall-clock cap on the whole fetch
CAM_SLOW_WARN_MS = 1000.0    # ms: log a SLOW anomaly above this
CAM_ANOMALY_LOG_MIN_INTERVAL = 1.0  # seconds: rate-limit repeated anomaly logs


class VideoThread(QThread):
    frame_ready = Signal(object)

    def _log_anomaly(self, kind, url, elapsed_ms, err=None):
        # Rate-limited so a sustained stall does not flood the log, but each
        # anomaly window is still self-marked in the log for post-hoc grep.
        now = time.monotonic()
        if now - self._last_anomaly_log < CAM_ANOMALY_LOG_MIN_INTERVAL:
            return
        self._last_anomaly_log = now
        if err is None:
            logger.warning("%s url=%s elapsed_ms=%.0f", kind, url, elapsed_ms)
        else:
            logger.warning(
                "%s url=%s elapsed_ms=%.0f err=%s", kind, url, elapsed_ms, err
            )

    def _fetch_snapshot(self, url, t0):
        # Stream the body and enforce a hard wall-clock deadline so the worker
        # loop can never block indefinitely on a trickling / stalled IOC.
        resp = self._http_session.get(
            url,
            timeout=(CAM_CONNECT_TIMEOUT, CAM_READ_TIMEOUT),
            stream=True,
        )
        try:
            resp.raise_for_status()
            chunks = []
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    chunks.append(chunk)
                if time.monotonic() - t0 > CAM_TOTAL_DEADLINE:
                    raise TimeoutError(
                        f"total deadline {CAM_TOTAL_DEADLINE:.1f}s exceeded"
                    )
            return b"".join(chunks)
        finally:
            resp.close()

    def _make_capture(self, url):
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def camera_refresh(self):
        if self.url:
            url = self.url
            t0 = time.monotonic()
            try:
                content = self._fetch_snapshot(url, t0)
                elapsed_ms = (time.monotonic() - t0) * 1000
                qimage = QtGui.QImage()
                qimage.loadFromData(content)
                if self.width and self.height:
                    qimage = qimage.scaled(self.width, self.height)
                self.showing_error = False
                self.frame_ready.emit(qimage)
                if elapsed_ms > CAM_SLOW_WARN_MS:
                    self._log_anomaly("SAMPLE_CAM_SLOW", url, elapsed_ms)
            except Exception as e:
                elapsed_ms = (time.monotonic() - t0) * 1000
                # Always log anomalies (rate-limited) and keep emitting so the
                # feed recovers on its own once the IOC/stream resumes.
                self._log_anomaly("SAMPLE_CAM_TIMEOUT", url, elapsed_ms, err=e)
                if not self.showing_error:
                    logger.warning("CAM_FETCH_FAILED url=%s err=%s", self.url, e)
                    # self.frame_ready.emit(None)
                    self.showing_error = True
            self.msleep(int(max(0, self.delay - elapsed_ms)))
            return

        if self.video_capture:
            if self.new_mjpg_url != self.old_mjpg_url and self.new_mjpg_url is not None:
                try:
                    self.video_capture.release()
                finally:
                    self.video_capture = None
                self.video_capture = self._make_capture(self.new_mjpg_url)
                self.old_mjpg_url = self.new_mjpg_url 
            retval,self.currentFrame = self.video_capture.read()

            if self.currentFrame is None or not retval:
                if not self.showing_error:
                    logger.info("CAM_READ_FAILED url=%s retval=%s",
                                   self.new_mjpg_url, retval)
                    self.showing_error = True
                self.msleep(100)
                return
            # on a successful read, reset the flag:
            self.showing_error = False

            now = time.monotonic() * 1000
            if  now <= self.next_emit:
                return
            self.next_emit = now + self.delay

            height,width=self.currentFrame.shape[:2]
            qimage= QtGui.QImage(self.currentFrame,width,height,3*width,QtGui.QImage.Format_RGB888)
            qimage = qimage.copy()
            qimage = qimage.rgbSwapped()
            if self.width and self.height:
                qimage = qimage.scaledToHeight(self.height)

            
        if not self.showing_error:
            self.frame_ready.emit(qimage)
            
        
    def __init__(self, *args, delay=1000, url='', mjpg_url=None, width=None, height=None,**kwargs):
        self._retry_after = 0.0
        self.delay = delay
        self.width = width
        self.height = height
        self.url = url
        self.mjpg_url = mjpg_url
        self.old_mjpg_url = None
        self.new_mjpg_url = None
        self.video_capture = None
        if self.mjpg_url:
            self.video_capture = self._make_capture(self.mjpg_url)
            self.old_mjpg_url = self.mjpg_url
            self.new_mjpg_url = self.mjpg_url
            self.mjpg_url = None
        self.showing_error = False
        self._http_session = requests.Session()
        self._last_anomaly_log = 0.0
        self.is_running = True
        self.next_emit = time.monotonic() * 1000
        QThread.__init__(self, *args, **kwargs)
    
    def updateSnapshotUrl(self, url, delay=None):
        if delay is not None:
            self.delay = delay
        self.new_mjpg_url = None
        self.old_mjpg_url = None
        self.url = url

    def updateCam(self, url, delay=None):
        if delay is not None:
            self.delay = delay
        self.url = ''
        if self.video_capture is None:
            self.video_capture = self._make_capture(url)
            self.old_mjpg_url = url
            self.new_mjpg_url = url
        else:
            self.new_mjpg_url = url
        
    def run(self):
        while self.is_running:
            self.camera_refresh()

    
    def stop(self):
        self.is_running = False
        self.wait()
        self._http_session.close()


class RaddoseThread(QThread):
    lifetime = Signal(float)
    def __init__(self, *args, avg_dwd = 10, #Default of 10MGy 
                beamsizeV = 1.0, beamsizeH = 2.0,
                vectorL = 0.0,
                energy = 12.66,
                flux = -1.0,
                wedge = 180.0,
                verbose = False,
                dm_user = 1.0,
                beamsize_type = "S",
                **kwargs):
        self.avg_dwd = avg_dwd
        self.beamsizeV = beamsizeV
        self.beamsizeH = beamsizeH
        self.vectorL = vectorL
        self.energy = energy
        self.flux = flux
        self.wedge = wedge
        self.verbose = verbose
        self.dm_user = dm_user
        self.beamsize_type = beamsize_type
        QThread.__init__(self, *args, **kwargs)

    def run(self):
        lifetime_value = raddoseLib.fmx_expTime(
            self.avg_dwd, self.beamsizeV, self.beamsizeH, 
            self.vectorL, self.energy, self.flux, self.wedge, 
            self.verbose, dm_user=self.dm_user, beamsize_type=self.beamsize_type
        )
        self.lifetime.emit(lifetime_value)


class ServerCheckThread(QThread):
    visit_dir_changed = Signal()
    def __init__(self, *args, delay=SERVER_CHECK_DELAY, **kwargs):
        self.delay = delay
        self.is_running = True
        QThread.__init__(self, *args, **kwargs)

    def run(self):
        import db_lib
        beamline = os.environ["BEAMLINE_ID"]
        while self.is_running:
            if Path(db_lib.getBeamlineConfigParam(beamline, "visitDirectory")).resolve() != Path.cwd():
                message = "The server visit directory has changed, stopping!"
                logger.error(message)
                print(message)
                self.visit_dir_changed.emit()
                break
            self.msleep(self.delay)

    def stop(self):
        self.is_running = False
        self.wait()

class SignalObject(QObject):
    finished = Signal(object)

class DataFetchRunnable(QRunnable):
    def __init__(self, run_function, *args, **kwargs):
        """
        Initialize the runnable with a custom function.
        
        :param run_function: A callable to execute in the run() method.
        :param args: Positional arguments to pass to run_function.
        :param kwargs: Keyword arguments to pass to run_function.
        """
        super(DataFetchRunnable, self).__init__()
        self.run_function = run_function
        self.args = args
        self.kwargs = kwargs
        self.signal = SignalObject()

    def run(self):
        # Execute the provided function with its arguments.
        result = self.run_function(*self.args, **self.kwargs)
        # Emit the finished signal with the result.
        self.signal.finished.emit(result)


def run_summary_monitor(dir: str, basename:str , period=10, stop_evt=None):
    bn = BaseName(basename)
    d = DataDirectory(dir, bn)
    d.attach(FileObserver(bn))

    while True:
        if stop_evt and stop_evt.is_set():
            break
        d.check_directory()
        time.sleep(period)

