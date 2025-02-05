import logging
import typing

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

import daq_utils
import db_lib

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()

class ProcessPopup(QtWidgets.QMessageBox):
    def __init__(self, parent: "ControlMain",window_title = 'Info', main_text =  'Waiting for somethign in GUI, open more details for more info', detailed_text = 'waiting'):
        super(ProcessPopup, self).__init__(parent)
        self.setWindowTitle(window_title)
        self.setIcon(QtWidgets.QMessageBox.Question)
        self.setText(main_text)
        self.setDetailedText(detailed_text)

    

