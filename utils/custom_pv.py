from epics import PV


class MountedPinPV(PV):

    def get(self, *args, **kwargs):
        value = str(super().get(*args, **kwargs))
        return value.split(",")[0]

    def get_pin_state(self):
        value = str(super().get()).split(",")
        if len(value) == 2:
            return value[1]
        return None
