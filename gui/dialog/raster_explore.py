from qtpy import QtWidgets
from qtpy.QtCore import Qt


class RasterExploreDialog(QtWidgets.QDialog):
    def __init__(self):
        QtWidgets.QDialog.__init__(self)
        self.setModal(False)
        self.setWindowTitle("Raster Explore")
        vBoxParams1 = QtWidgets.QVBoxLayout()
        hBoxParams1 = QtWidgets.QHBoxLayout()
        hBoxParams2 = QtWidgets.QHBoxLayout()
        hBoxParams3 = QtWidgets.QHBoxLayout()
        spotCountLabel = QtWidgets.QLabel("Spot Count:")
        spotCountLabel.setFixedWidth(120)
        self.spotCount_ledit = QtWidgets.QLabel()
        self.spotCount_ledit.setFixedWidth(60)
        hBoxParams1.addWidget(spotCountLabel)
        hBoxParams1.addWidget(self.spotCount_ledit)
        intensityLabel = QtWidgets.QLabel("Total Intensity:")
        intensityLabel.setFixedWidth(120)
        self.intensity_ledit = QtWidgets.QLabel()
        self.intensity_ledit.setFixedWidth(60)
        hBoxParams2.addWidget(intensityLabel)
        hBoxParams2.addWidget(self.intensity_ledit)
        resoLabel = QtWidgets.QLabel("Resolution:")
        resoLabel.setFixedWidth(120)
        self.reso_ledit = QtWidgets.QLabel()
        self.reso_ledit.setFixedWidth(60)
        hBoxParams3.addWidget(resoLabel)
        hBoxParams3.addWidget(self.reso_ledit)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        self.buttons.buttons()[0].clicked.connect(self.rasterExploreCancelCB)
        vBoxParams1.addLayout(hBoxParams1)
        vBoxParams1.addLayout(hBoxParams2)
        vBoxParams1.addLayout(hBoxParams3)
        vBoxParams1.addWidget(self.buttons)
        self.setLayout(vBoxParams1)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowDoesNotAcceptFocus)

    def setSpotCount(self, val):
        self.spotCount_ledit.setText(str(val))

    def setTotalIntensity(self, val):
        self.intensity_ledit.setText(str(val))

    def setResolution(self, val):
        self.reso_ledit.setText(str(val))

    def rasterExploreCancelCB(self):
        self.done(QtWidgets.QDialog.Rejected)
