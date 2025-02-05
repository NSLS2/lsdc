import daq_utils
if daq_utils.beamline != 'nyx':
    from .loop_detection import detect_loop
else:
    from .jpeg_loop_detection import detect_loop
from .top_view import topview_optimized
