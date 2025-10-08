import json
import logging
import os
import string
import sys
import time
import traceback

import beamline_lib
import beamline_support
import config_params
import daq_lib
import daq_utils
import det_lib
from beamline_lib import *
from daq_lib import *

#imports to get useful things into namespace for server
from daq_macros import *
from gov_lib import setGovRobot
from robot_lib import *
from start_bs import gov_robot, plt

logger = logging.getLogger(__name__)

sitefilename = ""

def setGovState(state):
  setGovRobot(gov_robot, state)

functions = [
    set_beamsize,
    importSpreadsheet,
    mvaDescriptor,
    setTrans,
    loop_center_xrec,
    autoRasterLoop,
    snakeRaster,
    backlightBrighter,
    backlightDimmer,
    changeImageCenterHighMag,
    changeImageCenterLowMag,
    center_on_click,
    runDCQueue,
    warmupGripper,
    dryGripper,
    enableDewarTscreen,
    parkGripper,
    stopDCQueue,
    continue_data_collection,
    mountSample,
    unmountSample,
    reprocessRaster,
    fastDPNodes,
    spotNodes,
    unmountCold,
    openPort,
    set_beamcenter,
    closePorts,
    clearMountedSample,
    recoverRobot,
    rebootEMBL,
    restartEMBL,
    openGripper,
    closeGripper,
    homePins,
    setSlit1X,
    setSlit1Y,
    testRobot,
    setGovState,
    move_omega,
    lockGUI,
    unlockGUI,
    DewarAutoFillOff,
    DewarAutoFillOn,
    logMe,
    unlatchGov,
    backoffDetector,
    enableMount,
    disableMount,
    robotOn,
    set_cryostream_ramp_rate,
    set_cryostream_temp,
    robotOff,
    set_energy,
    insertRasterResult,
    anneal,
    ]

whitelisted_functions: "Dict[str, Callable]" = {
    func.__name__: func for func in functions
}
  
def execute_command(command_s):
  logger.info("executing command: %s" % command_s)
  try:
      command: "dict[str, Any]" = json.loads(command_s)
      func = whitelisted_functions[command["function"]]
  except Exception as e:
      logger.exception(f"Error in function parsing and lookup: {e}")
  
  try:
      func(*command["args"], **command["kwargs"])
  except Exception as e:
      logger.exception(f"Error executing {command_s}: {e}")


def pybass_init():
  global message_string_pv

  daq_utils.init_environment()
  daq_lib.init_var_channels()
  if getBlConfig(config_params.DETECTOR_OBJECT_TYPE) != config_params.DETECTOR_OBJECT_TYPE_NO_INIT:
    det_lib.init_detector()  
  daq_lib.message_string_pv = beamline_support.pvCreate(daq_utils.beamlineComm + "message_string")    
  daq_lib.gui_popup_message_string_pv = beamline_support.pvCreate(daq_utils.beamlineComm + "gui_popup_message_string")    
  beamline_lib.read_db()
  beamline_lib.init_mots()
  daq_lib.init_diffractometer()


def process_input(command_string):
  if (command_string == ""):
    return
  if (command_string == "q"):
    sys.exit()
  daq_lib.broadcast_output(time.ctime(time.time()) + "\n" + command_string)      
  try:
    daq_lib.set_field("program_state","Program Busy")
    execute_command(command_string)
  except NameError as e:
    error_string = "Unknown command in queue: %s Error: %s" % (command_string, e)
    logger.error(error_string)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("*** print_tb:")
    traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
  except SyntaxError:
    logger.exception("Syntax error")
  except KeyError as e:
    logger.exception("Key error. Error: %s. Command was: %s" % (e, command_string))
  except TypeError as e:
    logger.exception("Type error. Error: %s" % e)
  except AttributeError as e:
    logger.error("Attribute Error: %s" % e)
  except KeyboardInterrupt:
    abort_data_collection()
    logger.info("Interrupt caught by daq server\n")
  daq_lib.set_field("program_state","Program Ready")

