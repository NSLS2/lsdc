import logging
import typing

from qtpy import QtWidgets
from qtpy.QtWidgets import QGroupBox

import daq_utils
import db_lib

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()


class DataLocInfo(QGroupBox):  # type: ignore[misc]
    def __init__(self, parent: "ControlMain"):
        QtWidgets.QGroupBox.__init__(self, parent)
        self.parent = parent
        self.setTitle("Data Location")
        self.vBoxDPathParams1 = QtWidgets.QVBoxLayout()
        self.hBoxDPathParams1 = QtWidgets.QHBoxLayout()
        self.basePathLabel = QtWidgets.QLabel("Base Path:")
        self.base_path_ledit = QtWidgets.QLabel()
        self.base_path_ledit.setText(daq_utils.getBlConfig("visitDirectory"))
        # self.base_path_ledit.textChanged[str].connect(self.basePathTextChanged)
        self.browseBasePathButton = QtWidgets.QPushButton("Browse...")
        self.browseBasePathButton.setEnabled(False)
        # self.browseBasePathButton.clicked.connect(self.parent.popBaseDirectoryDialogCB)
        self.hBoxDPathParams1.addWidget(self.basePathLabel)
        self.hBoxDPathParams1.addWidget(self.base_path_ledit)
        self.hBoxDPathParams1.addWidget(self.browseBasePathButton)
        self._file_prefix = ""
        self._file_numstart = "1"
        self.hBoxDPathParams3 = QtWidgets.QHBoxLayout()
        self.dataPathLabel = QtWidgets.QLabel("Data Path:")
        self.dataPath_ledit = QtWidgets.QLineEdit()
        self.dataPath_ledit.setFrame(False)
        self.dataPath_ledit.setReadOnly(True)
        self.hBoxDPathParams3.addWidget(self.dataPathLabel)
        self.hBoxDPathParams3.addWidget(self.dataPath_ledit)
        self.vBoxDPathParams1.addLayout(self.hBoxDPathParams1)
        self.vBoxDPathParams1.addLayout(self.hBoxDPathParams3)
        self.setLayout(self.vBoxDPathParams1)

    def basePathTextChanged(self, text):
        prefix = self.getFilePrefix()
        self.setDataPath_ledit(
            text + "/" + str(daq_utils.getVisitName()) + "/" + prefix + "/#/"
        )

    def prefixTextChanged(self, text):
        self._file_prefix = str(text)
        prefix = self.getFilePrefix()
        try:
            runNum = db_lib.getSampleRequestCount(self.parent.selectedSampleID)
        except KeyError:
            logger.error("just setting a value of 1 for now")
            runNum = 1
        try:
            (
                puckPosition,
                samplePositionInContainer,
                containerID,
            ) = db_lib.getCoordsfromSampleID(
                daq_utils.beamline, self.parent.selectedSampleID
            )
        except IndexError:
            logger.error("IndexError returning")
            return
        self.setDataPath_ledit(
            self.base_path_ledit.text()
            + "/"
            + str(daq_utils.getVisitName())
            + "/"
            + prefix
            + "/"
            + str(runNum + 1)
            + "/"
            + db_lib.getContainerNameByID(containerID)
            + "_"
            + str(samplePositionInContainer + 1)
            + "/"
        )

    def setFileNumstart_ledit(self, s):
        self._file_numstart = str(s)

    def setFilePrefix_ledit(self, s):
        self.prefixTextChanged(str(s))

    def setBasePath_ledit(self, s):
        self.base_path_ledit.setText(s)

    def setDataPath_ledit(self, s):
        self.dataPath_ledit.setText(s)

    def getFileNumstart(self):
        return self._file_numstart

    def getFilePrefix(self):
        return self._file_prefix
