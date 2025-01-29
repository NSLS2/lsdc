from logging import getLogger

import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np
from bluesky.preprocessors import finalize_decorator
from bluesky.utils import FailedStatus
from ophyd.utils import WaitTimeoutError, StatusTimeoutError
from scipy.interpolate import interp1d
from sklearn.linear_model import LinearRegression, RANSACRegressor
import gov_lib
from mxbluesky.devices.top_align import GovernorError, CamMode
from mxbluesky.plans.utils import mv_with_retry, mvr_with_retry
from start_bs import (
    db,
    gonio,
    gov_robot,
    mount_pos,
    top_aligner_fast,
    top_aligner_slow,
    work_pos,
    top_cam_reset_signal
)

logger = getLogger()

def cleanup_topcam():
    try:
        yield from bps.abs_set(top_aligner_slow.cam.acquire, 1, wait=True, timeout=4)
        yield from bps.abs_set(top_aligner_fast.zebra.pos_capt.direction, 0, wait=True, timeout=4)
    except WaitTimeoutError as error:
        logger.exception(f"Exception in cleanup_topcam, trying again: {error}")
        yield from bps.abs_set(top_aligner_slow.cam.acquire, 1, wait=True, timeout=4)
        yield from bps.abs_set(top_aligner_fast.zebra.pos_capt.direction, 0, wait=True, timeout=4)
    

def inner_pseudo_fly_scan(*args, **kwargs):
    scan_uid = yield from bp.count(*args, **kwargs)
    omegas = db[scan_uid].table()[
        top_aligner_fast.zebra.pos_capt.data.enc4.name
    ][1]

    d = np.pi / 180

    # rot axis calculation, use linear regression
    
    omegas_rad = np.array(omegas) * d
    X = np.vstack([np.cos(omegas_rad), np.sin(omegas_rad)]).T

    y = np.array(db[scan_uid].table()[top_aligner_fast.topcam.out9_buffer.name][
        1
    ]).reshape(-1,1)
    try:
        ransac_kwargs = {
            'estimator': LinearRegression(),
            'min_samples': 5,
            'residual_threshold': 10,
            'random_state': 0,
        }
        delta_z_pix, delta_y_pix = fit_ransac_linear(X, y, **ransac_kwargs)
    except ValueError as e:
        logger.error(f"Error using RANSAC estimator: {e}. Using linear instead")
        delta_z_pix, delta_y_pix = fit_linear(X, y)

    print(f"Ransac Regression predictions: {delta_z_pix}, {delta_y_pix}")
    
    delta_y, delta_z = (
        delta_y_pix / top_aligner_fast.topcam.pix_per_um.get(),
        delta_z_pix / top_aligner_fast.topcam.pix_per_um.get(),
    )
    
    # face on calculation
    b = db[scan_uid].table()[top_aligner_fast.topcam.out10_buffer.name][1]

    sample = 300
    f_splines = interp1d(omegas, b)
    b_splines = f_splines(np.linspace(omegas[0], omegas[-1], sample))
    omega_min = np.linspace(omegas[0], omegas[-1], sample)[
        b_splines.argmin()
    ]
    logger.debug(f"SPLINES / {omega_min}")

    """
    if (-2000 < delta_y[[0]] < 2000) or (-2000 < delta_z[[0]] < 2000):
        raise ValueError(f"Calculated Delta y or z too large {delta_y=} {delta_z=}")
    """
    

    return delta_y, delta_z, omega_min

def setup_transition_signals(target_state, zebra_dir, cam_mode):
    yield from bps.abs_set(top_aligner_fast.target_gov_state, target_state, wait=True)
    yield from bps.abs_set(top_aligner_fast.zebra.pos_capt.direction, zebra_dir, wait=True, timeout=4)
    yield from bps.abs_set(top_aligner_fast.topcam.cam_mode, cam_mode, wait=True, timeout=4)
    yield from bps.sleep(0.1)

def reset_top_cam():
    yield from bps.abs_set(top_aligner_slow.cam.acquire, 0, wait=True)
    yield from bps.sleep(3)
    yield from bps.abs_set(top_cam_reset_signal, 1, wait=True)
    yield from bps.sleep(12)
    n = 1
    # sometimes array_callbacks not setup properly, need to find out why
    while top_aligner_slow.cam.array_callbacks.get() != 1 and n <= 10:
        yield from bps.abs_set(top_cam_reset_signal, 1, wait=True)
        yield from bps.sleep(12)
        logger.info(f'rebooting topcam after {n} out of 10 attempts')
        n += 1
    yield from bps.abs_set(top_aligner_slow.cam.acquire, 1, wait=True)
    yield from bps.sleep(3) # Sleeping here to prevent interference with count

