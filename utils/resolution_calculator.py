import math


class Calculator:
    """
    Make a calculator object that can calculate resolution formulas (and nothing else)

    """

    def __init__(self):
        self.r = None
        self.d = None
        self.L = None
        self.theta = None
        self.wavelength = None

    def set_all_variables(self, variable_dict):
        for key in variable_dict:
            self.set_variables(key, variable_dict[key])

    def set_variables(self, name, value):
        if name == "r":
            self.r = value
        elif name == "d":
            self.d = value
        elif name == "L":
            self.L = value
        elif name == "theta":
            self.theta = value
        elif name == "wavelength":
            self.wavelength = value

    def calcD(self, r=None, L=None, wavelength=None, theta=None):
        r = r or self.r
        L = L or self.L
        wavelength = wavelength or self.wavelength
        theta = theta or self.theta
        try:
            denominator = 2 * (math.sin((0.5 * math.atan(r / L)) + theta))
            numerator = wavelength
            return numerator / denominator
        except Exception as e:
            return e

    def calcL(self, r=None, d=None, wavelength=None, theta=None):
        r = r or self.r
        d = d or self.d
        wavelength = wavelength or self.wavelength
        theta = theta or self.theta
        try:
            denominator = math.tan((2 * math.asin(wavelength / (2 * d))) - (2 * theta))
            numerator = r
            return numerator / denominator
        except Exception as e:
            return e

    def calcTheta(self, r=None, L=None, wavelength=None, d=None):
        r = r or self.r
        L = L or self.L
        wavelength = wavelength or self.wavelength
        d = d or self.d
        try:
            val1 = math.asin(wavelength / (2 * d))
            val2 = 0.5 * math.atan(r / L)
            return val1 - val2
        except Exception as e:
            return e

    def calcWavelength(self, r=None, L=None, d=None, theta=None):
        r = r or self.r
        L = L or self.L
        d = d or self.d
        theta = theta or self.theta
        valin = 0.5 * math.atan(r / L)
        try:
            wavelength = 2 * d * math.sin(valin + theta)
            return wavelength
        except Exception as e:
            return e
