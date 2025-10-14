from functools import wraps
from ophyd import Device
try:
    from .auto_center import *
    from .top_align import *
    from .zebra import *
except Exception as e:
    pass


def standardize_readback(cls):
    original_init = cls.__init__

    @wraps(original_init)
    def new_init(self, *args, **kwargs):
        methods_to_extend = {"readback": "user_readback", 
                             "setpoint": "user_setpoint",
                             "val": "user_readback.get"}
        original_init(self, *args, **kwargs)
        for attr_name in self.component_names:
            comp = getattr(self, attr_name)
            if not isinstance(comp, Device):
                continue

            for new_method_name, old_method_name in methods_to_extend.items():
                if not hasattr(comp, new_method_name):
                    if hasattr(comp, old_method_name):
                        setattr(comp, new_method_name, getattr(comp, old_method_name))

    cls.__init__ = new_init
    return cls

from .generic import *