import time
from beamline_support import getPvValFromDescriptor as getPvDesc, setPvValFromDescriptor as setPvDesc
import logging
from start_bs import robot, RE
from config_params import MOUNT_STEP_SUCCESSFUL, UNMOUNT_STEP_SUCCESSFUL, MOUNT_SUCCESSFUL, UNMOUNT_SUCCESSFUL
from denso_robot import OphydRobot
from threading import Thread
logger = logging.getLogger(__name__)

def mountRobotSample(gov_robot, puck_pos, pin_pos, samp_id, **kwargs):
  status, kwargs = robot.preMount(gov_robot, puck_pos, pin_pos, samp_id, **kwargs)  # TODO return governor status, send to mount function so embl robot can use it if necessary
  if status != MOUNT_STEP_SUCCESSFUL:
      return status
  if robot.control_type() == "Bluesky":
    logger.info('bluesky robot')
    RE(robot.mount(gov_robot, puck_pos, pin_pos, samp_id, **kwargs))
  else:
    logger.info('regular robot')
    status = robot.mount(gov_robot, puck_pos, pin_pos, samp_id, **kwargs)
    if status is not MOUNT_STEP_SUCCESSFUL:
        return status
  if isinstance(robot, OphydRobot):
    status = robot.check_sample_mounted(mount=True, puck_pos=puck_pos, pin_pos=pin_pos)
  else:
    status = MOUNT_STEP_SUCCESSFUL
  if status != MOUNT_STEP_SUCCESSFUL:
      return status
  status = robot.postMount(gov_robot, puck_pos, pin_pos, samp_id)
  return status

def unmountRobotSample(gov_robot, puck_pos, pin_pos, samp_id):
  status = robot.preUnmount(gov_robot, puck_pos, pin_pos, samp_id)
  if status != UNMOUNT_STEP_SUCCESSFUL:
      return status
  
  if robot.control_type() == "Bluesky":
    RE(robot.unmount(gov_robot, puck_pos, pin_pos, samp_id))
  
  if isinstance(robot, OphydRobot):
    status = robot.check_sample_mounted(mount=False, puck_pos=puck_pos, pin_pos=pin_pos)
  else:
    status = robot.unmount(gov_robot, puck_pos, pin_pos, samp_id)
  return status


def finish():
    robot.finish()

def recoverRobot():
    robot.recoverRobot()

def dryGripper():
    robot.dryGripper()

# TODO ask Edwin about these Dewar functions

def DewarRefill(hours):
  global _dewarRefillThread
  seconds = int((hours * 60 * 60))
  try:
    if _dewarRefillThread is not None:
      if _dewarRefillThread.is_alive():
        logger.info("An existing DewarRefillTask is already running.")
        return
  except NameError:
    logger.info("_dewarRefillThread not defined - this is ok, conntinuing with dewar refill task")
  _dewarRefillThread = Thread(target=_dewarRefillTask, args=(seconds,))
  _dewarRefillThread.start()

def _dewarRefillTask(seconds):
  global dewarRefillStop
  DewarAutoFillOff()
  DewarHeaterOn()
  dewarRefillStop = 0
  start_time = time.time()
  goal_time = time.time() + (seconds)
  while not dewarRefillStop:
    if time.time() < goal_time:
      time_remaining = round(((goal_time - time.time()) / 60), 1)
      logger.info(f"DewarRefillTask: Time remaining until auto fill on... {time_remaining} minutes")
      time.sleep(60)
    else:
      logger.info("DewarRefillTask running.")
      DewarAutoFillOn()
      DewarHeaterOn()
      return
  logger.info("DewarRefillTask cancelled.")
  dewarRefillStop = 0

def multiSampleGripper():
    return robot.multiSampleGripper()

def DewarRefillCancel():
  global dewarRefillStop
  logger.info("DewarRefillTask cancelling...")
  dewarRefillStop = 1

def DewarAutoFillOn():
    robot.DewarAutoFillOn()

def DewarAutoFillOff():
    robot.DewarAutoFillOff()

def DewarHeaterOn():
    robot.DewarHeaterOn()

def DewarHeaterOff():
    robot.DewarHeaterOff()

def warmupGripper():
    robot.warmupGripper()

def enableDewarTscreen():
    robot.enableDewarTscreen()

def openPort(portNo):
    robot.openPort(portNo)

def closePorts():
    robot.closePorts()

def rebootEMBL():
    robot.rebootEMBL()

def parkRobot():
    robot.parkRobot()

def parkGripper():
    robot.parkGripper()

def testRobot():
    robot.testRobot()

def openGripper():
    robot.openGripper()

def closeGripper():
    robot.closeGripper()

def cooldownGripper():
  robot.cooldownGripper()