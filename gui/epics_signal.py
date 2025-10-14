from qtpy.QtCore import Signal, QObject
from epics import PV


class EpicsQObject(QObject):
    """
    Class to simplify the process of triggering a qt signal based on an epics PV
    Previously there were multiple unique signals defined and their corresponding callbacks
    But their code is not unique. This class attempts to reduce the noise
    """

    # Define the PyQt signal
    epics_pv_changed = Signal(object)

    def __init__(self, pv_name, qt_callback, use_string=False, pv_callback=None, custom_pv=None):
        super().__init__()
        self.use_string = use_string
        # Define the pyepics PV and its callback
        if not pv_callback:
            pv_callback = self.on_pv_changed

        if custom_pv:
            PV = custom_pv

        self.pv = PV(pv_name, callback=pv_callback, auto_monitor=True)
        self.epics_pv_changed.connect(qt_callback)

    # Define the callback for the pyepics PV
    def on_pv_changed(self, value, char_value, **kwargs):
        # Emit the PyQt signal
        if self.use_string:
            self.epics_pv_changed.emit(char_value)
        else:
            self.epics_pv_changed.emit(value)

    def get(self):
        return self.pv.get()

    def put(self, *args, **kwargs):
        self.pv.put(*args, **kwargs)
