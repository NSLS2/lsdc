import getpass
import logging
import os
import typing

import requests
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

import daq_utils
import db_lib
from config_params import (
    DEWAR_SECTORS,
    IS_STAFF,
    PUCKS_PER_DEWAR_SECTOR,
    SAMPLE_TIMER_DELAY,
    MountState
)

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()

global sampleDict
sampleDict = {}

global containerDict
containerDict = {}
ICON = ":/trolltech/styles/commonstyle/images/file-16.png"


class DewarTree(QtWidgets.QTreeView):
    def __init__(self, parent: "ControlMain"):
        super(DewarTree, self).__init__(parent)
        self.pucksPerDewarSector = PUCKS_PER_DEWAR_SECTOR[daq_utils.beamline]
        self.dewarSectors = DEWAR_SECTORS[daq_utils.beamline]
        self.parent = parent
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setAnimated(True)
        self.model = QtGui.QStandardItemModel()

        # self.isExpanded = 1
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openMenu)
        self.setStyleSheet("QTreeView::item::hover{background-color: #999966;}")
        # Keeps track of whether the user is part of a proposal
        self.proposal_membership = {}

    def openMenu(self, position):
        indexes = self.selectedIndexes()
        selectedLevels = set()
        if indexes:
            for index in indexes:
                level = 0
                while index.parent().isValid():
                    index = index.parent()
                    level += 1
                selectedLevels.add(level)
            if len(selectedLevels) == 1:
                level = list(selectedLevels)[0]
                menu = QtWidgets.QMenu()
                if level == 2:  # This is usually a request
                    useParamsAction = QtWidgets.QAction('Use Request Parameters', self)
                    useParamsAction.triggered.connect(self.useParamsCB)
                    deleteReqAction = QtWidgets.QAction(
                        "Delete selected request(s)", self
                    )
                    deleteReqAction.triggered.connect(self.deleteSelectedCB)
                    cloneReqAction = QtWidgets.QAction("Clone selected request", self)
                    cloneReqAction.triggered.connect(self.cloneRequestCB)
                    queueSelAction = QtWidgets.QAction(
                        "Queue selected request(s)", self
                    )
                    queueSelAction.triggered.connect(self.queueAllSelectedCB)
                    dequeueSelAction = QtWidgets.QAction(
                        "Dequeue selected request(s)", self
                    )
                    dequeueSelAction.triggered.connect(self.deQueueAllSelectedCB)
                    menu.addAction(useParamsAction)
                    menu.addAction(cloneReqAction)
                    menu.addAction(queueSelAction)
                    menu.addAction(dequeueSelAction)
                    menu.addSeparator()
                    menu.addAction(deleteReqAction)
                menu.exec_(self.viewport().mapToGlobal(position))

    def useParamsCB(self):
        index = self.selectedIndexes()[0]
        item = self.model.itemFromIndex(index)
        requestData = db_lib.getRequestByID(item.data(32))
        reqObj = requestData['request_obj']
        self.parent.fillRequestParameters(reqObj)

    def fillToolTip(self, data):
        text = ""
        table_data = {}
        if 'request_obj' in data:
            req_data = data['request_obj']
            table_data['Exposure Time'] = req_data['exposure_time']
            table_data['Transmission'] = req_data['attenuation']
            table_data['Oscillation Width'] = req_data['img_width']
            table_data['Oscillation Range'] = req_data['sweep_end'] - req_data['sweep_start']
            table_data['Oscillation Start'] = req_data['sweep_start']
            table_data['Detector Distance'] = req_data['detDist']
            table_data['Resolution'] = req_data['resolution']
            table_data['Energy (eV)'] = req_data['energy']
            table_data['Wavelength'] = req_data['wavelength']
            table_data['Data path'] = req_data['directory']
            text = """<table border='1' style='border-collapse: collapse;'>
            <tr>
            <th style='border: 1px solid black;'>Parameter</th>
            <th style='border: 1px solid black;'>Value</th>
            </tr>"""
            for key, value in table_data.items():
                text += f"""<tr><td style='border: 1px solid black;'>{key}</td>
                <td style='border: 1px solid black;'>{value}</td></tr>"""
            text = text + "</table>" 
        return text  
    
    def cloneRequestCB(self):
        # Only the first selected request is cloned (If multiple are chosen)
        index = self.selectedIndexes()[0]
        item = self.model.itemFromIndex(index)
        requestData = db_lib.getRequestByID(item.data(32))
        protocol = requestData["request_obj"]["protocol"]
        if "raster" in protocol.lower():  # Will cover specRaster and stepRaster as well
            self.parent.cloneRequestCB()
        elif "standard" in protocol.lower():
            self.parent.addRequestsToAllSelectedCB()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self.deleteSelectedCB(0)
        else:
            super(DewarTree, self).keyPressEvent(event)

    def refreshTree(self):
        self.parent.dewarViewToggleCheckCB()

    def set_mounted_sample(self, item, sample_name=None):
        # Formats the text of the item that is passed in as the mounted sample
        item.setForeground(QtGui.QColor("red"))
        font = QtGui.QFont()
        font.setUnderline(True)
        font.setItalic(True)
        font.setOverline(True)
        item.setFont(font)
        if self.parent.mountedPin_pv.get_pin_state() is not None:
            state = self.parent.mountedPin_pv.get_pin_state()
            mount_state = MountState(state)
            if sample_name is None:
                sample_name = item.text()
            item.setText(sample_name + MountState.get_text(mount_state))

    def refreshTreeDewarView(self, get_latest_pucks=False):
        puck = ""
        self.model.clear()
        dewar_data, puck_data, sample_data, request_data = db_lib.get_dewar_tree_data(
            daq_utils.primaryDewarName, daq_utils.beamline, get_latest_pucks
        )
        parentItem = self.model.invisibleRootItem()
        for i, puck_id in enumerate(
            dewar_data["content"]
        ):  # dewar contents is the list of puck IDs
            puck = ""
            puckName = ""
            if puck_id:
                puck = puck_data[puck_id]
                puckName = puck["name"]
            sector, puck_pos = divmod(i, self.pucksPerDewarSector)
            index_s = f"{sector+1}{chr(puck_pos + ord('A'))}"
            item = QtGui.QStandardItem(QtGui.QIcon(ICON), f"{index_s} {puckName}")
            item.setData(puckName, 32)
            item.setData("container", 33)
            parentItem.appendRow(item)
            if puck != "" and puckName != "private":
                puckContents = puck.get("content", [])
                self.add_samples_to_puck_tree(
                    puckContents, item, index_s, sample_data, request_data
                )
        self.setModel(self.model)
        self.model.itemChanged.connect(self.queueSelectedSample)
        if self.isExpanded:
            self.expandAll()
        else:
            self.collapseAll()
        self.scrollTo(self.currentIndex(), QtWidgets.QAbstractItemView.PositionAtCenter)

    def add_samples_to_puck_tree(
        self,
        puckContents,
        parentItem: QtGui.QStandardItem,
        index_label,
        sample_data,
        request_data,
    ):
        # Method will attempt to add samples to the puck. If you don't belong to the proposal,
        # it will not add samples and clear the puck information
        selectedIndex = None
        mountedIndex = None
        selectedSampleIndex = None
        collectionRunning = False
        for j, sample_id in enumerate(puckContents):
            if not sample_id:
                # this is an empty spot, no sample
                position_s = str(j + 1)
                item = QtGui.QStandardItem(QtGui.QIcon(ICON), position_s)
                item.setData("", 32)
                parentItem.appendRow(item)
                continue

            sample = sample_data[sample_id]

            if not IS_STAFF and not self.is_proposal_member(sample["proposalID"]):
                # If the user is not part of the proposal and is not staff, don't fill tree
                # Clear the puck information and don't make it selectable
                parentItem.setText(index_label)
                current_flags = parentItem.flags()
                parentItem.setFlags(current_flags & ~Qt.ItemFlag.ItemIsSelectable)  # type: ignore
                position_s = f'{j+1}-{sample.get("name", "")}'
                item = QtGui.QStandardItem(
                    QtGui.QIcon(ICON),
                    position_s,
                )
                return

            proposal_id_text = f"(pass-{sample['proposalID']})"
            if not parentItem.text().endswith(proposal_id_text):
                parentItem.setText(f"{parentItem.text()} -- {proposal_id_text}")

            position_s = f'{j+1}-{sample.get("name", "")}'
            item = QtGui.QStandardItem(
                QtGui.QIcon(ICON),
                position_s,
            )
            # just stuck sampleID there, but negate it to diff from reqID
            item.setData(sample_id, 32)
            item.setData("sample", 33)
            if sample_id == self.parent.mountedPin_pv.get():
                self.set_mounted_sample(item, position_s)
            parentItem.appendRow(item)

            if sample_id == self.parent.mountedPin_pv.get():
                mountedIndex = self.model.indexFromItem(item)
            # looking for the selected item
            if sample_id == self.parent.selectedSampleID:
                logger.info("found " + str(self.parent.SelectedItemData))
                selectedSampleIndex = self.model.indexFromItem(item)
            sampleRequestList = request_data[sample_id]
            for request in sampleRequestList:
                if not ("protocol" in request["request_obj"]):
                    continue
                col_item = self.create_request_item(request)
                if request["priority"] == 99999:
                    selectedIndex = self.model.indexFromItem(
                        col_item
                    )  ##attempt to leave it on the request after collection
                    collectionRunning = True
                item.appendRow(col_item)
                if (
                    request["uid"] == self.parent.SelectedItemData
                ):  # looking for the selected item, this is a request
                    selectedIndex = self.model.indexFromItem(col_item)

        current_index = None
        if not collectionRunning:
            if selectedSampleIndex:
                current_index = selectedSampleIndex
            elif mountedIndex:
                current_index = mountedIndex
                item = self.model.itemFromIndex(mountedIndex)
            elif selectedIndex:
                current_index = selectedIndex
        elif collectionRunning and mountedIndex:
            current_index = mountedIndex

        if current_index:
            self.setCurrentIndex(current_index)
            self.parent.row_clicked(current_index)

    def is_proposal_member(self, proposal_id) -> bool:
        # Check if the user running LSDC is part of the sample's proposal
        try:
            if proposal_id not in self.proposal_membership:
                r = requests.get(f"{os.environ['NSLS2_API_URL']}/v1/proposal/{proposal_id}")
                r.raise_for_status()
                response = r.json()['proposal']
                if "users" in response and getpass.getuser() in [
                    user["username"] for user in response["users"] if "username" in user
                ]:
                    self.proposal_membership[proposal_id] = True
                else:
                    logger.info(f"Users not found in response: {response}")
                    self.proposal_membership[proposal_id] = False
        except Exception as e:
            logger.exception(e)
            return False
        return self.proposal_membership[proposal_id]

    def create_request_item(self, request) -> QtGui.QStandardItem:
        col_item = QtGui.QStandardItem(
            QtGui.QIcon(ICON),
            request["request_obj"]["file_prefix"]
            + "_"
            + request["request_obj"]["protocol"],
        )
        col_item.setData(request["uid"], 32)
        col_item.setData("request", 33)
        col_item.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable  # type:ignore
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
        )
        if request["priority"] == 99999:
            col_item.setCheckState(Qt.CheckState.Checked)
            col_item.setBackground(QtGui.QColor("green"))
            self.parent.refreshCollectionParams(request, validate_hdf5=False)
        elif request["priority"] > 0:
            col_item.setCheckState(Qt.CheckState.Checked)
            col_item.setBackground(QtGui.QColor("white"))
        elif request["priority"] < 0:
            col_item.setCheckable(False)
            col_item.setBackground(QtGui.QColor("cyan"))
        else:
            col_item.setCheckState(Qt.CheckState.Unchecked)
            col_item.setBackground(QtGui.QColor("white"))
        col_item.setToolTip(self.fillToolTip(request))
        return col_item

    def refreshTreePriorityView(
        self,
    ):  # "item" is a sample, "col_items" are requests which are children of samples.
        collectionRunning = False
        selectedIndex = None
        mountedIndex = None
        selectedSampleIndex = None
        self.model.clear()
        self.orderedRequests = db_lib.getOrderedRequestList(daq_utils.beamline)
        dewarContents = db_lib.getContainerByName(
            daq_utils.primaryDewarName, daq_utils.beamline
        )["content"]
        maxPucks = len(dewarContents)
        requestedSampleList = []
        mountedPin = self.parent.mountedPin_pv.get()
        for i in range(
            len(self.orderedRequests)
        ):  # I need a list of samples for parent nodes
            if self.orderedRequests[i]["sample"] not in requestedSampleList:
                requestedSampleList.append(self.orderedRequests[i]["sample"])
        for i in range(len(requestedSampleList)):
            sample = db_lib.getSampleByID(requestedSampleList[i])
            owner = sample["owner"]
            parentItem = self.model.invisibleRootItem()
            nodeString = str(db_lib.getSampleNamebyID(requestedSampleList[i]))
            item = QtGui.QStandardItem(
                QtGui.QIcon(ICON),
                nodeString,
            )
            item.setData(requestedSampleList[i], 32)
            item.setData("sample", 33)
            if requestedSampleList[i] == mountedPin:
                self.set_mounted_sample(item)
            parentItem.appendRow(item)
            if requestedSampleList[i] == mountedPin:
                mountedIndex = self.model.indexFromItem(item)
            if (
                requestedSampleList[i] == self.parent.selectedSampleID
            ):  # looking for the selected item
                selectedSampleIndex = self.model.indexFromItem(item)
            parentItem = item
            for k in range(len(self.orderedRequests)):
                if self.orderedRequests[k]["sample"] == requestedSampleList[i]:
                    col_item = QtGui.QStandardItem(
                        QtGui.QIcon(ICON),
                        self.orderedRequests[k]["request_obj"]["file_prefix"]
                        + "_"
                        + self.orderedRequests[k]["request_obj"]["protocol"],
                    )
                    col_item.setData(self.orderedRequests[k]["uid"], 32)
                    col_item.setData("request", 33)
                    col_item.setFlags(
                        Qt.ItemIsUserCheckable
                        | Qt.ItemIsEnabled
                        | Qt.ItemIsEditable
                        | Qt.ItemIsSelectable
                    )
                    if self.orderedRequests[k]["priority"] == 99999:
                        col_item.setCheckState(Qt.Checked)
                        col_item.setBackground(QtGui.QColor("green"))
                        collectionRunning = True
                        self.parent.refreshCollectionParams(
                            self.orderedRequests[k], validate_hdf5=False
                        )

                    elif self.orderedRequests[k]["priority"] > 0:
                        col_item.setCheckState(Qt.Checked)
                        col_item.setBackground(QtGui.QColor("white"))
                    elif self.orderedRequests[k]["priority"] < 0:
                        col_item.setCheckable(False)
                        col_item.setBackground(QtGui.QColor("cyan"))
                    else:
                        col_item.setCheckState(Qt.Unchecked)
                        col_item.setBackground(QtGui.QColor("white"))
                    item.appendRow(col_item)
                    if (
                        self.orderedRequests[k]["uid"] == self.parent.SelectedItemData
                    ):  # looking for the selected item
                        selectedIndex = self.model.indexFromItem(col_item)
        self.setModel(self.model)
        if selectedSampleIndex != None and collectionRunning == False:
            self.setCurrentIndex(selectedSampleIndex)
            self.parent.row_clicked(selectedSampleIndex)
        elif selectedSampleIndex == None and collectionRunning == False:
            if mountedIndex != None:
                self.setCurrentIndex(mountedIndex)
                self.parent.row_clicked(mountedIndex)
        else:
            pass

        if selectedIndex != None and collectionRunning == False:
            self.setCurrentIndex(selectedIndex)
            self.parent.row_clicked(selectedIndex)
        self.scrollTo(self.currentIndex(), QtWidgets.QAbstractItemView.PositionAtCenter)
        self.expandAll()

    def queueSelectedSample(self, item):
        if item.data(33) == "request":
            reqID = str(item.data(32))
            checkedSampleRequest = db_lib.getRequestByID(reqID)  # line not needed???
            if item.checkState() == Qt.Checked:
                db_lib.updatePriority(reqID, 5000)
            else:
                db_lib.updatePriority(reqID, 0)
            item.setBackground(QtGui.QColor("white"))
            self.parent.treeChanged_pv.put(
                self.parent.processID
            )  # the idea is touch the pv, but have this gui instance not refresh

    def queueAllSelectedCB(self):
        selmod = self.selectionModel()
        selection = selmod.selection()
        indexes = selection.indexes()
        for i in range(len(indexes)):
            item = self.model.itemFromIndex(indexes[i])
            itemData = str(item.data(32))
            itemDataType = str(item.data(33))
            if (itemDataType == "request") and item.isCheckable():
                selectedSampleRequest = db_lib.getRequestByID(itemData)
                db_lib.updatePriority(itemData, 5000)
        self.parent.treeChanged_pv.put(1)

    def deQueueAllSelectedCB(self):
        selmod = self.selectionModel()
        selection = selmod.selection()
        indexes = selection.indexes()
        for i in range(len(indexes)):
            item = self.model.itemFromIndex(indexes[i])
            itemData = str(item.data(32))
            itemDataType = str(item.data(33))
            if (itemDataType == "request") and item.isCheckable():
                selectedSampleRequest = db_lib.getRequestByID(itemData)
                db_lib.updatePriority(itemData, 0)
        self.parent.treeChanged_pv.put(1)

    def confirmDelete(self, numReq):
        if numReq:
            quit_msg = f"Are you sure you want to delete {numReq} requests?"
        else:
            quit_msg = "Are you sure you want to delete all requests?"
        self.parent.timerSample.stop()
        reply = QtWidgets.QMessageBox.question(
            self,
            "Message",
            quit_msg,
            QtWidgets.QMessageBox.Yes,
            QtWidgets.QMessageBox.No,
        )
        self.parent.timerSample.start(SAMPLE_TIMER_DELAY)
        if reply == QtWidgets.QMessageBox.Yes:
            return 1
        else:
            return 0

    def deleteSelectedCB(self, deleteAll):
        if deleteAll:
            if not self.confirmDelete(0):
                return
            self.selectAll()
        selmod = self.selectionModel()
        selection = selmod.selection()
        indexes = selection.indexes()
        if len(indexes) > 1:
            if not self.confirmDelete(len(indexes)):
                return
        progressInc = 100.0 / float(len(indexes))
        self.parent.progressDialog.setWindowTitle("Deleting Requests")
        self.parent.progressDialog.show()
        for i in range(len(indexes)):
            self.parent.progressDialog.setValue(int((i + 1) * progressInc))
            item = self.model.itemFromIndex(indexes[i])
            itemData = str(item.data(32))
            itemDataType = str(item.data(33))
            if itemDataType == "request":
                selectedSampleRequest = db_lib.getRequestByID(itemData)
                self.selectedSampleID = selectedSampleRequest["sample"]
                db_lib.deleteRequest(selectedSampleRequest["uid"])
                if selectedSampleRequest["request_obj"]["protocol"] in (
                    "raster",
                    "stepRaster",
                    "multiCol",
                ):
                    for i in range(len(self.parent.rasterList)):
                        if self.parent.rasterList[i] != None:
                            if (
                                self.parent.rasterList[i]["uid"]
                                == selectedSampleRequest["uid"]
                            ):
                                self.parent.scene.removeItem(
                                    self.parent.rasterList[i]["graphicsItem"]
                                )
                                self.parent.rasterList[i] = None
                if (
                    selectedSampleRequest["request_obj"]["protocol"] == "vector"
                    or selectedSampleRequest["request_obj"]["protocol"] == "stepVector"
                ):
                    self.parent.clearVectorCB()
        self.parent.progressDialog.close()
        self.parent.treeChanged_pv.put(1)

    def expandAllCB(self):
        self.expandAll()

    def collapseAllCB(self):
        self.collapseAll()

    def getSelectedSample(self):
        selectedSampleID = None
        if self.selectedIndexes():
            index = self.selectedIndexes()[0]
            item = self.model.itemFromIndex(index)
            if str(item.data(33)) == "sample":
                selectedSampleID = str(item.data(32))
            elif str(item.data(33)) == "request":
                selectedSampleRequest = db_lib.getRequestByID(item.data(32))
                selectedSampleID = selectedSampleRequest["sample"]
        return selectedSampleID
