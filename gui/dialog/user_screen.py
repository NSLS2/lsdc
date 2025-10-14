import logging
import typing

from qt_epics.QtEpicsPVLabel import QtEpicsPVLabel
from qtpy import QtCore, QtWidgets
from qtpy.QtWidgets import QCheckBox
from config_params import ON_MOUNT_OPTION
import daq_utils

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()


class UserScreenDialog(QtWidgets.QFrame):
    def __init__(self, parent: "ControlMain"):
        self.parent = parent
        QtWidgets.QFrame.__init__(self)
        self.setWindowTitle("User Extras")
        vBoxColParams1 = QtWidgets.QVBoxLayout()
        hBoxColParams1 = QtWidgets.QHBoxLayout()
        hBoxColParams2 = QtWidgets.QHBoxLayout()
        hBoxColParams25 = QtWidgets.QHBoxLayout()
        hBoxColParams3 = QtWidgets.QHBoxLayout()
        govLabel = QtWidgets.QLabel("Set Governor State:")
        self.SEbutton = QtWidgets.QPushButton("SE")
        self.SEbutton.clicked.connect(self.SEgovCB)
        self.SAbutton = QtWidgets.QPushButton("SA")
        self.SAbutton.clicked.connect(self.SAgovCB)
        self.DAbutton = QtWidgets.QPushButton("DA")
        self.DAbutton.clicked.connect(self.DAgovCB)
        self.BLbutton = QtWidgets.QPushButton("BL")
        self.BLbutton.clicked.connect(self.BLgovCB)
        hBoxColParams1.addWidget(govLabel)
        hBoxColParams1.addWidget(self.SEbutton)
        hBoxColParams1.addWidget(self.SAbutton)
        hBoxColParams1.addWidget(self.DAbutton)
        hBoxColParams1.addWidget(self.BLbutton)
        govLabel2 = QtWidgets.QLabel("Current Governor State:")
        self.governorMessage = QtEpicsPVLabel(
            daq_utils.pvLookupDict["governorMessage"],
            self,
            140,
            highlight_on_change=False,
        )
        hBoxColParams2.addWidget(govLabel2)
        hBoxColParams2.addWidget(self.governorMessage.getEntry())

        self.openShutterButton = QtWidgets.QPushButton("Open Photon Shutter")
        self.openShutterButton.clicked.connect(self.parent.openPhotonShutterCB)
        hBoxColParams25.addWidget(self.openShutterButton)
        robotGB = QtWidgets.QGroupBox()
        robotGB.setTitle("Robot")

        self.unmountWarmButton = QtWidgets.QPushButton("Unmount Warm")
        self.unmountWarmButton.clicked.connect(self.unmountWarmCB)
        self.testRobotButton = QtWidgets.QPushButton("Test Robot")
        self.testRobotButton.clicked.connect(self.testRobotCB)
        self.recoverRobotButton = QtWidgets.QPushButton("Recover Robot")
        self.recoverRobotButton.clicked.connect(self.recoverRobotCB)
        self.dryGripperButton = QtWidgets.QPushButton("Dry Gripper")
        self.dryGripperButton.clicked.connect(self.dryGripperCB)

        self.queueCollectOnCheckBox = QCheckBox("Queue Collect")
        hBoxColParams3.addWidget(self.queueCollectOnCheckBox)
        self.checkQueueCollect()
        self.queueCollectOnCheckBox.stateChanged.connect(self.queueCollectOnCheckCB)

        hBoxColParams3.addWidget(self.unmountWarmButton)
        hBoxColParams3.addWidget(self.testRobotButton)
        hBoxColParams3.addWidget(self.recoverRobotButton)
        hBoxColParams3.addWidget(self.dryGripperButton)

        hBoxRobotParamsRow2 = QtWidgets.QHBoxLayout()
        hBoxRobotParamsRow2.addWidget(QtWidgets.QLabel("After mount:"))
        self.mountOptionDropdown = QtWidgets.QComboBox()
        self.mountOptionDropdown.addItem("Do nothing", 0)
        self.mountOptionDropdown.addItem("Center sample", 1)
        self.mountOptionDropdown.addItem("Collect rasters", 2)
        self.mountOptionDropdown.currentIndexChanged.connect(self.onMountOptionChanged)
        self.mountOptionDropdown.setCurrentIndex(daq_utils.getBlConfig(ON_MOUNT_OPTION))
        hBoxRobotParamsRow2.addWidget(self.mountOptionDropdown)

        vBoxRobotParams = QtWidgets.QVBoxLayout()
        vBoxRobotParams.addLayout(hBoxColParams3)
        vBoxRobotParams.addLayout(hBoxRobotParamsRow2)
        robotGB.setLayout(vBoxRobotParams)

        zebraGB = QtWidgets.QGroupBox()
        detGB = QtWidgets.QGroupBox()
        zebraGB.setTitle("Zebra (Timing)")
        detGB.setTitle("Eiger Detector")
        hBoxDet1 = QtWidgets.QHBoxLayout()
        hBoxDet2 = QtWidgets.QHBoxLayout()
        vBoxDet1 = QtWidgets.QVBoxLayout()
        self.stopDetButton = QtWidgets.QPushButton("Stop")
        self.stopDetButton.clicked.connect(self.stopDetCB)
        self.rebootDetIocButton = QtWidgets.QPushButton("Reboot Det IOC")
        self.rebootDetIocButton.clicked.connect(self.rebootDetIocCB)
        detStatLabel = QtWidgets.QLabel("Detector Status:")
        self.detMessage_ledit = QtWidgets.QLabel()
        hBoxDet1.addWidget(self.stopDetButton)
        hBoxDet1.addWidget(self.rebootDetIocButton)
        hBoxDet2.addWidget(detStatLabel)
        hBoxDet2.addWidget(self.detMessage_ledit)

        beamGB = QtWidgets.QGroupBox()
        beamGB.setTitle("Beam")
        hBoxBeam1 = QtWidgets.QHBoxLayout()
        hBoxBeam2 = QtWidgets.QHBoxLayout()
        hBoxBeam3 = QtWidgets.QHBoxLayout()
        vBoxBeam = QtWidgets.QVBoxLayout()
        if daq_utils.beamline == "fmx":
            slit1XLabel = QtWidgets.QLabel("Slit 1 X Gap:")
            slit1XLabel.setAlignment(QtCore.Qt.AlignCenter)
            slit1XRBLabel = QtWidgets.QLabel("Readback:")
            self.slit1XRBVLabel = QtEpicsPVLabel(
                daq_utils.motor_dict["slit1XGap"] + ".RBV", self, 70
            )
            slit1XSPLabel = QtWidgets.QLabel("SetPoint:")
            self.slit1XMotor_ledit = QtWidgets.QLineEdit()
            self.slit1XMotor_ledit.returnPressed.connect(self.setSlit1XCB)
            self.slit1XMotor_ledit.setText(str(self.parent.slit1XGapSP_pv.get()))

            slit1YLabel = QtWidgets.QLabel("Slit 1 Y Gap:")
            slit1YLabel.setAlignment(QtCore.Qt.AlignCenter)
            slit1YRBLabel = QtWidgets.QLabel("Readback:")
            self.slit1YRBVLabel = QtEpicsPVLabel(
                daq_utils.motor_dict["slit1YGap"] + ".RBV", self, 70
            )
            slit1YSPLabel = QtWidgets.QLabel("SetPoint:")
            self.slit1YMotor_ledit = QtWidgets.QLineEdit()
            self.slit1YMotor_ledit.setText(str(self.parent.slit1YGapSP_pv.get()))
            self.slit1YMotor_ledit.returnPressed.connect(self.setSlit1YCB)

        sampleFluxLabelDesc = QtWidgets.QLabel("Sample Flux:")
        sampleFluxLabelDesc.setFixedWidth(80)
        self.sampleFluxLabel = QtWidgets.QLabel()
        self.sampleFluxLabel.setText("%E" % self.parent.sampleFluxPV.get())
        hBoxBeam3.addWidget(sampleFluxLabelDesc)
        hBoxBeam3.addWidget(self.sampleFluxLabel)

        if daq_utils.beamline == "fmx":
            hBoxBeam1.addWidget(slit1XLabel)
            hBoxBeam1.addWidget(slit1XRBLabel)
            hBoxBeam1.addWidget(self.slit1XRBVLabel.getEntry())
            hBoxBeam1.addWidget(slit1XSPLabel)
            hBoxBeam1.addWidget(self.slit1XMotor_ledit)
            hBoxBeam2.addWidget(slit1YLabel)
            hBoxBeam2.addWidget(slit1YRBLabel)
            hBoxBeam2.addWidget(self.slit1YRBVLabel.getEntry())
            hBoxBeam2.addWidget(slit1YSPLabel)
            hBoxBeam2.addWidget(self.slit1YMotor_ledit)
            vBoxBeam.addLayout(hBoxBeam1)
            vBoxBeam.addLayout(hBoxBeam2)
        vBoxBeam.addLayout(hBoxBeam3)
        beamGB.setLayout(vBoxBeam)

        vBoxDet1.addLayout(hBoxDet1)
        vBoxDet1.addLayout(hBoxDet2)
        detGB.setLayout(vBoxDet1)
        hBoxColParams4 = QtWidgets.QHBoxLayout()
        vBoxZebraParams4 = QtWidgets.QVBoxLayout()
        self.resetZebraButton = QtWidgets.QPushButton("Reset Zebra")
        self.resetZebraButton.clicked.connect(self.resetZebraCB)
        self.rebootZebraButton = QtWidgets.QPushButton("Reboot Zebra IOC")
        self.rebootZebraButton.clicked.connect(self.rebootZebraIOC_CB)
        hBoxColParams5 = QtWidgets.QHBoxLayout()
        self.zebraArmCheckBox = QCheckBox("Arm")
        self.zebraArmCheckBox.setEnabled(False)
        self.zebraPulseCheckBox = QCheckBox("Pulse")
        self.zebraPulseCheckBox.setEnabled(False)
        self.zebraDownloadCheckBox = QCheckBox("Downloading")
        self.zebraDownloadCheckBox.setEnabled(False)
        self.zebraSentTriggerCheckBox = QCheckBox("Trigger Sent")
        self.zebraSentTriggerCheckBox.setEnabled(False)
        self.zebraReturnedTriggerCheckBox = QCheckBox("Trigger Returned")
        self.zebraReturnedTriggerCheckBox.setEnabled(False)
        hBoxColParams4.addWidget(self.resetZebraButton)
        hBoxColParams4.addWidget(self.rebootZebraButton)
        hBoxColParams5.addWidget(self.zebraArmCheckBox)
        hBoxColParams5.addWidget(self.zebraPulseCheckBox)
        hBoxColParams5.addWidget(self.zebraDownloadCheckBox)
        hBoxColParams5.addWidget(self.zebraSentTriggerCheckBox)
        hBoxColParams5.addWidget(self.zebraReturnedTriggerCheckBox)
        vBoxZebraParams4.addLayout(hBoxColParams4)
        vBoxZebraParams4.addLayout(hBoxColParams5)
        zebraGB.setLayout(vBoxZebraParams4)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok, QtCore.Qt.Horizontal, self
        )
        self.buttons.buttons()[0].clicked.connect(self.userScreenOKCB)

        if daq_utils.beamline == "nyx":
            self.openShutterButton.setDisabled(True)
            self.unmountWarmButton.setDisabled(True)
            self.testRobotButton.setDisabled(True)
            self.recoverRobotButton.setDisabled(True)
            self.dryGripperButton.setDisabled(True)
            self.resetZebraButton.setDisabled(True)
            self.rebootZebraButton.setDisabled(True)
            self.stopDetButton.setDisabled(True)
            self.rebootDetIocButton.setDisabled(True)

        vBoxColParams1.addLayout(hBoxColParams1)
        vBoxColParams1.addLayout(hBoxColParams2)
        vBoxColParams1.addLayout(hBoxColParams25)
        vBoxColParams1.addWidget(robotGB)
        vBoxColParams1.addWidget(zebraGB)
        vBoxColParams1.addWidget(detGB)
        vBoxColParams1.addWidget(beamGB)

        vBoxColParams1.addWidget(self.buttons)
        self.setLayout(vBoxColParams1)
            
    def onMountOptionChanged(self, index):
        value = self.mountOptionDropdown.itemData(index)
        daq_utils.setBlConfig(ON_MOUNT_OPTION, value)

    def show(self):
        self.checkQueueCollect()
        super().show()

    def setSlit1XCB(self):
        self.parent.send_to_server("setSlit1X", [self.slit1XMotor_ledit.text()])

    def setSlit1YCB(self):
        self.parent.send_to_server("setSlit1Y", [self.slit1YMotor_ledit.text()])

    def unmountWarmCB(self):
        self.parent.send_to_server("unmountSample")

    def testRobotCB(self):
        self.parent.send_to_server("testRobot")

    def recoverRobotCB(self):
        self.parent.send_to_server("recoverRobot")

    def dryGripperCB(self):
        self.parent.send_to_server("dryGripper")

    def stopDetCB(self):
        logger.info("stopping detector")
        self.parent.stopDet_pv.put(0)

    def rebootDetIocCB(self):
        logger.info("rebooting detector IOC")
        self.parent.rebootDetIOC_pv.put(
            1
        )  # no differences visible, but zebra IOC reboot works, this doesn't!

    def resetZebraCB(self):
        logger.info("resetting zebra")
        self.parent.resetZebra_pv.put(1)

    def rebootZebraIOC_CB(self):
        logger.info("rebooting zebra IOC")
        self.parent.rebootZebraIOC_pv.put(1)

    def SEgovCB(self):
        self.parent.send_to_server("setGovState", ["SE"])

    def SAgovCB(self):
        self.parent.send_to_server("setGovState", ["SA"])

    def DAgovCB(self):
        self.parent.send_to_server("setGovState", ["DA"])

    def BLgovCB(self):
        self.parent.send_to_server("setGovState", ["BL"])

    def userScreenOKCB(self):
        self.hide()

    def screenDefaultsCancelCB(self):
        self.done(QtWidgets.QDialog.Rejected)

    def screenDefaultsOKCB(self):
        self.done(QtWidgets.QDialog.Accepted)

    def queueCollectOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            daq_utils.setBlConfig("queueCollect", 1)
            self.parent.queue_collect_status_widget.setText("Queue Collect: ON")
        else:
            daq_utils.setBlConfig("queueCollect", 0)
            self.parent.queue_collect_status_widget.setText("Queue Collect: OFF")
        self.parent.row_clicked(
            0
        )  # This is so that appropriate boxes are filled when toggling queue collect

    def checkQueueCollect(self):
        if daq_utils.getBlConfig("queueCollect") == 1:
            self.queueCollectOnCheckBox.setChecked(True)
        else:
            self.queueCollectOnCheckBox.setChecked(False)
