import typing

from qtpy import QtWidgets
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout

from utils.resolution_calculator import Calculator

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

WINDOW_SIZE = 480

# main qtpy window the calculator exists in


class CalculatorWindow(QtWidgets.QDialog):
    def __init__(self, parent: "ControlMain"):
        super(CalculatorWindow, self).__init__(parent)
        self.setFixedSize(WINDOW_SIZE, WINDOW_SIZE)
        # making radio buttons to choose formula
        self.buttonDictionary = {
            "L": {"picker": QRadioButton("Caluclate crystal to detector distance")},
            "d": {"picker": QRadioButton("Calculate resolution")},
            "theta": {"picker": QRadioButton("Calculate detector 2theta")},
            "wavelength": {"picker": QRadioButton("Calculate wavelength")},
            "r": {"value": None},
        }

        self.r_value_enter = QLineEdit()
        self.r_value_enter.setPlaceholderText("Set r value")
        self.buttonDictionary["r"]["value"] = self.r_value_enter
        self.r_value_enter.setValidator(QDoubleValidator())
        # setting inputs to Double only

        self.L_value_enter = QLineEdit()
        self.L_value_enter.setPlaceholderText("Set L value")
        self.buttonDictionary["L"]["value"] = self.L_value_enter
        self.L_value_enter.setValidator(QDoubleValidator())

        self.d_value_enter = QLineEdit()
        self.d_value_enter.setPlaceholderText("Set d value")
        self.buttonDictionary["d"]["value"] = self.d_value_enter
        self.d_value_enter.setValidator(QDoubleValidator())

        self.theta_value_enter = QLineEdit()
        self.theta_value_enter.setPlaceholderText("Set theta value")
        self.buttonDictionary["theta"]["value"] = self.theta_value_enter
        self.theta_value_enter.setValidator(QDoubleValidator())

        self.wave_value_enter = QLineEdit()
        self.wave_value_enter.setPlaceholderText("Set wavelength value")
        self.buttonDictionary["wavelength"]["value"] = self.wave_value_enter
        self.wave_value_enter.setValidator(QDoubleValidator())

        self.final_button = QPushButton("Calculate", self)
        self.final_button.clicked.connect(self.calculateValue)

        self.bottom_text = QLabel()
        self.bottom_text.setText("Enter values and Press button to calculate")

        # creating calculator object
        self.calculator = Calculator()

        layout = QVBoxLayout()
        layout.addWidget(self.r_value_enter)
        for key in self.buttonDictionary:
            if "picker" in self.buttonDictionary[key].keys():
                layout.addWidget(self.buttonDictionary[key]["picker"])
            layout.addWidget(self.buttonDictionary[key]["value"])
        layout.addWidget(self.final_button)
        layout.addWidget(self.bottom_text)
        self.setLayout(layout)

    """
	calls resolution calculator to calculate value depending on inputs from widgets

	-outputs
		-value_to_return = value from formula calculated if no problems
		-returns nothing if a problem occured, changes bottom_text
	"""

    def calculateValue(self):
        checked_key = None
        # checking which formula to use
        for key in self.buttonDictionary:
            if key != "r" and self.buttonDictionary[key]["picker"].isChecked():
                checked_key = key
        if not checked_key:
            self.bottom_text.setText(
                "No calculation specified (press one of the radio buttons)"
            )
            return

        r_value = self.r_value_enter.displayText()
        # checking if value is a number string or empty string
        if r_value == "" or r_value[0].isalpha():
            self.bottom_text.setText(
                "formula to calculate {} requires r value".format(checked_key)
            )
            return
        elif float(r_value) < 140 or float(r_value) > 350:
            self.bottom_text.setText("r value must be between 140 and 350")
            return

        r_value = float(r_value)

        d_value = self.d_value_enter.displayText()
        # checking if value is string or none if not calculating that value (trying to use .isalpha but not when value is None)
        if (d_value == "" or d_value[0].isalpha()) and checked_key != "d":
            self.bottom_text.setText(
                "formula to calculate {} requires d value".format(checked_key)
            )
            return

        l_value = self.L_value_enter.displayText()
        if (l_value == "" or l_value[0].isalpha()) and checked_key != "L":
            self.bottom_text.setText(
                "formula to calculate {} requires L value".format(checked_key)
            )
            return

        theta_value = self.theta_value_enter.displayText()
        if (theta_value == "" or theta_value[0].isalpha()) and checked_key != "theta":
            self.bottom_text.setText(
                "formula to calculate {} requires theta value".format(checked_key)
            )
            return

        wave_value = self.wave_value_enter.displayText()
        if (
            wave_value == "" or wave_value[0].isalpha()
        ) and checked_key != "wavelength":
            self.bottom_text.setText(
                "formula to calculate {} requires the wavelenght".format(checked_key)
            )
            return

        # setting value to return if want value returned
        value_to_return = None

        if checked_key == "d":
            l_value = float(self.L_value_enter.displayText())
            theta_value = float(self.theta_value_enter.displayText())
            wave_value = float(self.wave_value_enter.displayText())

            variableDict = {
                "L": l_value,
                "theta": theta_value,
                "wavelength": wave_value,
                "r": r_value,
            }

            self.calculator.set_all_variables(variableDict)
            d_value = self.calculator.calcD()
            value_to_return = d_value
            self.d_value_enter.setText(str(d_value))
            self.calculator.set_variables("d", d_value)

        elif checked_key == "L":

            d_value = float(self.d_value_enter.displayText())
            theta_value = float(self.theta_value_enter.displayText())
            wave_value = float(self.wave_value_enter.displayText())

            variableDict = {
                "d": d_value,
                "theta": theta_value,
                "wavelength": wave_value,
                "r": r_value,
            }

            self.calculator.set_all_variables(variableDict)
            L_value = self.calculator.calcL()
            value_to_return = L_value
            self.L_value_enter.setText(str(L_value))
            self.calculator.set_variables("L", L_value)

        elif checked_key == "theta":

            l_value = float(self.L_value_enter.displayText())
            d_value = float(self.d_value_enter.displayText())
            wave_value = float(self.wave_value_enter.displayText())

            variableDict = {
                "L": l_value,
                "d": d_value,
                "wavelength": wave_value,
                "r": r_value,
            }

            self.calculator.set_all_variables(variableDict)
            theta_value = self.calculator.calcTheta()
            value_to_return = theta_value
            self.theta_value_enter.setText(str(theta_value))
            self.calculator.set_variables("theta", theta_value)

        elif checked_key == "wavelength":

            l_value = float(self.L_value_enter.displayText())
            theta_value = float(self.theta_value_enter.displayText())
            d_value = float(self.d_value_enter.displayText())
            variableDict = {
                "L": l_value,
                "d": d_value,
                "theta": theta_value,
                "r": r_value,
            }

            self.calculator.set_all_variables(variableDict)
            wave_value = self.calculator.calcWavelength()
            self.calculator.set_variables("wavelength", wave_value)
            value_to_return = wave_value
            self.wave_value_enter.setText(str(wave_value))

        self.bottom_text.setText(
            "- Done Calculating - \n {} value = {}".format(checked_key, value_to_return)
        )
        return value_to_return
