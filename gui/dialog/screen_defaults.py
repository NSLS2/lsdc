import logging
import typing

from qtpy import QtCore, QtGui, QtWidgets

import db_lib
from config_params import (
    RASTER_DOZOR_SPOT_LEVEL,
    RASTER_TUNE_HIGH_RES,
    RASTER_TUNE_ICE_RING_FLAG,
    RASTER_TUNE_ICE_RING_WIDTH,
    RASTER_TUNE_LOW_RES,
    RASTER_TUNE_RESO_FLAG,
    VALID_EXP_TIMES,
)
from daq_utils import beamline, getBlConfig, setBlConfig

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()


class ScreenDefaultsDialog(QtWidgets.QDialog):
    def __init__(self, parent: "ControlMain"):
        QtWidgets.QDialog.__init__(self, parent)
        self.parent = parent
        self.setModal(False)
        self.setWindowTitle("Raster Params")

        vBoxColParams1 = QtWidgets.QVBoxLayout()

        collectionGB = QtWidgets.QGroupBox()
        collectionGB.setTitle("Collection parameters")

        hBoxColParams2 = QtWidgets.QHBoxLayout()
        colRangeLabel = QtWidgets.QLabel("Oscillation Width:")
        colRangeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.osc_range_ledit = (
            QtWidgets.QLineEdit()
        )  # note, this is for rastering! same name used for data collections
        self.setGuiValues({"osc_range": getBlConfig("rasterDefaultWidth")})
        self.osc_range_ledit.returnPressed.connect(self.screenDefaultsOKCB)
        colExptimeLabel = QtWidgets.QLabel("ExposureTime:")
        colExptimeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.exp_time_ledit = QtWidgets.QLineEdit()
        self.setGuiValues({"exp_time": getBlConfig("rasterDefaultTime")})
        self.exp_time_ledit.returnPressed.connect(self.screenDefaultsOKCB)
        self.exp_time_ledit.setValidator(
            QtGui.QDoubleValidator(
                VALID_EXP_TIMES[beamline]["min"],
                VALID_EXP_TIMES[beamline]["max"],
                VALID_EXP_TIMES[beamline]["digits"],
            )
        )
        self.exp_time_ledit.textChanged.connect(self.checkEntryState)

        colTransLabel = QtWidgets.QLabel("Transmission (0.0-1.0):")
        colTransLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.trans_ledit = QtWidgets.QLineEdit()
        self.setGuiValues({"transmission": getBlConfig("rasterDefaultTrans")})
        self.trans_ledit.returnPressed.connect(self.screenDefaultsOKCB)
        hBoxColParams2.addWidget(colRangeLabel)
        hBoxColParams2.addWidget(self.osc_range_ledit)
        hBoxColParams2.addWidget(colExptimeLabel)
        hBoxColParams2.addWidget(self.exp_time_ledit)
        hBoxColParams2.addWidget(colTransLabel)
        hBoxColParams2.addWidget(self.trans_ledit)
        collectionGB.setLayout(hBoxColParams2)

        dozorGB = QtWidgets.QGroupBox()
        dozorGB.setTitle("Dozor Parameter")
        hBoxColParams2a = QtWidgets.QHBoxLayout()
        dozorSpotLevelLabel = QtWidgets.QLabel(
            "Dozor Spot Level\n(Applies immediately)"
        )
        self.dozorSpotLevel = QtWidgets.QComboBox()
        self.dozorSpotLevel.addItems(["5", "6", "7", "8"])
        self.dozorSpotLevel.currentIndexChanged.connect(self.dozorSpotLevelChangedCB)
        hBoxColParams2a.addWidget(dozorSpotLevelLabel)
        hBoxColParams2a.addWidget(self.dozorSpotLevel)
        dozorGB.setLayout(hBoxColParams2a)

        dialsGB = QtWidgets.QGroupBox()
        dialsGB.setTitle("Dials Parameters")
        vBoxDialsParams = QtWidgets.QVBoxLayout()
        hBoxColParams2b = QtWidgets.QHBoxLayout()
        colMinSpotLabel = QtWidgets.QLabel("Min Spot Size:")
        colMinSpotLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.minSpot_ledit = QtWidgets.QLineEdit()
        self.minSpot_ledit.setText(str(getBlConfig("rasterDefaultMinSpotSize")))
        self.minSpot_ledit.returnPressed.connect(self.screenDefaultsOKCB)
        hBoxColParams2b.addWidget(colMinSpotLabel)
        hBoxColParams2b.addWidget(self.minSpot_ledit)

        self.hBoxRasterLayout2 = QtWidgets.QHBoxLayout()
        rasterTuneLabel = QtWidgets.QLabel("Raster\nTuning")
        self.rasterResoCheckBox = QtWidgets.QCheckBox("Constrain Resolution")
        self.rasterResoCheckBox.stateChanged.connect(self.rasterResoCheckCB)
        rasterLowResLabel = QtWidgets.QLabel("LowRes:")
        self.rasterLowRes = QtWidgets.QLineEdit()
        self.rasterLowRes.setText(str(getBlConfig(RASTER_TUNE_LOW_RES)))
        self.rasterLowRes.returnPressed.connect(self.screenDefaultsOKCB)
        rasterHighResLabel = QtWidgets.QLabel("HighRes:")
        self.rasterHighRes = QtWidgets.QLineEdit()
        self.rasterHighRes.setText(str(getBlConfig(RASTER_TUNE_HIGH_RES)))
        self.rasterHighRes.returnPressed.connect(self.screenDefaultsOKCB)
        if getBlConfig(RASTER_TUNE_RESO_FLAG) == 1:
            resoFlag = True
        else:
            resoFlag = False
            self.rasterHighRes.setEnabled(False)
            self.rasterLowRes.setEnabled(False)
        self.rasterResoCheckBox.setChecked(resoFlag)
        self.rasterIceRingCheckBox = QtWidgets.QCheckBox("Ice Ring")
        self.rasterIceRingCheckBox.setChecked(False)
        self.rasterIceRingCheckBox.stateChanged.connect(self.rasterIceRingCheckCB)
        self.rasterIceRingWidth = QtWidgets.QLineEdit()
        self.rasterIceRingWidth.setText(str(getBlConfig(RASTER_TUNE_ICE_RING_WIDTH)))
        self.rasterIceRingWidth.returnPressed.connect(self.screenDefaultsOKCB)
        self.rasterIceRingWidth.setEnabled(False)
        if getBlConfig(RASTER_TUNE_ICE_RING_FLAG) == 1:
            iceRingFlag = True
        else:
            iceRingFlag = False
        self.rasterIceRingCheckBox.setChecked(iceRingFlag)
        self.hBoxRasterLayout2.addWidget(self.rasterResoCheckBox)
        self.hBoxRasterLayout2.addWidget(rasterLowResLabel)
        self.hBoxRasterLayout2.addWidget(self.rasterLowRes)
        self.hBoxRasterLayout2.addWidget(rasterHighResLabel)
        self.hBoxRasterLayout2.addWidget(self.rasterHighRes)
        self.hBoxRasterLayout2.addWidget(self.rasterIceRingCheckBox)
        self.hBoxRasterLayout2.addWidget(self.rasterIceRingWidth)

        self.hBoxRasterLayout3 = QtWidgets.QHBoxLayout()
        self.rasterThreshCheckBox = QtWidgets.QCheckBox("Tune Threshold")
        if getBlConfig("rasterThreshFlag") == 1:
            threshFlag = True
        else:
            threshFlag = False
        self.rasterThreshCheckBox.setChecked(threshFlag)
        self.rasterThreshCheckBox.stateChanged.connect(self.rasterThreshCheckCB)

        rasterThreshKernSizeLabel = QtWidgets.QLabel("KernelSize")
        self.rasterThreshKernSize = QtWidgets.QLineEdit()
        self.rasterThreshKernSize.setText(str(getBlConfig("rasterThreshKernSize")))
        self.rasterThreshKernSize.returnPressed.connect(self.screenDefaultsOKCB)
        rasterThreshSigBckLabel = QtWidgets.QLabel("SigmaBkrnd")
        self.rasterThreshSigBckrnd = QtWidgets.QLineEdit()
        self.rasterThreshSigBckrnd.setText(str(getBlConfig("rasterThreshSigBckrnd")))
        self.rasterThreshSigBckrnd.returnPressed.connect(self.screenDefaultsOKCB)
        rasterThreshSigStrongLabel = QtWidgets.QLabel("SigmaStrong")
        self.rasterThreshSigStrong = QtWidgets.QLineEdit()
        self.rasterThreshSigStrong.setText(str(getBlConfig("rasterThreshSigStrong")))
        self.rasterThreshSigStrong.returnPressed.connect(self.screenDefaultsOKCB)
        self.rasterThreshKernSize.setEnabled(threshFlag)
        self.rasterThreshSigBckrnd.setEnabled(threshFlag)
        self.rasterThreshSigStrong.setEnabled(threshFlag)
        self.hBoxRasterLayout3.addWidget(self.rasterThreshCheckBox)
        self.hBoxRasterLayout3.addWidget(rasterThreshKernSizeLabel)
        self.hBoxRasterLayout3.addWidget(self.rasterThreshKernSize)
        self.hBoxRasterLayout3.addWidget(rasterThreshSigBckLabel)
        self.hBoxRasterLayout3.addWidget(self.rasterThreshSigBckrnd)
        self.hBoxRasterLayout3.addWidget(rasterThreshSigStrongLabel)
        self.hBoxRasterLayout3.addWidget(self.rasterThreshSigStrong)

        vBoxDialsParams.addLayout(hBoxColParams2b)
        vBoxDialsParams.addLayout(self.hBoxRasterLayout2)
        vBoxDialsParams.addLayout(self.hBoxRasterLayout3)
        dialsGB.setLayout(vBoxDialsParams)

        reprocessRasterButton = QtWidgets.QPushButton("ReProcessRaster")
        reprocessRasterButton.clicked.connect(self.reprocessRasterRequestCB)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Apply | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.buttons.buttons()[1].clicked.connect(self.screenDefaultsOKCB)
        self.buttons.buttons()[0].clicked.connect(self.screenDefaultsCancelCB)
        vBoxColParams1.addWidget(collectionGB)
        vBoxColParams1.addWidget(dozorGB)
        vBoxColParams1.addWidget(dialsGB)
        # vBoxColParams1.addWidget(reprocessRasterButton)
        vBoxColParams1.addWidget(self.buttons)
        self.setLayout(vBoxColParams1)

    def setGuiValues(self, values):
        for item, value in values.items():
            logger.info("resetting %s to %s" % (item, value))
            if item == "osc_range":
                self.osc_range_ledit.setText("%.3f" % float(value))
            elif item == "exp_time":
                self.exp_time_ledit.setText("%.3f" % float(value))
            elif item == "transmission":
                self.trans_ledit.setText("%.3f" % float(value))
            else:
                logger.error("setGuiValues unknown item: %s value: %s" % (item, value))

    def reprocessRasterRequestCB(self):
        self.parent.eraseCB()
        try:
            reqID = self.parent.selectedSampleRequest["uid"]
            self.parent.drawPolyRaster(db_lib.getRequestByID(reqID))
            self.parent.send_to_server("reprocessRaster", [reqID])
        except:
            pass

    def screenDefaultsCancelCB(self):
        self.done(QtWidgets.QDialog.Rejected)

    def dozorSpotLevelChangedCB(self, i):
        setBlConfig(RASTER_DOZOR_SPOT_LEVEL, int(self.dozorSpotLevel.itemText(i)))

    def screenDefaultsOKCB(self):
        setBlConfig("rasterDefaultWidth", float(self.osc_range_ledit.text()))
        setBlConfig("rasterDefaultTime", float(self.exp_time_ledit.text()))
        setBlConfig("rasterDefaultTrans", float(self.trans_ledit.text()))
        setBlConfig("rasterDefaultMinSpotSize", float(self.minSpot_ledit.text()))
        setBlConfig(RASTER_TUNE_LOW_RES, float(self.rasterLowRes.text()))
        setBlConfig(RASTER_TUNE_HIGH_RES, float(self.rasterHighRes.text()))
        setBlConfig(RASTER_TUNE_ICE_RING_WIDTH, float(self.rasterIceRingWidth.text()))
        setBlConfig("rasterThreshKernSize", float(self.rasterThreshKernSize.text()))
        setBlConfig("rasterThreshSigBckrnd", float(self.rasterThreshSigBckrnd.text()))
        setBlConfig("rasterThreshSigStrong", float(self.rasterThreshSigStrong.text()))
        if self.rasterIceRingCheckBox.isChecked():
            setBlConfig(RASTER_TUNE_ICE_RING_FLAG, 1)
        else:
            setBlConfig(RASTER_TUNE_ICE_RING_FLAG, 0)
        if self.rasterResoCheckBox.isChecked():
            setBlConfig(RASTER_TUNE_RESO_FLAG, 1)
        else:
            setBlConfig(RASTER_TUNE_RESO_FLAG, 0)

    def rasterIceRingCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            self.rasterIceRingWidth.setEnabled(True)
        else:
            self.rasterIceRingWidth.setEnabled(False)

    def rasterResoCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig(RASTER_TUNE_RESO_FLAG, 1)
            self.rasterLowRes.setEnabled(True)
            self.rasterHighRes.setEnabled(True)
        else:
            setBlConfig(RASTER_TUNE_RESO_FLAG, 0)
            self.rasterLowRes.setEnabled(False)
            self.rasterHighRes.setEnabled(False)

    def rasterThreshCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("rasterThreshFlag", 1)
            self.rasterThreshKernSize.setEnabled(True)
            self.rasterThreshSigBckrnd.setEnabled(True)
            self.rasterThreshSigStrong.setEnabled(True)
        else:
            setBlConfig("rasterThreshFlag", 0)
            self.rasterThreshKernSize.setEnabled(False)
            self.rasterThreshSigBckrnd.setEnabled(False)
            self.rasterThreshSigStrong.setEnabled(False)

    # code below and its application from: https://snorfalorpagus.net/blog/2014/08/09/validating-user-input-in-pyqt4-using-qvalidator/
    def checkEntryState(self, *args, **kwargs):
        sender = self.sender()
        validator = sender.validator()
        state = validator.validate(sender.text(), 0)[0]
        if state == QtGui.QValidator.Intermediate:
            color = "#fff79a"  # yellow
        elif state == QtGui.QValidator.Invalid:
            color = "#f6989d"  # red
        else:
            color = "#ffffff"  # white
        sender.setStyleSheet("QLineEdit { background-color: %s }" % color)
