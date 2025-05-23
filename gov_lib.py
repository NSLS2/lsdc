from config_params import GOVERNOR_TIMEOUT, LOW_MAG_GAIN, LOW_MAG_EXP_TIME, LOW_MAG_GAIN_DA, LOW_MAG_EXP_TIME_DA
from ophyd.utils.errors import StatusTimeoutError, WaitTimeoutError
import ophyd
from ophyd import StatusBase
from beamline_support import setPvValFromDescriptor as setPvDesc
import daq_utils
from daq_utils import getBlConfig
import logging
logger = logging.getLogger(__name__)

def set_detz_in(gov_robot, distance):
    gov_robot.dev.dz.target_In.set(distance)

def set_detz_out(gov_robot, distance):
    gov_robot.dev.dz.target_Out.set(distance)

def setGovRobot(gov_robot, state, wait=True):
  try:
    logger.info(f"setGovRobot{state}")
    if gov_robot.state.get() == state:
        logger.warning(f'governor already in state:  {state}')
    if gov_robot.state.get() == "M" and state != "SE":
        raise Exception(f'Governor can not transition from M to {state}')
    govStatus = gov_robot.set(state)
    # TODO ophyd object should check that the request is a valid state transition
    if wait:
      waitGov(govStatus)
    if wait and govStatus.success and gov_robot.state.get() != state:
      raise Exception(f'Did not reach expected state "{state}". actual state is "{gov_robot.state.get()}"')
    if ((wait and govStatus.success) or not wait) and state in ["SA", "DA", "DI", "SE"]:
      toggleLowMagCameraSettings(state)
    return govStatus
  except Exception as e:
    logger.error(f"Governor did not reach {state}: exception {e}")
    govStatus = StatusBase()
    govStatus.set_exception(e)
    return govStatus

def waitGov(status, timeout=GOVERNOR_TIMEOUT):
  try:
    # TODO add callback for periodic updates
    ophyd.status.wait(status, timeout)
  except (StatusTimeoutError, WaitTimeoutError) as e:
    message = 'Governor Timeout!'
    logger.error(message)
    #gui_message(message)

def waitGovNoSleep(timeout=GOVERNOR_TIMEOUT):
  pass

def toggleLowMagCameraSettings(stateCode):
  if (stateCode == "DA"):
    setPvDesc("lowMagGain", getBlConfig(LOW_MAG_GAIN_DA))
    setPvDesc("lowMagAcquireTime",getBlConfig(LOW_MAG_EXP_TIME_DA))
  else:
    setPvDesc("lowMagGain", getBlConfig(LOW_MAG_GAIN))
    setPvDesc("lowMagAcquireTime",getBlConfig(LOW_MAG_EXP_TIME))
