"""
The GUI for the LSDC system
"""
import sys
import threading
import time
import traceback
from qtpy import QtCore, QtWidgets
import daq_utils
from utils.healthcheck import perform_checks
import logging
import platform
from logging import handlers
from gui.control_main import ControlMain


class HostnameFilter(logging.Filter):
    hostname = platform.node().split(".")[0]

    def filter(self, record):
        record.hostname = HostnameFilter.hostname
        return True


logging_file = "lsdcGuiLog.txt"
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


class UiStallMonitor:
    def __init__(
        self,
        app,
        logger,
        heartbeat_ms=100,
        stall_threshold_s=2.0,
        check_interval_s=0.5,
    ):
        self.app = app
        self.logger = logger
        self.heartbeat_ms = heartbeat_ms
        self.stall_threshold_s = stall_threshold_s
        self.check_interval_s = check_interval_s
        self._last_tick = time.monotonic()
        self._stall_active = False
        self._stall_started = 0.0
        self._request_process_events = False
        self._running = False
        self._watchdog_thread = None
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._on_ui_heartbeat)

    def start(self):
        self._running = True
        self._timer.start(self.heartbeat_ms)
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="ui-stall-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()
        self.logger.info(
            "UI_STALL_MONITOR_STARTED heartbeat_ms=%s threshold_s=%.2f check_interval_s=%.2f",
            self.heartbeat_ms,
            self.stall_threshold_s,
            self.check_interval_s,
        )

    def stop(self):
        self._running = False
        if self._timer.isActive():
            self._timer.stop()
        if self._watchdog_thread is not None:
            self._watchdog_thread.join(timeout=1.0)
            self._watchdog_thread = None

    def _on_ui_heartbeat(self):
        self._last_tick = time.monotonic()
        if self._request_process_events:
            self._request_process_events = False
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 25)
            self.logger.warning("UI_STALL_PROCESS_EVENTS_CALLED")

    def _watchdog_loop(self):
        while self._running:
            time.sleep(self.check_interval_s)
            now = time.monotonic()
            age = now - self._last_tick
            if age >= self.stall_threshold_s:
                if not self._stall_active:
                    self._stall_active = True
                    self._stall_started = now
                    self._request_process_events = True
                    self.logger.warning(
                        "UI_STALL_START age_s=%.3f threshold_s=%.3f",
                        age,
                        self.stall_threshold_s,
                    )
                    self._dump_main_thread_stack()
            elif self._stall_active:
                self._stall_active = False
                self.logger.warning(
                    "UI_STALL_END duration_s=%.3f recovery_age_s=%.3f",
                    now - self._stall_started,
                    age,
                )

    def _dump_main_thread_stack(self):
        main_thread = threading.main_thread()
        main_ident = main_thread.ident
        frames = sys._current_frames()
        frame = frames.get(main_ident)
        if frame is None:
            self.logger.warning("UI_STALL_STACK_UNAVAILABLE")
            return
        stack_s = "".join(traceback.format_stack(frame))
        self.logger.warning("UI_STALL_STACK_BEGIN\n%sUI_STALL_STACK_END", stack_s)

def main():
    logger.info("Starting LSDC...")
    perform_checks()
    daq_utils.init_environment()
    daq_utils.readPVDesc()
    app = QtWidgets.QApplication(sys.argv)
    ui_stall_monitor = UiStallMonitor(app, logger)
    app.aboutToQuit.connect(ui_stall_monitor.stop)
    ui_stall_monitor.start()
    app.ui_stall_monitor = ui_stall_monitor
    ex = ControlMain()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Exception occured: {e}")
        print(traceback.format_exc())
