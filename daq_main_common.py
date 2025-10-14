import _thread
import atexit
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
global command_list,immediate_command_list,z
command_list = []
immediate_command_list = []
z = 25

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
    robotOn,
    set_energy
    ]

if daq_utils.beamline != "nyx":
  functions = functions + [anneal]

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
  logger.info("init mots")
  beamline_lib.init_mots()    #for now
  logger.info("init done mots")
  daq_lib.init_diffractometer()
  try:
    sitefilename = os.environ["LSDC_SITE_FILE"]
  except KeyError:
    gui_message("\$LSDC_SITE_FILE not defined. Questionable defaults in effect.")
  if (sitefilename != ""):    
    if (os.path.exists(sitefilename) == 0):
      error_msg = "\$LSDC_SITE_FILE: %s does not exist. Questionable defaults in effect." % sitefilename
      gui_message(error_msg)
    else:
      process_command_file(sitefilename)


def process_command_file(command_file_name):
  echo_s =  "reading %s\n" % command_file_name
  logger.info(echo_s)
  command_file = open(command_file_name,"r")  
  while 1:
    command = command_file.readline()
    if not command:
      break
    else:
      input_tokens = string.split(command)
      if (len(input_tokens)>0):
        command_string = "%s(" % input_tokens[0]
        for i in range(1,len(input_tokens)):
          command_string = command_string + "\"" + input_tokens[i] + "\""
          if (i != (len(input_tokens)-1)):
            command_string = command_string + ","
        command_string = command_string + ")"
      logger.info(command_string)
      try:
        exec(command_string);    
      except NameError as e:
        error_string = "Unknown command in file: %s Error: %s" % (command_string, e)
        logger.error(error_string)
      except SyntaxError:
        logger.error("Syntax error")
      except KeyError as e:
        logger.error("Key error. Error: %s" % e)
  command_file.close()
  


def process_immediate_commands(frequency):
  while (1):
    if (len(immediate_command_list) > 0):
      command = immediate_command_list.pop(0)
      logger.info('immediate command: %s' % command)
      process_input(command)
    time.sleep(frequency)      

def process_commands(frequency):
  while (1):
    if (len(command_list) > 0):
      command = command_list.pop(0)
      logger.info('command: %s' % command)
      process_input(command)

    
def print_status_thread(frequency):
  global count_list,ring_intensity

  previous_image_started = 0
  percent_done = 0
  shutter_dead_time = .6
  while 1:
    time.sleep(frequency)
    current_percent_done = daq_lib.get_field("state_percent")
    if (daq_lib.image_started > 0):
      if (start_time == 0 or daq_lib.image_started != previous_image_started):
        previous_image_started = daq_lib.image_started
        start_time = time.time()
      now = time.time()
      total_time = float(daq_lib.image_started)
      if (total_time>0.0):
        percent_done = int(.5+((now-start_time)/total_time*100))
      else:
        percent_done = 0
    else:
      start_time = 0
      percent_done = 0
    if (percent_done != current_percent_done):
      daq_lib.set_field("state_percent",percent_done)


def comm_cb(value=None, char_value=None, **kw):
  command = char_value
  command_list.append(command)
  
def comm2_cb(value=None, char_value=None, **kw):
  command = char_value
  if not (command == "\n"):
    immediate_command_list.append(command)
  


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
  if (command_string != "pause_data_collection()" and command_string != "continue_data_collection()" and command_string != "abort_data_collection()" and command_string != "unmount_after_abort()" and command_string != "no_unmount_after_abort()"):
    daq_lib.set_field("program_state","Program Ready")


def run_server():
  _thread.start_new_thread(process_immediate_commands,(.25,))  
  comm_pv = beamline_support.pvCreate(daq_utils.beamlineComm + "command_s")
  beamline_support.pvPut(comm_pv,"\n")
  immediate_comm_pv = beamline_support.pvCreate(daq_utils.beamlineComm + "immediate_command_s")
  beamline_support.pvPut(immediate_comm_pv,"\n")  
  comm_pv.add_callback(comm_cb)
  immediate_comm_pv.add_callback(comm2_cb)
  process_commands(0.5)
