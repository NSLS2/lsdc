"""
The GUI for the LSDC system
"""
import sys
from qtpy import QtWidgets
import daq_utils
from utils.healthcheck import perform_checks
import logging
import platform
import traceback
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

def main():
    logger.info("Starting LSDC...")
    perform_checks()
    daq_utils.init_environment()
    daq_utils.readPVDesc()
    app = QtWidgets.QApplication(sys.argv)
    ex = ControlMain()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Exception occured: {e}")
        print(traceback.format_exc())
