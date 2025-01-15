from typing import Dict
from logging import getLogger

import numpy as np
import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.utils import FailedStatus
from bluesky.preprocessors import finalize_decorator
from ophyd.utils.errors import WaitTimeoutError
import daq_utils
from start_bs import db, two_click_low, loop_detector, gonio, low_mag_cam_reset_signal
from mxbluesky.plans.utils import mvr_with_retry, mv_with_retry

logger = getLogger()

def cleanup_two_click_low():
    if daq_utils.beamline == "fmx":
        logger.info("Cleaning up two_click_low")
        yield from bps.abs_set(two_click_low.jpeg.file_write_mode, 2, wait=True)
        yield from bps.abs_set(two_click_low.jpeg.file_template, "%s%s_%d.jpg", wait=True)

def reset_low_mag_cam():
    yield from bps.abs_set(two_click_low.cam.acquire, 0, wait=True)
    yield from bps.sleep(3)
    yield from bps.abs_set(low_mag_cam_reset_signal, 1, wait=True)
    yield from bps.sleep(5)
    yield from bps.abs_set(two_click_low.cam.acquire, 1, wait=True)

def trigger_two_click():
    tries = 0
    max_tries = 3
    
    while tries < max_tries:
        try:
            yield from bp.count([two_click_low], 1)
            break  # If trigger succeeds, exit the loop
        except (FailedStatus, WaitTimeoutError) as e:
            tries += 1
            logger.exception(f"Exception while triggering two click, retry #{tries} : {e}")
            if tries == 3:
                logger.exception("Resetting low mag camera")
                yield from reset_low_mag_cam()
                yield from bp.count([two_click_low], 1)
                
@finalize_decorator(cleanup_two_click_low)
def detect_loop(sample_detection: "Dict[str, float|int]"):
    # face on attempt, most features, should work
    yield from bps.abs_set(two_click_low.cam_mode, "two_click", wait=True)
    logger.info("Starting loop centering")
    yield from trigger_two_click()
        
    loop_detector.filename.set(two_click_low.jpeg.full_file_name.get())
    
    scan_uid = yield from bp.count([loop_detector], 1)
    #box_coords_face: "list[int]" = db[scan_uid].table()['loop_detector_box'][1]
    box_coords_face: "list[int]" = loop_detector.box.get()
    logger.info("Got loop predictions")
    if len(box_coords_face) != 4:
        logger.exception("Exception during loop detection plan. Face on loop not found")
        sample_detection["sample_detected"] = False
        return
    else:
        sample_detection["large_box_width"] = (box_coords_face[2] - box_coords_face[0]) * 2 * two_click_low.pix_per_um.get()
        sample_detection["large_box_height"] = (box_coords_face[3] - box_coords_face[1]) * 2 * two_click_low.pix_per_um.get()

        mean_x = (box_coords_face[0] + box_coords_face[2]) / 2
        mean_y = (box_coords_face[1] + box_coords_face[3]) / 2

    mean_x = mean_x - 320
    mean_y = mean_y - 256

    delta_x = mean_x * 2*two_click_low.pix_per_um.get()
    delta_cam_y = mean_y * 2*two_click_low.pix_per_um.get()
    logger.info("Calculated delta")
    

    omega: float = gonio.o.user_readback.get()
    sample_detection["face_on_omega"] = omega

    real_y = delta_cam_y * np.cos(np.deg2rad(omega))
    real_z = delta_cam_y * np.sin(np.deg2rad(omega))

    yield from mvr_with_retry(gonio.gx, delta_x)
    yield from mvr_with_retry(gonio.py, -real_y)
    yield from mvr_with_retry(gonio.pz, -real_z)
    logger.info("Moving sample to center")
    # The sample has moved to the center of the beam (hopefully), need to update co-ordinates

    # orthogonal face, use loop model only if predicted width matches face on
    # otherwise, threshold
    yield from bps.mv(gonio.o, sample_detection["face_on_omega"]+90)
    yield from trigger_two_click()

    try:
        yield from bp.count([two_click_low], 1)
    except FailedStatus:
        yield from bp.count([two_click_low], 1)
    
    loop_detector.get_threshold.set(True)
    loop_detector.x_start.set(int(box_coords_face[0]-mean_x))
    loop_detector.x_end.set(int(box_coords_face[2]-mean_x))
    loop_detector.filename.set(two_click_low.jpeg.full_file_name.get())
    
    scan_uid = yield from bp.count([loop_detector], 1)
    box_coords_ortho = db[scan_uid].table()['loop_detector_box'][1]
    box_coords_ortho_threshold = db[scan_uid].table()['loop_detector_thresholded_box'][1]
    mean_y_threshold = (box_coords_ortho_threshold[1] + box_coords_ortho_threshold[3]) / 2
    small_box_height_threshold = (box_coords_ortho_threshold[3] - box_coords_ortho_threshold[1]) * 2 * two_click_low.pix_per_um.get()

    try:
        mean_y = (box_coords_ortho[1] + box_coords_ortho[3]) / 2
        sample_detection["small_box_height"] = (box_coords_ortho[3] - box_coords_ortho[1]) * 2 * two_click_low.pix_per_um.get()
                # sum of squared difference, face-on vs. ortho width similarity
        ssd_ratio = (
            ((box_coords_face[0]-mean_x - box_coords_ortho[0])**2 +
            (box_coords_face[2]-mean_x - box_coords_ortho[2])**2)
        ) / (box_coords_face[0]-mean_x - box_coords_face[2]-mean_x)**2

    except IndexError:
        logger.error("Orthogonal loop detection failed")
        mean_y = mean_y_threshold
        ssd_ratio = 10000

    if ssd_ratio > 0.2:
        logger.info(f'ssd_ratio of {ssd_ratio}, thresholding for loop sideview')
        mean_y = mean_y_threshold
        sample_detection["small_box_height"] = small_box_height_threshold
        if mean_y == -1:
            logger.error('threshold of -1 detected, something is wrong')
            sample_detection["sample_detected"] = False
            yield from bps.mvr(gonio.o, -90)
            return 

    delta_cam_y = (mean_y - 256) * 2*two_click_low.pix_per_um.get()
    omega = gonio.o.user_readback.get()
    d = np.pi/180

    real_y = delta_cam_y * np.cos(omega * d)
    real_z = delta_cam_y * np.sin(omega * d)

    yield from mvr_with_retry(gonio.py, -real_y)
    yield from mvr_with_retry(gonio.pz, -real_z)
    yield from mv_with_retry(gonio.o, sample_detection["face_on_omega"])

    sample_detection["center_x"] = gonio.gx.user_readback.get()
    sample_detection["center_y"] =  gonio.py.user_readback.get()
    sample_detection["center_z"] = gonio.pz.user_readback.get()
    logger.info("Saving gonio x,y,z spositions")

    sample_detection["sample_detected"] = True
