import logging
import typing
import daq_utils

from qtpy import QtCore, QtWidgets
from qtpy.QtWidgets import QCheckBox

from config_params import (
    BEAM_CHECK,
    SET_ENERGY_CHECK,
    TOP_VIEW_CHECK,
    UNMOUNT_COLD_CHECK,
)
from daq_utils import getBlConfig, setBlConfig
import daq_utils

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()


class StaffScreenDialog(QtWidgets.QFrame):
    def __init__(self, parent: "ControlMain", **kwargs):
        show = kwargs.get("show", True)
        self.parent = parent
        QtWidgets.QFrame.__init__(self)
        self.setWindowTitle("Staff Only")
        self.spotNodeCount = 8
        self.fastDPNodeCount = 4
        self.cpuCount = 28
        vBoxColParams1 = QtWidgets.QVBoxLayout()
        hBoxColParams0 = QtWidgets.QHBoxLayout()
        hBoxColParams1 = QtWidgets.QHBoxLayout()
        hBoxColParams2 = QtWidgets.QHBoxLayout()
        hBoxColParams3 = QtWidgets.QHBoxLayout()
        hBoxFastDP = QtWidgets.QHBoxLayout()
        hBoxSpotfinder = QtWidgets.QHBoxLayout()
        puckToDewarButton = QtWidgets.QPushButton("Puck to Dewar...")
        puckToDewarButton.clicked.connect(self.parent.puckToDewarCB)
        removePuckButton = QtWidgets.QPushButton("Remove Puck...")
        removePuckButton.clicked.connect(self.parent.removePuckCB)
        hBoxColParams0.addWidget(puckToDewarButton)
        hBoxColParams0.addWidget(removePuckButton)
        self.robotOnCheckBox = QCheckBox("Robot (On)")
        if getBlConfig("robot_online") == 1:
            self.robotOnCheckBox.setChecked(True)
        else:
            self.robotOnCheckBox.setChecked(False)
        self.robotOnCheckBox.stateChanged.connect(self.robotOnCheckCB)
        self.topViewCheckOnCheckBox = QCheckBox("TopViewCheck (On)")
        if getBlConfig(TOP_VIEW_CHECK) == 1:
            self.topViewCheckOnCheckBox.setChecked(True)
        else:
            self.topViewCheckOnCheckBox.setChecked(False)
        self.topViewCheckOnCheckBox.stateChanged.connect(self.topViewOnCheckCB)
        # BeamCheck check box
        self.beamCheckOnCheckBox = QCheckBox("BeamCheck (On)")
        if getBlConfig(BEAM_CHECK) == 1:
            self.beamCheckOnCheckBox.setChecked(True)
        else:
            self.beamCheckOnCheckBox.setChecked(False)
        self.beamCheckOnCheckBox.stateChanged.connect(self.beamCheckOnCheckCB)

        self.gripperUnmountColdCheckBox = QCheckBox("Unmount Cold")
        self.gripperUnmountColdCheckBox.stateChanged.connect(self.unmountColdCheckCB)
        if getBlConfig(UNMOUNT_COLD_CHECK) == 1:
            self.gripperUnmountColdCheckBox.setEnabled(True)
            self.gripperUnmountColdCheckBox.setChecked(True)
        else:
            self.gripperUnmountColdCheckBox.setEnabled(False)
            self.gripperUnmountColdCheckBox.setChecked(False)

        # Set energy checkbox
        if daq_utils.beamline == "fmx":
            self.set_energy_checkbox = QCheckBox("Set Energy")
            hBoxColParams1.addWidget(self.set_energy_checkbox)
            if getBlConfig(SET_ENERGY_CHECK) == 1:
                self.set_energy_checkbox.setChecked(True)
            else:
                self.set_energy_checkbox.setChecked(False)
            self.set_energy_checkbox.stateChanged.connect(self.set_energy_check_cb)


        self.queueCollectOnCheckBox = QCheckBox("Queue Collect")
        hBoxColParams1.addWidget(self.queueCollectOnCheckBox)
        self.checkQueueCollect()
        self.queueCollectOnCheckBox.stateChanged.connect(self.queueCollectOnCheckCB)
        self.vertRasterOnCheckBox = QCheckBox("Vert. Raster")
        hBoxColParams1.addWidget(self.vertRasterOnCheckBox)
        if getBlConfig("vertRasterOn") == 1:
            self.vertRasterOnCheckBox.setChecked(True)
        else:
            self.vertRasterOnCheckBox.setChecked(False)
        self.vertRasterOnCheckBox.stateChanged.connect(self.vertRasterOnCheckCB)
        self.procRasterOnCheckBox = QCheckBox("Process Raster")
        hBoxColParams1.addWidget(self.procRasterOnCheckBox)
        if getBlConfig("rasterProcessFlag") == 1:
            self.procRasterOnCheckBox.setChecked(True)
        else:
            self.procRasterOnCheckBox.setChecked(False)
        self.procRasterOnCheckBox.stateChanged.connect(self.procRasterOnCheckCB)
        self.guiRemoteOnCheckBox = QCheckBox("GUI Remote")
        hBoxColParams1.addWidget(self.guiRemoteOnCheckBox)
        if getBlConfig("omegaMonitorPV") == "VAL":
            self.guiRemoteOnCheckBox.setChecked(True)
        else:
            self.guiRemoteOnCheckBox.setChecked(False)
        self.guiRemoteOnCheckBox.stateChanged.connect(self.guiRemoteOnCheckCB)
        self.albulaDispCheckBox = QCheckBox("Display Data (Albula)")
        self.albulaDispCheckBox.setChecked(True)
        hBoxColParams1.addWidget(self.albulaDispCheckBox)

        self.enableMountCheckBox = QCheckBox("Enable Mount")
        if getBlConfig("mountEnabled") == 1:
            self.enableMountCheckBox.setChecked(True)
        else:
            self.enableMountCheckBox.setChecked(False)
        self.enableMountCheckBox.stateChanged.connect(self.enableMountCheckCB)
        self.unmountColdButton = QtWidgets.QPushButton("Unmount Cold")
        self.unmountColdButton.clicked.connect(self.unmountColdCB)
        self.openPort1Button = QtWidgets.QPushButton("Open Port 1")
        self.openPort1Button.clicked.connect(self.openPort1CB)
        self.closePortsButton = QtWidgets.QPushButton("Close Ports")
        self.closePortsButton.clicked.connect(self.closePortsCB)
        self.warmupButton = QtWidgets.QPushButton("Dry Gripper")
        self.warmupButton.clicked.connect(self.parent.dryGripperCB)
        self.enableTScreenButton = QtWidgets.QPushButton("Enable Dewar Tscreen")
        self.enableTScreenButton.clicked.connect(self.parent.enableTScreenGripperCB)
        self.parkButton = QtWidgets.QPushButton("Park Gripper")
        self.parkButton.clicked.connect(self.parent.parkGripperCB)
        self.homePinsButton = QtWidgets.QPushButton("Home Pins")
        self.homePinsButton.clicked.connect(self.homePinsCB)
        self.clearMountedSampleButton = QtWidgets.QPushButton("Clear Mounted Sample")
        self.clearMountedSampleButton.clicked.connect(self.clearMountedSampleCB)
        self.refreshDewarListButton = QtWidgets.QPushButton("Refresh Dewar Tree")
        self.refreshDewarListButton.clicked.connect(self.refresh_dewar_tree)
        hBoxColParams2.addWidget(self.openPort1Button)
        hBoxColParams2.addWidget(self.closePortsButton)
        hBoxColParams2.addWidget(self.unmountColdButton)
        hBoxColParams2.addWidget(self.warmupButton)
        hBoxColParams2.addWidget(self.enableTScreenButton)
        hBoxColParams2.addWidget(self.parkButton)
        hBoxColParams2.addWidget(self.clearMountedSampleButton)
        hBoxColParams2.addWidget(self.refreshDewarListButton)
        hBoxColParams1.addWidget(self.homePinsButton)
        self.setFastDPNodesButton = QtWidgets.QPushButton("Set FastDP Nodes")
        self.setFastDPNodesButton.clicked.connect(self.setFastDPNodesCB)
        hBoxFastDP.addWidget(self.setFastDPNodesButton)
        self.fastDPNodeEntryList = []
        nodeList = self.getFastDPNodeList()
        for i in range(0, self.fastDPNodeCount):
            self.fastDPNodeEntryList.append(QtWidgets.QLineEdit())
            self.fastDPNodeEntryList[i].setFixedWidth(30)
            self.fastDPNodeEntryList[i].setText(str(nodeList[i]))
            hBoxFastDP.addWidget(self.fastDPNodeEntryList[i])
        self.fastDPCheckBox = QCheckBox("FastDP")
        self.fastDPCheckBox.setChecked(True)
        hBoxFastDP.addWidget(self.fastDPCheckBox)
        self.setBeamcenterButton = QtWidgets.QPushButton("Set Beamcenter")
        self.setBeamcenterButton.clicked.connect(self.setBeamcenterCB)
        hBoxFastDP.addWidget(self.setBeamcenterButton)
        self.beamcenterX_ledit = QtWidgets.QLineEdit()
        self.beamcenterX_ledit.setText(str(self.parent.beamCenterX_pv.get()))
        self.beamcenterY_ledit = QtWidgets.QLineEdit()
        self.beamcenterY_ledit.setText(str(self.parent.beamCenterY_pv.get()))
        hBoxFastDP.addWidget(self.beamcenterX_ledit)
        hBoxFastDP.addWidget(self.beamcenterY_ledit)
        self.setSpotNodesButton = QtWidgets.QPushButton("Set Spotfinder Nodes")
        self.setSpotNodesButton.clicked.connect(self.setSpotNodesCB)
        self.lockGuiButton = QtWidgets.QPushButton("Lock")
        self.lockGuiButton.clicked.connect(self.lockGuiCB)
        self.unLockGuiButton = QtWidgets.QPushButton("unLock")
        self.unLockGuiButton.clicked.connect(self.unLockGuiCB)
        hBoxSpotfinder.addWidget(self.lockGuiButton)
        hBoxSpotfinder.addWidget(self.unLockGuiButton)
        hBoxSpotfinder.addWidget(self.setSpotNodesButton)
        self.spotNodeEntryList = []
        nodeList = self.getSpotNodeList()
        for i in range(0, self.spotNodeCount):
            self.spotNodeEntryList.append(QtWidgets.QLineEdit())
            self.spotNodeEntryList[i].setFixedWidth(30)
            self.spotNodeEntryList[i].setText(str(nodeList[i]))
            hBoxSpotfinder.addWidget(self.spotNodeEntryList[i])
        robotGB = QtWidgets.QGroupBox()
        robotGB.setTitle("Robot")
        hBoxRobot1 = QtWidgets.QHBoxLayout()
        vBoxRobot1 = QtWidgets.QVBoxLayout()
        self.recoverRobotButton = QtWidgets.QPushButton("Recover Robot")
        self.recoverRobotButton.clicked.connect(self.recoverRobotCB)
        self.rebootEMBLButton = QtWidgets.QPushButton("Reboot EMBL")
        self.rebootEMBLButton.clicked.connect(self.rebootEMBL_CB)
        self.restartEMBLButton = QtWidgets.QPushButton("Start EMBL")
        self.restartEMBLButton.clicked.connect(self.restartEMBL_CB)
        self.openGripperButton = QtWidgets.QPushButton("Open Gripper")
        self.openGripperButton.clicked.connect(self.openGripper_CB)
        self.closeGripperButton = QtWidgets.QPushButton("Close Gripper")
        self.closeGripperButton.clicked.connect(self.closeGripper_CB)
        hBoxRobot1.addWidget(self.robotOnCheckBox)
        hBoxRobot1.addWidget(self.beamCheckOnCheckBox)
        hBoxRobot1.addWidget(self.gripperUnmountColdCheckBox)
        hBoxRobot1.addWidget(self.topViewCheckOnCheckBox)
        hBoxRobot1.addWidget(self.enableMountCheckBox)
        hBoxRobot1.addWidget(self.recoverRobotButton)
        hBoxRobot1.addWidget(self.rebootEMBLButton)
        hBoxRobot1.addWidget(self.restartEMBLButton)
        hBoxRobot1.addWidget(self.openGripperButton)
        hBoxRobot1.addWidget(self.closeGripperButton)
        vBoxRobot1.addLayout(hBoxRobot1)
        vBoxRobot1.addLayout(hBoxColParams2)
        robotGB.setLayout(vBoxRobot1)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok, QtCore.Qt.Horizontal, self
        )
        self.buttons.buttons()[0].clicked.connect(self.screenDefaultsOKCB)
        vBoxColParams1.addLayout(hBoxColParams0)
        vBoxColParams1.addLayout(hBoxColParams1)
        vBoxColParams1.addLayout(hBoxFastDP)
        vBoxColParams1.addLayout(hBoxSpotfinder)
        vBoxColParams1.addWidget(robotGB)
        vBoxColParams1.addWidget(self.buttons)
        self.setLayout(vBoxColParams1)
        if show:
            self.show()


    def refresh_dewar_tree(self):
        self.parent.dewarTree.refreshTreeDewarView(get_latest_pucks=True)

    def show(self):
        self.checkQueueCollect()
        super().show()

    def getSpotNodeList(self):
        nodeList = []
        for i in range(0, self.spotNodeCount):
            nodeList.append(int(getBlConfig("spotNode"+str(i+1)).split('cpu')[1]))
        return nodeList

    def getFastDPNodeList(self):
        nodeList = []
        for i in range(0, self.fastDPNodeCount):
            nodeList.append(int(getBlConfig("fastDPNode" + str(i + 1)).split("cpu")[1]))
        return nodeList

    def setFastDPNodesCB(self):
        self.parent.send_to_server(
            "fastDPNodes",
            [
                int(self.fastDPNodeEntryList[i].text())
                for i in range(self.fastDPNodeCount)
            ],
        )

    def lockGuiCB(self):
        self.parent.send_to_server("lockControl")

    def unLockGuiCB(self):
        self.parent.send_to_server("unlockControl")

    def setSpotNodesCB(self):
        self.parent.send_to_server(
            "spotNodes",
            [int(self.spotNodeEntryList[i].text()) for i in range(self.spotNodeCount)],
        )

    def unmountColdCB(self):
        self.parent.send_to_server("unmountCold")

    def openPort1CB(self):
        self.parent.send_to_server("openPort", [1])

    def setBeamcenterCB(self):
        self.parent.send_to_server(
            "set_beamcenter",
            [self.beamcenterX_ledit.text(), self.beamcenterY_ledit.text()],
        )

    def closePortsCB(self):
        self.parent.send_to_server("closePorts")

    def clearMountedSampleCB(self):
        self.parent.send_to_server("clearMountedSample")

    def recoverRobotCB(self):
        self.parent.aux_send_to_server("recoverRobot")

    def rebootEMBL_CB(self):
        self.parent.aux_send_to_server("rebootEMBL")

    def restartEMBL_CB(self):
        self.parent.send_to_server("restartEMBL")

    def openGripper_CB(self):
        self.parent.send_to_server("openGripper")

    def closeGripper_CB(self):
        self.parent.send_to_server("closeGripper")

    def homePinsCB(self):
        self.parent.send_to_server("homePins")

    def robotOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("robot_online", 1)
        else:
            setBlConfig("robot_online", 0)

    def beamCheckOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig(BEAM_CHECK, 1)
            logger.debug(f"{BEAM_CHECK} on")
        else:
            setBlConfig(BEAM_CHECK, 0)
            logger.debug(f"{BEAM_CHECK} off")

    def set_energy_check_cb(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig(SET_ENERGY_CHECK, 1)
            logger.debug(f"{SET_ENERGY_CHECK} on")
        else:
            setBlConfig(SET_ENERGY_CHECK, 0)
            logger.debug(f"{SET_ENERGY_CHECK} off")
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("Set Energy state changed, please restart the GUI to access feature")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)  # type: ignore
        msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Ok)

    def unmountColdCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            logger.info("unmountColdCheckCB On")
            setBlConfig(UNMOUNT_COLD_CHECK, 1)
        else:
            logger.info("unmountColdCheckCB Off")
            setBlConfig(UNMOUNT_COLD_CHECK, 0)

    def topViewOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig(TOP_VIEW_CHECK, 1)
        else:
            setBlConfig(TOP_VIEW_CHECK, 0)

    def vertRasterOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("vertRasterOn", 1)
        else:
            setBlConfig("vertRasterOn", 0)

    def procRasterOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("rasterProcessFlag", 1)
        else:
            setBlConfig("rasterProcessFlag", 0)

    def guiRemoteOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("omegaMonitorPV", "VAL")
        else:
            setBlConfig("omegaMonitorPV", "RBV")

    def queueCollectOnCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("queueCollect", 1)
            self.gripperUnmountColdCheckBox.setEnabled(True)
            self.parent.queue_collect_status_widget.setText("Queue Collect: ON")
        else:
            setBlConfig("queueCollect", 0)
            self.gripperUnmountColdCheckBox.setEnabled(False)
            self.parent.queue_collect_status_widget.setText("Queue Collect: OFF")
        self.parent.row_clicked(
            0
        )  # This is so that appropriate boxes are filled when toggling queue collect

    def checkQueueCollect(self):
        if getBlConfig("queueCollect") == 1:
            self.queueCollectOnCheckBox.setChecked(True)
            self.gripperUnmountColdCheckBox.setEnabled(True)
        else:
            self.queueCollectOnCheckBox.setChecked(False)
            self.gripperUnmountColdCheckBox.setEnabled(False)

    def enableMountCheckCB(self, state):
        if state == QtCore.Qt.Checked:
            setBlConfig("mountEnabled", 1)
        else:
            setBlConfig("mountEnabled", 0)

    def screenDefaultsCancelCB(self):
        self.hide()

    def screenDefaultsOKCB(self):
        self.hide()
