import logging
import typing

from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

import daq_utils
import db_lib

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

logger = logging.getLogger()


class DCM(Device):
    b = Cpt(EpicsMotor, "-Ax:B}Mtr", labels=["fmx"])
    g = Cpt(EpicsMotor, "-Ax:G}Mtr", labels=["fmx"])
    p = Cpt(EpicsMotor, "-Ax:P}Mtr", labels=["fmx"])
    r = Cpt(EpicsMotor, "-Ax:R}Mtr", labels=["fmx"])
    e = Cpt(EpicsMotor, "-Ax:E}Mtr", labels=["fmx"])


class SetEnergyDialog(QtWidgets.QDialog):
    energy_changed_signal = QtCore.Signal(object)

    def __init__(self, parent: "ControlMain"):
        self.hdcm = DCM("XF:17IDA-OP:FMX{Mono:DCM", name="hdcm")
        super().__init__(parent)
        self._parent = parent
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QGridLayout()
        self.current_energy_label = QtWidgets.QLabel("Current Energy: ")
        self.current_energy_value_label = QtWidgets.QLabel(
            f"{self.hdcm.e.user_readback.get():.2f} eV"
        )
        layout.addWidget(self.current_energy_label, 0, 0)
        layout.addWidget(self.current_energy_value_label, 0, 1)

        self.setpoint_label = QtWidgets.QLabel("Energy setpoint: ")
        validator = QtGui.QDoubleValidator()
        validator.setBottom(5000)
        validator.setTop(15000)
        self.setpoint_edit = QtWidgets.QLineEdit()
        self.setpoint_edit.setValidator(validator)
        self.setpoint_edit.returnPressed.connect(self.check_value)
        layout.addWidget(self.setpoint_label, 1, 0)
        layout.addWidget(self.setpoint_edit, 1, 1)

        self.message = QtWidgets.QLabel("")
        layout.addWidget(self.message, 2, 0, 1, 2)

        self.monochromator_button = QtWidgets.QPushButton("Monochromator")
        self.monochromator_button.setAutoDefault(False)
        self.monochromator_button.clicked.connect(self.set_monochromator_energy)

        self.full_alignment_button = QtWidgets.QPushButton("Full Alignment")
        self.full_alignment_button.setAutoDefault(False)
        self.full_alignment_button.clicked.connect(self.set_full_alignment_energy)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setAutoDefault(False)

        layout.addWidget(self.monochromator_button, 3, 0)
        layout.addWidget(self.full_alignment_button, 3, 1)
        layout.addWidget(self.close_button, 4, 0, 1, 2)

        self.hdcm.e.user_readback.subscribe(self.update_energy, run=True)

        self.energy_changed_signal.connect(
            lambda value: self.current_energy_value_label.setText(f"{value:.2f}")
        )

        self.setLayout(layout)
        self.setModal(True)
        self.show()

    def update_energy(self, value, old_value, **kwargs):
        self.energy_changed_signal.emit(value)

    def check_value(self):
        if abs(float(self.setpoint_edit.text()) - self.hdcm.e.user_readback.get()) > 10:
            self.message.setText(
                "Energy change is greater than 10 eV.\nMonochromator cannot be used for alignment"
            )
            self.monochromator_button.setDisabled(True)
        else:
            self.message.setText("Energy change less than 10 eV")
            self.monochromator_button.setDisabled(False)

        if float(self.setpoint_edit.text()) <= 10000:
            self.message.setText(
                f"{self.message.text()} \n Beam shape not automatically optimized \nfor energies between 5 keV and 10 keV"
            )

    def unmount_cold_dialog(self):
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("A sample is mounted. Unmount cold?")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel)  # type: ignore
        msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Ok)
        return msg_box

    def set_full_alignment_energy(self):
        if self._parent.mountedPin_pv.get():
            # If sample is mounted, ask user to unmount cold
            response = self.unmount_cold_dialog().exec_()

            if response == QtWidgets.QMessageBox.Ok:
                self._parent.send_to_server("unmountCold")
            else:
                return

        if self._parent.governorMessage.getEntry().text() not in [
            "state SE",
            "state BA",
            "state BL",
            "state XF",
            "state SA",
        ]:
            self.message.setText("Governor not in a valid state, call staff!")
            return
        else:
            self._parent.send_to_server("setGovState", ['SA'])

        self._parent.send_to_server(f"set_energy", [float(self.setpoint_edit.text())])

    def set_monochromator_energy(self):
        if abs(float(self.setpoint_edit.text()) - self.hdcm.e.user_readback.get()) > 10:
            self.message.setText(
                "Energy change is greater than 10 eV.\nMonochromator cannot be used for alignment"
            )
        else:
            self._parent.send_to_server("mvaDescriptor", ["energy", float(self.setpoint_edit.text())])
