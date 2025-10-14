import functools
import logging
import typing

from qtpy import QtWidgets

import daq_utils
import db_lib
from config_params import DEWAR_SECTORS, PUCKS_PER_DEWAR_SECTOR

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()


class DewarDialog(QtWidgets.QDialog):
    def __init__(self, parent: "ControlMain", action="add"):
        super(DewarDialog, self).__init__(parent)
        self.pucksPerDewarSector = PUCKS_PER_DEWAR_SECTOR[daq_utils.beamline]
        self.dewarSectors = DEWAR_SECTORS[daq_utils.beamline]
        self.action = action
        self.parent = parent

        self.initData()
        self.initUI()

    def initData(self):
        dewarObj = db_lib.getPrimaryDewar(daq_utils.beamline)
        puckLocs = dewarObj["content"]
        self.data = []
        self.dewarPos = None
        for i in range(len(puckLocs)):
            if puckLocs[i] != "":
                owner = db_lib.getContainerByID(puckLocs[i])["owner"]
                self.data.append(db_lib.getContainerNameByID(puckLocs[i]))
            else:
                self.data.append("Empty")
        logger.info(self.data)

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        headerLabelLayout = QtWidgets.QHBoxLayout()
        aLabel = QtWidgets.QLabel("A")
        aLabel.setFixedWidth(15)
        headerLabelLayout.addWidget(aLabel)
        bLabel = QtWidgets.QLabel("B")
        bLabel.setFixedWidth(10)
        headerLabelLayout.addWidget(bLabel)
        cLabel = QtWidgets.QLabel("C")
        cLabel.setFixedWidth(10)
        headerLabelLayout.addWidget(cLabel)
        layout.addLayout(headerLabelLayout)
        self.allButtonList = [None] * (self.dewarSectors * self.pucksPerDewarSector)
        for i in range(0, self.dewarSectors):
            rowLayout = QtWidgets.QHBoxLayout()
            numLabel = QtWidgets.QLabel(str(i + 1))
            rowLayout.addWidget(numLabel)
            for j in range(0, self.pucksPerDewarSector):
                dataIndex = (i * self.pucksPerDewarSector) + j
                self.allButtonList[dataIndex] = QtWidgets.QPushButton(
                    #(str(self.data[dataIndex]))
                    '{}: {}'.format(str(dataIndex+1),str(self.data[dataIndex]))
                )
                self.allButtonList[dataIndex].clicked.connect(
                    functools.partial(self.on_button, str(dataIndex))
                )
                rowLayout.addWidget(self.allButtonList[dataIndex])
            layout.addLayout(rowLayout)
        cancelButton = QtWidgets.QPushButton("Done")
        cancelButton.clicked.connect(self.containerCancelCB)
        layout.addWidget(cancelButton)
        self.setLayout(layout)

    def on_button(self, n):
        if self.action == "remove":
            self.dewarPos = n
            db_lib.removePuckFromDewar(daq_utils.beamline, int(n))
            self.allButtonList[int(n)].setText("Empty")
            self.parent.treeChanged_pv.put(1)
        else:
            self.dewarPos = n
            self.accept()

    def containerCancelCB(self):
        self.dewarPos = 0
        self.reject()

    @staticmethod
    def getDewarPos(parent=None, action="add"):
        dialog = DewarDialog(parent, action)
        result = dialog.exec_()
        return (dialog.dewarPos, result == QtWidgets.QDialog.Accepted)