@finalize_decorator(cleanup_topcam)
def topview_optimized():
    logger.info("Starting topview --")
    try:
        # horizontal bump calculation, don't move just yet to avoid disturbing gov
        scan_uid = yield from bp.count([top_aligner_slow], 1)
    except (FailedStatus, WaitTimeoutError, StatusTimeoutError) as e:
        yield from reset_top_cam()
        scan_uid = yield from bp.count([top_aligner_slow], 1)

    logger.info(f"Finished top aligner slow scan {scan_uid}")
    x = db[scan_uid].table()[top_aligner_slow.cv1.outputs.output8.name][1]
    delta_x = ((top_aligner_slow.roi2.size.x.get() / 2) -
               x) / top_aligner_slow.pix_per_um.get()
    logger.info(f"Horizontal bump calc finished: {delta_x}")
    # update work positions
    yield from set_TA_work_pos(delta_x=delta_x)
    logger.info("Updated TA work pos, starting transition to TA")

    # SE -> TA
    try:
        yield from setup_transition_signals("TA", 0, CamMode.COARSE_ALIGN.value)
    except WaitTimeoutError as error:
        logger.exception(f"Exception while setting SE to TA signals, trying again: {error}")
        yield from setup_transition_signals("TA", 0, CamMode.COARSE_ALIGN.value)
        
    logger.info("Starting 1st inner fly scan")

    try:
        delta_y, delta_z, omega_min = yield from inner_pseudo_fly_scan(
            [top_aligner_fast]
        )
    except (FailedStatus, WaitTimeoutError, GovernorError, ValueError) as error:
        print(f"Error: {error}")
        print("arming problem during coarse alignment...trying again")

        yield from bps.sleep(15)
        yield from bps.abs_set(gov_robot, 'SE', wait=True)
        yield from bps.abs_set(top_aligner_fast.zebra.reset, 1, wait=True)
        yield from bps.sleep(4)  # 2-3 sec will disarm zebra after reset

        delta_y, delta_z, omega_min = yield from inner_pseudo_fly_scan(
            [top_aligner_fast]
        )
    logger.info("Ended 1st inner fly scan, starting gonio move")
    yield from mvr_with_retry(top_aligner_fast.gonio_py, delta_y)
    yield from mvr_with_retry(top_aligner_fast.gonio_pz, -delta_z)
    logger.info("Finished move, setting SA work pos")
    # update work positions
    yield from set_SA_work_pos(delta_y, delta_z)
    logger.info("Starting transition to SA")
    # TA -> SA
    try:
        yield from setup_transition_signals("SA", 1, CamMode.FINE_FACE.value)
    except WaitTimeoutError as error:
        logger.exception(f"Exception while setting TA to SA signals, trying again: {error}")
        yield from setup_transition_signals("SA", 1, CamMode.FINE_FACE.value)

    logger.info("Starting 2nd inner fly scan")
    try:
        delta_y, delta_z, omega_min = yield from inner_pseudo_fly_scan(
            [top_aligner_fast]
        )
    except (FailedStatus, WaitTimeoutError, GovernorError, ValueError) as error:
        print(f"Error: {error}")
        print("arming problem during fine alignment...trying again")
        yield from bps.sleep(15)
        # update work positions for TA reset
        yield from set_TA_work_pos()
        yield from bps.abs_set(gov_robot, 'TA', wait=True)
        yield from bps.abs_set(top_aligner_fast.zebra.reset, 1, wait=True)

        # update work positions for TA -> SA retry
        yield from set_SA_work_pos(delta_y, delta_z)
        yield from bps.sleep(4)  # 2-3 sec will disarm zebra after reset

        delta_y, delta_z, omega_min = yield from inner_pseudo_fly_scan(
            [top_aligner_fast]
        )
    logger.info("Finished 2nd inner fly scan, moving gonio")
    yield from mv_with_retry(top_aligner_fast.gonio_o, omega_min)
    yield from mvr_with_retry(top_aligner_fast.gonio_py, delta_y)
    yield from mvr_with_retry(top_aligner_fast.gonio_pz, -delta_z)
    logger.info("Finished gonio move setting SA work pos")
    set_SA_work_pos(delta_y, delta_z, gonio.py.user_readback.get(), gonio.pz.user_readback.get(), omega=gonio.o.user_readback.get())
    logger.info("Completed topview optimized")

def set_TA_work_pos(delta_x=None):
    if delta_x:
        yield from bps.abs_set(work_pos.gx, mount_pos.gx.get() + delta_x, wait=True)
    yield from bps.abs_set(
        work_pos.gpy, mount_pos.py.get(), wait=True
    )
    yield from bps.abs_set(
        work_pos.gpz, mount_pos.pz.get(), wait=True
    )
    yield from bps.abs_set(work_pos.o, 180, wait=True)

def set_SA_work_pos(delta_y, delta_z, current_y=None, current_z= None, omega=0):
    if current_y is None:
        current_y = mount_pos.py.get()
    if current_z is None:
        current_z = mount_pos.pz.get()
    yield from bps.abs_set(
        work_pos.gpy, current_y + delta_y, wait=True
    )
    yield from bps.abs_set(
        work_pos.gpz, current_z - delta_z, wait=True
    )
    yield from bps.abs_set(work_pos.o, omega, wait=True)

def fit_linear(X,y):
    reg = LinearRegression().fit(X,y)
    return reg.coef_[0]

def fit_ransac_linear(X,y, min_n_inliers=10, **kwargs):
    reg = RANSACRegressor(**kwargs).fit(X,y)
    mask = reg.inlier_mask_
    masked_X = X[mask, :]
    masked_y = y[mask, :]
    if len(masked_y) < min_n_inliers:
        raise ValueError(
            f'Too few inliers. Identified {len(masked_y)}, need {min_n_inliers}.'
        )
    return reg.estimator_.coef_[0]
