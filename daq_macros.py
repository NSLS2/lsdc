import Gen_Commands
import Gen_Traj_Square
import beamline_support
from beamline_support import getPvValFromDescriptor as getPvDesc, setPvValFromDescriptor as setPvDesc
import beamline_lib #did this really screw me if I imported b/c of daq_utils import??
import daq_lib
import daq_utils
import db_lib
from daq_utils import getBlConfig, setBlConfig
from utils.raster import get_raster_max_col, get_flattened_indices_of_max_col
import det_lib
import math
import time
import glob
import xmltodict
from start_bs import *
import super_state_machine
import _thread
import parseSheet
import attenCalc
import raddoseLib
import robot_lib
from raddoseLib import *
import logging
logger = logging.getLogger(__name__)
import os #for runDozorThread
import numpy as np # for runDozorThread
from string import Template
from collections import OrderedDict
from threading import Thread
from config_params import *
from ophyd.status import SubscriptionStatus
from ophyd.utils import WaitTimeoutError
from kafka_producer import send_kafka_message

import gov_lib
import urllib.request
import io

from scans import (zebra_daq_prep, setup_zebra_vector_scan,
                   setup_zebra_vector_scan_for_raster,
                   setup_vector_program)
import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.preprocessors import finalize_wrapper
from bluesky.log import config_bluesky_logging
config_bluesky_logging(level='INFO')
from fmx_annealer import govStatusGet, govStateSet, fmxAnnealer, amxAnnealer # for using annealer specific to FMX and AMX
from config_params import ON_MOUNT_OPTION, OnMountAvailOptions, BEAMSIZE_OPTIONS
from mxbluesky.plans import detect_loop, topview_optimized

if daq_utils.beamline == 'fmx':
  from setenergy_lsdc import setELsdc


try:
  import ispybLib
except Exception as e:
  logger.error("daq_macros: ISPYB import error, %s" % e)
  
from XSDataMXv1 import XSDataResultCharacterisation
global rasterRowResultsList, processedRasterRowCount
global ednaActiveFlag

ednaActiveFlag = 0

global autoRasterFlag
autoRasterFlag = 0

rasterRowResultsList = []

global autoVectorFlag, autoVectorCoarseCoords
autoVectorCoarseCoords = {}
autoVectorFlag=False

max_col = None
face_on_max_coords = None
ortho_max_coords = None

C3D_SEARCH_BASE = f'{os.environ["PROJDIR"]}/software/c3d/c3d_search -p=$CONFIGDIR/'

IMAGES_PER_FILE = 500 # default images per HDF5 data file for Eiger
EXTERNAL_TRIGGER = 2 # external trigger for detector
#12/19 - general comments. This file takes the brunt of the near daily changes and additions the scientists request. Some duplication and sloppiness reflects that.
# I'm going to leave a lot of the commented lines in, since they might shed light on things or be useful later.

def hi_macro():
  logger.info("hello from macros\n")
  daq_lib.broadcast_output("broadcast hi")


def BS():
  movr(omega,40)

def BS2():
  ascan(omega,0,100,10)

def abortBS():
  if (RE.state != "idle"):
    try:
      RE.abort()
    except super_state_machine.errors.TransitionError:
      logger.error("caught BS")
  
def set_energy(energy):
  try:
    daq_lib.set_field("program_state","Setting Energy")
    RE(setELsdc(energy))
  except Exception as e:
    logger.error(f"Exception while running set_energy: {e}")
    daq_lib.set_field("program_state","Program Ready")

def move_omega(omega, relative=True):
  """Moves omega by a certain amount"""
  if gov_robot.state.get() == "SA":
    if relative:
      RE(bps.mvr(gonio.omega, omega))
    else:
      RE(bps.mv(gonio.omega, omega))

def changeImageCenterLowMag(x,y,czoom):
  zoom = int(czoom)
  zoomMinXRBV = getPvDesc("lowMagZoomMinXRBV")
  zoomMinYRBV = getPvDesc("lowMagZoomMinYRBV")
  minXRBV = getPvDesc("lowMagMinXRBV")
  minYRBV = getPvDesc("lowMagMinYRBV")
  
  sizeXRBV = getPvDesc("lowMagZoomSizeXRBV")
  sizeYRBV = getPvDesc("lowMagZoomSizeYRBV")
  sizeXRBV = 640.0
  sizeYRBV = 512.0
  roiSizeXRBV = getPvDesc("lowMagROISizeXRBV")
  roiSizeYRBV = getPvDesc("lowMagROISizeYRBV")  
  roiSizeZoomXRBV = getPvDesc("lowMagZoomROISizeXRBV")
  roiSizeZoomYRBV = getPvDesc("lowMagZoomROISizeYRBV")
  inputSizeZoomXRBV = getPvDesc("lowMagZoomMaxSizeXRBV")
  inputSizeZoomYRBV = getPvDesc("lowMagZoomMaxSizeYRBV")      
  inputSizeXRBV = getPvDesc("lowMagMaxSizeXRBV")
  inputSizeYRBV = getPvDesc("lowMagMaxSizeYRBV")      
  x_click = float(x)
  y_click = float(y)
  binningFactor = 2.0  
  if (zoom):
    xclickFullFOV = x_click + zoomMinXRBV
    yclickFullFOV = y_click + zoomMinYRBV
  else:
    binningFactor = 2.0
    xclickFullFOV = (x_click * binningFactor) + minXRBV
    yclickFullFOV = (y_click * binningFactor) + minYRBV    
  new_minXZoom = xclickFullFOV-(sizeXRBV/2.0)
  new_minYZoom = yclickFullFOV-(sizeYRBV/2.0)
  new_minX = new_minXZoom - (sizeXRBV/2.0)
  new_minY = new_minYZoom - (sizeYRBV/2.0)
  noZoomCenterX = sizeXRBV/2.0
  noZoomCenterY = sizeYRBV/2.0  
  if (new_minX < 0):
    new_minX = 0
    noZoomCenterX = (new_minXZoom+(sizeXRBV/2.0))/binningFactor
  if (new_minY < 0):
    new_minY = 0    
    noZoomCenterY = (new_minYZoom+(sizeYRBV/2.0))/binningFactor
  if (new_minX+roiSizeXRBV>inputSizeXRBV):
    new_minX = inputSizeXRBV-roiSizeXRBV    
    noZoomCenterX = ((new_minXZoom+(sizeXRBV/2.0)) - new_minX)/binningFactor
  if (new_minY+roiSizeYRBV>inputSizeYRBV):
    new_minY = inputSizeYRBV-roiSizeYRBV
    noZoomCenterY = ((new_minYZoom+(sizeYRBV/2.0)) - new_minY)/binningFactor    
  if (new_minXZoom+roiSizeZoomXRBV>inputSizeZoomXRBV):
    new_minXZoom = inputSizeZoomXRBV-roiSizeZoomXRBV
  if (new_minXZoom < 0):
    new_minXZoom = 0
  setPvDesc("lowMagZoomMinX",new_minXZoom)    
  if (new_minYZoom+roiSizeZoomYRBV>inputSizeZoomYRBV):
    new_minYZoom = inputSizeZoomYRBV-roiSizeZoomYRBV
  if (new_minYZoom < 0):
    new_minYZoom = 0
  setPvDesc("lowMagZoomMinY",new_minYZoom)        
  setPvDesc("lowMagMinX",new_minX)
  setPvDesc("lowMagMinY",new_minY)    
  setPvDesc("lowMagCursorX",noZoomCenterX)
  setPvDesc("lowMagCursorY",noZoomCenterY)  
      

def changeImageCenterHighMag(x,y,czoom):
  zoom = int(czoom)
  zoomMinXRBV = getPvDesc("highMagZoomMinXRBV")
  zoomMinYRBV = getPvDesc("highMagZoomMinYRBV")
  minXRBV = getPvDesc("highMagMinXRBV")
  minYRBV = getPvDesc("highMagMinYRBV")
  
  sizeXRBV = getPvDesc("highMagZoomSizeXRBV")
  sizeYRBV = getPvDesc("highMagZoomSizeYRBV")
  sizeXRBV = 640.0
  sizeYRBV = 512.0
  roiSizeXRBV = getPvDesc("highMagROISizeXRBV")
  roiSizeYRBV = getPvDesc("highMagROISizeYRBV")  
  roiSizeZoomXRBV = getPvDesc("highMagZoomROISizeXRBV")
  roiSizeZoomYRBV = getPvDesc("highMagZoomROISizeYRBV")
  inputSizeZoomXRBV = getPvDesc("highMagZoomMaxSizeXRBV")
  inputSizeZoomYRBV = getPvDesc("highMagZoomMaxSizeYRBV")      
  inputSizeXRBV = getPvDesc("highMagMaxSizeXRBV")
  inputSizeYRBV = getPvDesc("highMagMaxSizeYRBV")      
  x_click = float(x)
  y_click = float(y)
  binningFactor = 2.0  
  if (zoom):
    xclickFullFOV = x_click + zoomMinXRBV
    yclickFullFOV = y_click + zoomMinYRBV
  else:
    binningFactor = 2.0
    xclickFullFOV = (x_click * binningFactor) + minXRBV
    yclickFullFOV = (y_click * binningFactor) + minYRBV    
  new_minXZoom = xclickFullFOV-(sizeXRBV/2.0)
  new_minYZoom = yclickFullFOV-(sizeYRBV/2.0)
  new_minX = new_minXZoom - (sizeXRBV/2.0)
  new_minY = new_minYZoom - (sizeYRBV/2.0)
  noZoomCenterX = sizeXRBV/2.0
  noZoomCenterY = sizeYRBV/2.0  
  if (new_minX < 0):
    new_minX = 0
    noZoomCenterX = (new_minXZoom+(sizeXRBV/2.0))/binningFactor
  if (new_minY < 0):
    new_minY = 0    
    noZoomCenterY = (new_minYZoom+(sizeYRBV/2.0))/binningFactor
  if (new_minX+roiSizeXRBV>inputSizeXRBV):
    new_minX = inputSizeXRBV-roiSizeXRBV    
    noZoomCenterX = ((new_minXZoom+(sizeXRBV/2.0)) - new_minX)/binningFactor
  if (new_minY+roiSizeYRBV>inputSizeYRBV):
    new_minY = inputSizeYRBV-roiSizeYRBV
    noZoomCenterY = ((new_minYZoom+(sizeYRBV/2.0)) - new_minY)/binningFactor    

  if (new_minXZoom+roiSizeZoomXRBV>inputSizeZoomXRBV):
    new_minXZoom = inputSizeZoomXRBV-roiSizeZoomXRBV
  if (new_minXZoom < 0):
    new_minXZoom = 0
  if (new_minYZoom+roiSizeZoomYRBV>inputSizeZoomYRBV):
    new_minYZoom = inputSizeZoomYRBV-roiSizeZoomYRBV
  if (new_minYZoom < 0):
    new_minYZoom = 0
  setPvDesc("highMagZoomMinX",new_minXZoom)
  setPvDesc("highMagZoomMinY",new_minYZoom)
  setPvDesc("highMagMinX",new_minX)
  setPvDesc("highMagMinY",new_minY)    
  setPvDesc("highMagCursorX",noZoomCenterX)
  setPvDesc("highMagCursorY",noZoomCenterY)

sample_detection = {
  "sample_detected": False,
  "large_box_width": 0,
  "large_box_height": 0,
  "small_box_height": 0,
  "center_x" : 0,
  "center_y" : 0,
  "center_z" : 0,
  "face_on_omega" : 0
}

def run_robot_recovery_procedure():
  """ Generic recovery procedure to be used during automated
  collection"""
  # Recover robot
  logging.info("Running robot recovery procedure (nuclear option)")
  logger.info("Recovering robot")
  robot_lib.recoverRobot()
  # Dry Gripper
  logger.info("Drying gripper")
  robot_lib.dryGripper()
  # Dry Gripper
  logger.info("Drying gripper, again")
  robot_lib.dryGripper()
  # Park Gripper and cool gripper
  logger.info("Cooling gripper")
  robot_lib.cooldownGripper()
  logger.info("Homing pins")
  from start_bs import home_pins
  RE(home_pins())
  logger.info("Setting robot state to SE")
  gov_lib.setGovRobot(gov_robot, 'SE')
  logger.info("Turning govmon ON")
  daq_lib.govMonOn()

def recoverCS8():
  logger.info("Starting CS8 recovery")
  logger.info("Recovering robot")
  robot_lib.recoverRobot()
  logger.info("Drying gripper")
  robot_lib.dryGripper()
  rotCP = beamline_lib.motorPosFromDescriptor("dewarRot")
  logger.info(f"Rotate dewar +1 degree, from {rotCP} to {rotCP+1}")
  beamline_lib.mvaDescriptor("dewarRot",rotCP + 1)
  logger.info(f"Rotate dewar -1 degree, from {rotCP+1} to {rotCP}")
  beamline_lib.mvaDescriptor("dewarRot",rotCP)
  logger.info("Setting robot state to SE")
  gov_lib.setGovRobot(gov_robot, 'SE')
  logger.info("Setting robot state to M")
  gov_lib.setGovRobot(gov_robot, 'M')
  logger.info("Setting robot state to SE")
  gov_lib.setGovRobot(gov_robot, 'SE')

def run_recovery_procedure(stop=True):
  """
  Manual recovery procedure used in daq_lib.flocoStopOperations and daq_lib.flocoContinueOperations
  """
  logger.info(f"Running recovery procedure: {'stop operations' if stop else 'continue operations'}")
  def check_robot():
    if not getBlConfig("robot_online") or not getBlConfig("mountEnabled"):
      raise ValueError("Robot is offline or mount is disabled, sample found in gripper. Stopping recovery...")

  def run_home_pin():
    from start_bs import home_pins
    RE(home_pins())
  
  def gov_state_to_se():
    gov_lib.setGovRobot(gov_robot, 'SE')
  
  def check_robot_speed():
    if not robot_arm.is_full_speed():
      logger.error("Robot arm speed is NOT 100%")

  def check_beam():
    if not (getPvDesc("beamAvailable") or getBlConfig(BEAM_CHECK) == 0):
      logger.error("Beam not available, please open shutter")

  steps_to_run = {"Recover robot": robot_lib.recoverRobot, 
                  "Check robot status": check_robot, 
                  "Dry gripper": robot_lib.dryGripper, 
                  "Home pin": run_home_pin, }
  if stop:
    steps_to_run.update({"Disable mount": disableMount, "Robot off": robotOff})
  else:
    steps_to_run.update({"Enable mount": enableMount, "Robot on": robotOn})
  
  steps_to_run.update({"Move Governor to SE": gov_state_to_se, 
                       "Checking robot arm speed": check_robot_speed,
                       "Checking beam": check_beam})

  for i, (step_message, func) in enumerate(steps_to_run.items()):
    logger.info(f"Step {i+1} of {len(steps_to_run)}: {step_message}")
    func()
    logger.info(f"Completed step: {step_message}")
  

def run_top_view_optimized():
    RE(topview_optimized())

def run_on_mount_option(sample_id):
    option = OnMountAvailOptions(daq_utils.getBlConfig(ON_MOUNT_OPTION))
    logger.info(f"Running on mount option : {option}")
    request = {}

    if option == OnMountAvailOptions.DO_NOTHING:
      return
    
    if (option == OnMountAvailOptions.CENTER_SAMPLE 
        or option == OnMountAvailOptions.AUTO_RASTER):
      # Center using ML model
      run_loop_center_plan()
    
    if option == OnMountAvailOptions.AUTO_RASTER:
      # Set up a fake standard collection for autoRasterLoop
      request = {"sample": sample_id, 
                  "uid": -1,
                  "request_obj": {
                    "xbeam": getPvDesc('beamCenterX'),
                    "ybeam": getPvDesc('beamCenterY'),
                    "wavelength": daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6),
                    "basePath": getBlConfig("visitDirectory")
                  }
                }
      autoRasterLoop(request)

def run_loop_center_plan():
    if daq_utils.beamline == "fmx":
      # Run xrec for FMX, they don't have a top cam
      retries = 3
      while retries:
        success = loop_center_xrec()
        if not success:
          retries -= 1
        else:
          retries = 0
    RE(loop_center_plan())

def loop_center_plan():
    global sample_detection
    if gov_robot.state.get() == 'M':
      bps.sleep(15)
    if gov_robot.state.get() == "SE":
      gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
      if gov_status.success:
        yield from detect_loop(sample_detection)
      else:
        print("could not transition to SA")
    else:
      yield from detect_loop(sample_detection)

def autoRasterLoop(currentRequest):
    global sample_detection, autoRasterFlag, max_col, face_on_max_coords, ortho_max_coords
    
    if sample_detection["sample_detected"]:
      setTrans(getBlConfig("rasterDefaultTrans"))
      daq_lib.set_field("xrecRasterFlag","100")
      logger.info("auto raster " + str(currentRequest["sample"]))
      logger.info(f"sample detection : {sample_detection}")
      # time.sleep(1)
      autoRasterFlag = 1
      # Before collecting the 1st raster, reset max_col and face_on_max_coords
      max_col = None
      face_on_max_coords = None
      ortho_max_coords = None
      step_size = 10
      if sample_detection["large_box_width"] * sample_detection["large_box_height"] > 150_000:
        step_size = 20
        

      runRasterScan(currentRequest, rasterType="Custom", 
                    width=sample_detection["large_box_width"], 
                    height=sample_detection["large_box_height"], step_size=step_size)
      logger.info(f"AUTORASTER LOOP: {max_col} {face_on_max_coords}")

      if not face_on_max_coords:
        autoRasterFlag = 0
        if daq_utils.beamline == 'fmx':
          gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
        return 0
      
      if "osc_range" in currentRequest["request_obj"] and currentRequest["request_obj"]["osc_range"] == 0:
        autoRasterFlag = 0
        gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
        # Oscillation range is zero which means its a raster screen request
        return 0

      RE(bps.mv(gonio.gx, sample_detection["center_x"], 
            gonio.py, sample_detection["center_y"],
            gonio.pz, sample_detection["center_z"]))
      
      runRasterScan(currentRequest, rasterType="Custom", 
                    width=sample_detection["large_box_width"], 
                    height=sample_detection["small_box_height"], 
                    step_size=step_size,
                    omega_rel=90)
      # Gonio should be at the hot cell for the ortho raster. 
      # Now move to the hot cell of the face on raster, then start standard collection
      if not ortho_max_coords:
        autoRasterFlag = 0
        if daq_utils.beamline == 'fmx':
          gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
        return 0

      logger.info(f"AUTORASTER LOOP: {face_on_max_coords=} {ortho_max_coords=}")
      logger.info(f"AUTORASTER LOOP: {sample_detection=} {max_col=}")
      _, y_f, z_f = face_on_max_coords
      _, y_ort, z_ort = ortho_max_coords
      y_center, z_center = sample_detection["center_y"], sample_detection["center_z"]

      omega_face_on = sample_detection["face_on_omega"] 
      omega_ortho = (sample_detection["face_on_omega"] + 90)

      r_f = (y_f - y_center)*np.cos(np.deg2rad(omega_face_on)) + (z_f - z_center)*np.sin(np.deg2rad(omega_face_on))
      r_o = (y_ort - y_center)*np.cos(np.deg2rad(omega_ortho)) + (z_ort - z_center)*np.sin(np.deg2rad(omega_ortho))

      logger.info(f"AUTORASTER LOOP: {r_f=} {r_o=}")

      r = np.array([[r_f],[r_o]])
      A = np.matrix([[np.cos(np.deg2rad(omega_face_on)), np.sin(np.deg2rad(omega_face_on))],[np.cos(np.deg2rad(omega_ortho)), np.sin(np.deg2rad(omega_ortho))]])
      logger.info(f"AUTORASTER LOOP: {A=}")

      yz = np.linalg.inv(A)*r
      delta_y, delta_z = yz[0,0], yz[1,0]
      logger.info(f"AUTORASTER LOOP: {yz=}")

      final_y = y_center + delta_y
      final_z = z_center + delta_z

      logger.info(f"AUTORASTER LOOP: {final_y=} {final_z=}")


      RE(bps.mv(gonio.py, final_y, gonio.pz, final_z))

      autoRasterFlag = 0
      return 1
    else:
      return 0

def autoRasterLoopOld(currentRequest):
  global autoRasterFlag

  gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
  if not gov_status.success:
    return 0
  if (getBlConfig("queueCollect") == 1):
    delayTime = getBlConfig("autoRasterDelay")
    time.sleep(delayTime)
    
  reqObj = currentRequest["request_obj"]
  if ("centeringOption" in reqObj):
    if (reqObj["centeringOption"] == "AutoLoop"):
      status = loop_center_xrec()
      if (status== 0):
        beamline_lib.mvrDescriptor("sampleX",1000)
        status = loop_center_xrec()                
        if (status== 0):
          beamline_lib.mvrDescriptor("sampleX",1000)
          status = loop_center_xrec()
      time.sleep(2.0)
      status = loop_center_xrec()              
      return status
  setTrans(getBlConfig("rasterDefaultTrans"))
  daq_lib.set_field("xrecRasterFlag","100")        
  sampleID = currentRequest["sample"]
  logger.info("auto raster " + str(sampleID))
  status = loop_center_xrec()
  if (status== 0):
    beamline_lib.mvrDescriptor("sampleX",1000)
    status = loop_center_xrec()                
    if (status== 0):
      beamline_lib.mvrDescriptor("sampleX",1000)
      status = loop_center_xrec()
  time.sleep(2.0)
  status = loop_center_xrec()              
  if (status == -99): #abort, never hit this
    db_lib.updatePriority(currentRequest["uid"],5000)
    return 0    
  if not (status):
    return 0
  time.sleep(2.0) #looks like I really need this sleep, they really improve the appearance 
  runRasterScan(currentRequest,"Coarse")  
  time.sleep(1.5)
  loop_center_mask()
  time.sleep(1)
  autoRasterFlag = 1
  runRasterScan(currentRequest,"Fine")
  time.sleep(1)
  runRasterScan(currentRequest,"Line")
  gov_lib.setGovRobot(gov_robot, 'DI')
  time.sleep(1)
  autoRasterFlag = 0      

  return 1


def autoVector(currentRequest): #12/19 - not tested!
  global autoVectorFlag

  gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
  if not gov_status.success:
    return 0
  reqObj = currentRequest["request_obj"]
  daq_lib.set_field("xrecRasterFlag","100")        
  sampleID = currentRequest["sample"]
  logger.info("auto raster " + str(sampleID))
  status = loop_center_xrec()
  if (status== 0):
    beamline_lib.mvrDescriptor("sampleX",1000)
    status = loop_center_xrec()                
    if (status== 0):
      beamline_lib.mvrDescriptor("sampleX",1000)
      status = loop_center_xrec()                
  time.sleep(2.0)
  status = loop_center_xrec()
  if (status == -99): #abort, never hit this
    db_lib.updatePriority(currentRequest["uid"],5000)
    return 0    
  if not (status):
    return 0
  time.sleep(2.0) #looks like I really need this sleep, they really improve the appearance 
  autoVectorFlag = True
  runRasterScan(currentRequest,"autoVector") 
  logger.info("autovec coarse coords 1")
  logger.info(autoVectorCoarseCoords)
  x1Start = autoVectorCoarseCoords["start"]["x"]
  y1Start = autoVectorCoarseCoords["start"]["y"]
  z1Start = autoVectorCoarseCoords["start"]["z"]
  x1End = autoVectorCoarseCoords["end"]["x"]
  y1End = autoVectorCoarseCoords["end"]["y"]
  z1End = autoVectorCoarseCoords["end"]["z"]
  loop_center_mask()
  time.sleep(1)   
  runRasterScan(currentRequest,"autoVector")
  autoVectorFlag = False  
  logger.info("autovec coarse coords 2")
  logger.info(autoVectorCoarseCoords)
  x2Start = autoVectorCoarseCoords["start"]["x"]
  y2Start = autoVectorCoarseCoords["start"]["y"]
  z2Start = autoVectorCoarseCoords["start"]["z"]
  x2End = autoVectorCoarseCoords["end"]["x"]
  y2End = autoVectorCoarseCoords["end"]["y"]
  z2End = autoVectorCoarseCoords["end"]["z"]

  x_vec_start = min(x1Start,x2Start)
  y_vec_start = (y1Start+y2Start)/2.0
  z_vec_start = (z1Start+z2Start)/2.0  

  x_vec_end = max(x1End,x2End)
  y_vec_end = (y1End+y2End)/2.0
  z_vec_end = (z1End+z2End)/2.0  

  vectorStart = {"x":x_vec_start,"y":y_vec_start,"z":z_vec_start}  
  vectorEnd = {"x":x_vec_end,"y":y_vec_end,"z":z_vec_end}

  x_vec = x_vec_end - x_vec_start
  y_vec = y_vec_end - y_vec_start
  z_vec = z_vec_end - z_vec_start
  trans_total = math.sqrt(x_vec**2 + y_vec**2 + z_vec**2)
  framesPerPoint = 1
  vectorParams={"vecStart":vectorStart,"vecEnd":vectorEnd,"x_vec":x_vec,"y_vec":y_vec,"z_vec":z_vec,"trans_total":trans_total,"fpp":framesPerPoint}
  reqObj["vectorParams"] = vectorParams
  reqObj["centeringOption"] = "Interactive" #kind of kludgy so that collectData doesn't go rastering for vector params again
  currentRequest["request_obj"] = reqObj
  db_lib.updateRequest(currentRequest)
  daq_lib.collectData(currentRequest)
  gov_lib.setGovRobot(gov_robot, 'SA')
  return 1

def rasterScreen(currentRequest):
  if (daq_utils.beamline == "fmx" and getBlConfig("scannerType") == "PI"):
    gridRaster(currentRequest)
    return
  
  daq_lib.set_field("xrecRasterFlag","100")      
  sampleID = currentRequest["sample"]
  reqObj = currentRequest["request_obj"]
  gridStep = reqObj["gridStep"]
  logger.info("rasterScreen " + str(sampleID))
  time.sleep(20)
  status = loop_center_xrec()
  if (status== 0):
    beamline_lib.mvrDescriptor("sampleX",200)
    status = loop_center_xrec()                
  time.sleep(2.0)
  status = loop_center_xrec()              
  if not (status):
    return 0  
  time.sleep(1) #looks like I really need this sleep, they really improve the appearance
  loopSize = getLoopSize()
  if (loopSize != []):
    rasterW = 1.5 * screenXPixels2microns(loopSize[1])
    rasterH = 2.5 * screenXPixels2microns(loopSize[0])
    if (rasterH > (1.2 * rasterW)): # for c3d error
      rasterW = 630
      rasterH = 510
  else:
    rasterW = 630
    rasterH = 510
  rasterReqID = defineRectRaster(currentRequest,rasterW,rasterH,gridStep)     
  db_lib.updatePriority(rasterReqID, -1)
  RE(snakeRaster(rasterReqID))
  

def multiCol(currentRequest):
  daq_lib.set_field("xrecRasterFlag","100")      
  sampleID = currentRequest["sample"]
  logger.info("multiCol " + str(sampleID))
  status = loop_center_xrec()
  if not (status):
    return 0  
  time.sleep(1) #looks like I really need this sleep, they really improve the appearance
  runRasterScan(currentRequest,"Coarse")

def loop_center_xrec_slow():
  global face_on

  daq_lib.abort_flag = 0    

  for i in range(0,360,40):
    if (daq_lib.abort_flag == 1):
      logger.info("caught abort in loop center")
      return 0
    beamline_lib.mvaDescriptor("omega",i)
    pic_prefix = "findloop_" + str(i)
    time.sleep(1.5) #for video lag. This sucks
    daq_utils.take_crystal_picture(filename=pic_prefix)
  comm_s = "xrec " + os.environ["CONFIGDIR"] + "/xrec_360_40.txt xrec_result.txt"
  logger.info(comm_s)
  os.system(comm_s)
  xrec_out_file = open("xrec_result.txt","r")
  target_angle = 0.0
  radius = 0
  x_centre = 0
  y_centre = 0
  reliability = 0
  for result_line in xrec_out_file.readlines():
    logger.info(result_line)
    tokens = result_line.split()
    tag = tokens[0]
    val = tokens[1]
    if (tag == "TARGET_ANGLE"):
      target_angle = float(val )
    elif (tag == "RADIUS"):
      radius = float(val )
    elif (tag == "Y_CENTRE"):
      y_centre_xrec = float(val )
    elif (tag == "X_CENTRE"):
      x_centre_xrec = float(val )
    elif (tag == "RELIABILITY"):
      reliability = int(val )
    elif (tag == "FACE"):
      face_on = float(tokens[3])
  xrec_out_file.close()
  xrec_check_file = open("Xrec_check.txt","r")  
  check_result =  int(xrec_check_file.read(1))
  logger.info("result = " + str(check_result))
  xrec_check_file.close()
  if (reliability < 70 or check_result == 0): #bail if xrec couldn't align loop
    return 0
  beamline_lib.mvaDescriptor("omega",target_angle)
  x_center = getPvDesc("lowMagCursorX")
  y_center = getPvDesc("lowMagCursorY")
  logger.info("center on click " + str(x_center) + " " + str(y_center-radius))
  logger.info("center on click " + str((x_center*2) - y_centre_xrec) + " " + str(x_centre_xrec))
  fovx = daq_utils.lowMagFOVx
  fovy = daq_utils.lowMagFOVy
  
  daq_lib.center_on_click(x_center,y_center-radius,fovx,fovy,source="macro")
  daq_lib.center_on_click((x_center*2) - y_centre_xrec,x_centre_xrec,fovx,fovy,source="macro")
  beamline_lib.mvaDescriptor("omega",face_on)
  #now try to get the loopshape starting from here
  return 1


def generateRasterCoords4Traj(rasterRequest):

  reqObj = rasterRequest["request_obj"]
  exptimePerCell = reqObj["exposure_time"]  
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"])
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  rasterCellMap = {}
  numsteps = float(rasterDef["rowDefs"][0]["numsteps"])
  columns = numsteps
  rows = len(rasterDef["rowDefs"])
  firstRow = rasterDef["rowDefs"][0]
  sx1 = firstRow["start"]["x"] #startX
  sy1 = firstRow["start"]["y"]
  logger.info("start x,y")
  logger.info(sx1)
  logger.info(sy1)

#9/18 - I think these are crap, but will leave them  
  xRelativeMove = sx1
  yzRelativeMove = sy1*math.sin(omegaRad)
  yyRelativeMove = sy1*cos(omegaRad)
  xMotAbsoluteMove1 = xRelativeMove    
  yMotAbsoluteMove1 = yyRelativeMove
  zMotAbsoluteMove1 = yzRelativeMove


  lastRow= rasterDef["rowDefs"][-1]
  ex1 = lastRow["end"]["x"]   #endX
  ey1 = lastRow["end"]["y"]
  logger.info("end x,y")  
  logger.info(ex1)
  logger.info(ey1)  
  deltax = ex1-sx1
  deltay = ey1-sy1
  xMotAbsoluteMove1 = -(deltax/2.0)
  xMotAbsoluteMove2 = (deltax/2.0)  
  yMotAbsoluteMove1 = -(deltay/2.0)*math.cos(omegaRad)
  yMotAbsoluteMove2 = (deltay/2.0)*math.cos(omegaRad)
  zMotAbsoluteMove1 = -(deltay/2.0)*math.sin(omegaRad)
  zMotAbsoluteMove2 = (deltay/2.0)*math.sin(omegaRad)

  logger.info(xMotAbsoluteMove1)
  logger.info(yMotAbsoluteMove1)
  logger.info(zMotAbsoluteMove1)
  logger.info(xMotAbsoluteMove2)
  logger.info(yMotAbsoluteMove2)
  logger.info(zMotAbsoluteMove2)
  logger.info(stepsize)  
  genTraj = Gen_Traj_Square.gen_traj_square(xMotAbsoluteMove1, xMotAbsoluteMove2, yMotAbsoluteMove2, yMotAbsoluteMove1, zMotAbsoluteMove2, zMotAbsoluteMove1, columns,rows)
  Gen_Commands.gen_commands(genTraj,exptimePerCell)



def generateGridMap(rasterRequest,rasterEncoderMap=None): #12/19 - there's some dials vs dozor stuff in here
  global rasterRowResultsList

  reqObj = rasterRequest["request_obj"]
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"])
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  filePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]
  rasterCellMap = {}
  os.system("mkdir -p " + reqObj["directory"])
  for i in range(len(rasterDef["rowDefs"])):
    numsteps = float(rasterDef["rowDefs"][i]["numsteps"])
#next 6 lines to differentiate horizontal vs vertical raster    
    startX = rasterDef["rowDefs"][i]["start"]["x"]
    endX = rasterDef["rowDefs"][i]["end"]["x"]
    startY = rasterDef["rowDefs"][i]["start"]["y"]
    endY = rasterDef["rowDefs"][i]["end"]["y"]
    deltaX = abs(endX-startX)
    deltaY = abs(endY-startY)

    if ((deltaX != 0) and (deltaX>deltaY or not getBlConfig("vertRasterOn"))): #horizontal raster
      if (i%2 == 0): #left to right if even, else right to left - a snake attempt
        startX = rasterDef["rowDefs"][i]["start"]["x"]+(stepsize/2.0) #this is relative to center, so signs are reversed from motor movements.
      else:
        startX = (numsteps*stepsize) + rasterDef["rowDefs"][i]["start"]["x"]-(stepsize/2.0)
      startY = rasterDef["rowDefs"][i]["start"]["y"]+(stepsize/2.0)
      xRelativeMove = startX
      yzRelativeMove = startY*math.sin(omegaRad)
      yyRelativeMove = startY*math.cos(omegaRad)
      xMotAbsoluteMove = rasterStartX+xRelativeMove    
      yMotAbsoluteMove = rasterStartY-yyRelativeMove
      zMotAbsoluteMove = rasterStartZ-yzRelativeMove
      numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
      for j in range(numsteps):
        imIndexStr = str((i*numsteps)+j+1)        
        if (i%2 == 0): #left to right if even, else right to left - a snake attempt
          xMotCellAbsoluteMove = xMotAbsoluteMove+(j*stepsize)
        else:
          xMotCellAbsoluteMove = xMotAbsoluteMove-(j*stepsize)
        cellMapKey = 'cellMap_{}'.format(imIndexStr)
        rasterCellCoords = {"x":xMotCellAbsoluteMove,"y":yMotAbsoluteMove,"z":zMotAbsoluteMove}
        rasterCellMap[cellMapKey] = rasterCellCoords
    else: #vertical raster
      if (i%2 == 0): #top to bottom if even, else bottom to top - a snake attempt
        startY = rasterDef["rowDefs"][i]["start"]["y"]+(stepsize/2.0) #this is relative to center, so signs are reversed from motor movements.
      else:
        startY = (numsteps*stepsize) + rasterDef["rowDefs"][i]["start"]["y"]-(stepsize/2.0)
      startX = rasterDef["rowDefs"][i]["start"]["x"]+(stepsize/2.0)
      xRelativeMove = startX
      yzRelativeMove = startY*math.sin(omegaRad)
      yyRelativeMove = startY*math.cos(omegaRad)
      xMotAbsoluteMove = rasterStartX+xRelativeMove    
      yMotAbsoluteMove = rasterStartY-yyRelativeMove
      zMotAbsoluteMove = rasterStartZ-yzRelativeMove
      numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
      for j in range(numsteps):
        imIndexStr = str((i*numsteps)+j+1)              
        if (i%2 == 0): #top to bottom if even, else bottom to top - a snake attempt
          yMotCellAbsoluteMove = yMotAbsoluteMove-(math.cos(omegaRad)*(j*stepsize))
          zMotCellAbsoluteMove = zMotAbsoluteMove-(math.sin(omegaRad)*(j*stepsize))          
        else:
          yMotCellAbsoluteMove = yMotAbsoluteMove+(math.cos(omegaRad)*(j*stepsize))
          zMotCellAbsoluteMove = zMotAbsoluteMove+(math.sin(omegaRad)*(j*stepsize))          
        cellMapKey = 'cellMap_{}'.format(imIndexStr)
        rasterCellCoords = {"x":xMotAbsoluteMove,"y":yMotCellAbsoluteMove,"z":zMotCellAbsoluteMove}
        rasterCellMap[cellMapKey] = rasterCellCoords

#commented out all of the processing, as this should have been done by the thread
  if (rasterEncoderMap!= None):
    rasterCellMap = rasterEncoderMap
  if ("parentReqID" in rasterRequest["request_obj"]):
    parentReqID = rasterRequest["request_obj"]["parentReqID"]
  else:
    parentReqID = -1
  logger.info("RASTER CELL RESULTS")
  dialsResultLocalList = []
  for i in range (0,len(rasterRowResultsList)):
    for j in range (0,len(rasterRowResultsList[i])):
      try:
        dialsResultLocalList.append(rasterRowResultsList[i][j])
      except KeyError: #this is to deal with single cell row. Instead of getting back a list of one row, I get back just the row from Dials.
        dialsResultLocalList.append(rasterRowResultsList[i])
        break
  rasterResultObj = {"sample_id": rasterRequest["sample"],"parentReqID":parentReqID,"rasterCellMap":rasterCellMap,"rasterCellResults":{"type":"dialsRasterResult","resultObj":dialsResultLocalList}}  
  rasterResultID = db_lib.addResultforRequest("rasterResult",rasterRequest["uid"], owner=daq_utils.owner,result_obj=rasterResultObj,proposalID=daq_utils.getProposalID(),beamline=daq_utils.beamline)
  rasterResult = db_lib.getResult(rasterResultID)
  return rasterResult


def rasterWait():
  time.sleep(0.2)
  while (getPvDesc("RasterActive")):
    time.sleep(0.2)

def vectorWait():
  time.sleep(0.15)
  while (getPvDesc("VectorActive")):
    time.sleep(0.05)

def vectorActiveWait():
  start_time = time.time()
  while (getPvDesc("VectorActive")!=1):
    if time.time() - start_time > 3: #if we have waited long enough, just throw an exception
      raise TimeoutError()
    time.sleep(0.05)

def vectorHoldWait():
  time.sleep(0.15)
  while (getPvDesc("VectorState")!=2):
    time.sleep(0.05)

def vectorProceed():
  setPvDesc("vectorProceed",1)

def vectorSync():
  setPvDesc("vectorSync",1)

def vectorWaitForGo(source="raster",timeout_trials=3):
  while 1:
    try:
      setPvDesc("vectorGo",1)
      vectorActiveWait()
      break
    except TimeoutError:
      timeout_trials -= 1
      logger.info('timeout_trials is down to: %s' % timeout_trials)
      if not timeout_trials:
        message = 'too many errors during %s vectorGo checks' % source
        logger.error(message)
        raise TimeoutError(message)

def makeDozorRowDir(directory,rowIndex):
    """Makes separate directory for each row for dozor output,
    necessary to prevent file overwriting with mult. threads.

    Parameters
    ----------
    directory: str
        main data directory with .h5 files
    rowIndex: int
        raster row index starts at 0

    Returns
    -------
    rowDir: str
        path to row directory
    """

    dozorDir = directory + "/dozor"
    rowDir = dozorDir + "/row_{}/".format(rowIndex)
    os.system("mkdir -p " + rowDir)

    return rowDir

def makeDozorInputFile(directory,prefix,rowIndex,rowCellCount,seqNum,rasterReqObj):
    """Creates input file for dozor that corresponds to an individual
    raster row.

    Parameters
    ----------
    directory: str
        main data directory with .h5 files
    prefix: str
        sample name from spreadsheet and include _Raster if raster
    rowIndex: int
        index of row to be processed from raster
    rowCellCount: int
        number of frames in specified row
    seqNum: int
        seqNum, not sure why skinner included these (unique id?)
    rasterReqObj: dict
        describes experimental metadata for raster request used to
        set detector distance and beam center for dozor input file
    """
    
    #detector metadata from raster request
    orgX = rasterReqObj["xbeam"]
    orgY = rasterReqObj["ybeam"]
    wavelength = rasterReqObj["wavelength"]
    detectorDistance = rasterReqObj["detDist"]
    #detector metadata from epics PVs
    roiMode = beamline_support.getPvValFromDescriptor("detectorROIMode")
    if roiMode == 1:
        detector = "eiger4m"
    elif daq_utils.beamline in ("amx", "fmx"):
        detector = beamline_support.getPvValFromDescriptor("detectorDescription")
        detector = ''.join(detector.split()[1::]).lower() #format for dozor
    else:
        detector = "eiger2-9m"
    nx = beamline_support.getPvValFromDescriptor("detectorNx")
    ny = beamline_support.getPvValFromDescriptor("detectorNy")
    
    firstImageNumber = int(rowIndex)*int(rowCellCount) + 1
    hdf5TemplateImage = "../../{}_{}_??????.h5".format(prefix,seqNum,rowIndex)
    daqMacrosPath = os.path.dirname(__file__)
    inputTemplate = open(os.path.join(daqMacrosPath,"h5_template.dat"))
    src = Template(inputTemplate.read())
    dozorRowDir = makeDozorRowDir(directory,rowIndex)
    dozorSpotLevel = getBlConfig(RASTER_DOZOR_SPOT_LEVEL)
    if daq_utils.beamline == "nyx":
        dozorPlugin = "/nsls2/software/mx/nyx/bin/dectris-neggia.so"
    else:
        dozorPlugin = "/usr/lib64/dectris-neggia.so"
    templateDict = {"detector": detector,
                    "nx": nx,
                    "ny": ny,
                    "wavelength": wavelength,
                    "orgx": orgX,
                    "orgy": orgY,
                    "detector_distance": detectorDistance,
                    "first_image_number": firstImageNumber,
                    "number_images": rowCellCount,
                    "spot_level": dozorSpotLevel,
                    "name_template_image": hdf5TemplateImage,
                    "processing_plugin": dozorPlugin,}
    with open("".join([dozorRowDir,f"h5_row_{rowIndex}.dat"]),"w") as f:
        f.write(src.substitute(templateDict))
    return dozorRowDir

def dozorOutputToList(dozorRowDir,rowIndex,rowCellCount,pathToMasterH5):
    """Takes a dozor_average.dat file and converts the results into
    a list of dictionaries in the format previously implemented
    in lsdc for dials.find_spots_client output. Intended for use
    on a single row.

    Parameters
    ----------
    dozorRowDir: str
        path to dozor row directory
    rowIndex: int
        index of row currently being processed by dozor thread

    Returns
    -------
    localDozorRowList: list
        list of dictionaries for input into analysisstore database
    """

    dozorDat = str(os.path.join(dozorRowDir,"dozor_average.dat"))
    if os.path.isfile(dozorDat):
        try:
            dozorData = np.genfromtxt(dozorDat,skip_header=3)[:,0:4]
        except IndexError:
            #in event of single cell raster, 1d array needs 2 dimensions
            dozorData = np.genfromtxt(dozorDat,skip_header=3)[0:4]
            dozorData = np.reshape(dozorData,(1,4))
    else:
        dozorData = np.zeros((rowCellCount,4))
        dozorData[:,0] = np.arange(start=1,stop=dozorData.shape[0]+1)
        logger.info(f"dozor_avg.dat file not found, empty result returned for row {rowIndex}")
    dozorData[:,3][dozorData[:,3]==0] = 50 #required for scaling/visualizing res. results
    keys = ["image",
            "spot_count",
            "spot_count_no_ice",
            "d_min",
            "d_min_method_1",
            "d_min_method_2",
            "total_intensity",
            "cellMapKey"]
    localList = []

    for cell in range(0,dozorData.shape[0]):
        seriesIndex = int(rowCellCount*rowIndex + dozorData[cell,:][0])
        values = [(pathToMasterH5,seriesIndex),
                  dozorData[cell,:][1],
                  dozorData[cell,:][1],
                  dozorData[cell,:][3],
                  dozorData[cell,:][3],
                  dozorData[cell,:][3],
                  dozorData[cell,:][1]*dozorData[cell,:][2],
                  "cellMap_{}".format(seriesIndex)]
        localList.append(OrderedDict(zip(keys,values)))
    return localList

def runDozorThread(directory,
                   prefix,
                   rowIndex,
                   rowCellCount,
                   seqNum,
                   rasterReqObj,
                   rasterReqID):
    """Creates sub-directory that contains dozor input and output files
    that result from master.h5 file in directory. Dozor executed via
    ssh on remote node(s).

    Parameters
    ----------
    directory: str
        path to directory containing .h5 files
    prefix: str
        includes sample name from spreadsheet and protocol if raster
    rowIndex: int
        row number to be processed (starts at 0)
    seqNum: int
        some parameter Skinner included, maybe to avoid duplicate filenames
    rasterReqObj: dict
        contains experimental metadata, used for setting detector dist and
        beam center for dozor input files
    rasterReqID: str
        ID of raster collection
    """
    global rasterRowResultsList,processedRasterRowCount
    file_writing_delay = 0.5
    node = getNodeName("spot", rowIndex, 8)
    if daq_utils.beamline == 'nyx':
      file_writing_delay = 10
      node = "titania-cpu00"+str((rowIndex%4)+1)
    time.sleep(file_writing_delay) #allow for file writing

    if (seqNum>-1): #eiger
        dozorRowDir = makeDozorInputFile(directory,
                                         prefix,
                                         rowIndex,
                                         rowCellCount,
                                         seqNum,
                                         rasterReqObj)

    else:
        raise Exception("seqNum seems to be non-standard (<0)")

    comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}dozor.sh {rasterReqID} {rowIndex}\""
    logger.info(f"using the following command:   {comm_s}")
    os.system(comm_s)
    logger.info('checking for results on remote node: %s' % comm_s)
    logger.info("leaving thread")
    processedRasterRowCount += 1
    pathToMasterH5 = "{}/{}_{}_master.h5".format(directory,
                                                 prefix,
                                                 seqNum)
    rasterRowResultsList[rowIndex] = dozorOutputToList(dozorRowDir,
                                                       rowIndex,
                                                       rowCellCount,
                                                       pathToMasterH5)
    return

def runDialsThread(requestID, directory,prefix,rowIndex,rowCellCount,seqNum):
  global rasterRowResultsList,processedRasterRowCount
  time.sleep(1.0)
  node = getNodeName("spot", rowIndex, 8)
  if (seqNum>-1): #eiger
    startIndex=(rowIndex*rowCellCount) + 1
    endIndex = startIndex+rowCellCount-1
    comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}eiger2cbf.sh {requestID} {startIndex} {endIndex} {rowIndex} {seqNum}\""
    logger.info('eiger2cbf command: %s' % comm_s)
    os.system(comm_s)
    cbfDir = os.path.join(directory, "cbf")
    CBF_conversion_pattern = os.path.join(cbfDir, f'{prefix}_{rowIndex}_')
    CBFpattern = CBF_conversion_pattern + "*.cbf"
  else:
    CBFpattern = directory + "/cbf/" + prefix+"_" + str(rowIndex) + "_" + "*.cbf"
  time.sleep(1.0)
  comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}dials_spotfind.sh {requestID} {rowIndex} {seqNum}\""
  logger.info('checking for results on remote node: %s' % comm_s)
  retry = 3
  while(1):
    resultString = "<data>\n"+os.popen(comm_s).read()+"</data>\n"
    localDialsResultDict = xmltodict.parse(resultString)
    if (localDialsResultDict["data"] == None and retry>0):
      logger.error("ERROR \n" + resultString + " retry = " + str(retry))
      retry = retry - 1
      if (retry==0):
        localDialsResultDict["data"]={}
        localDialsResultDict["data"]["response"]=[]
        for jj in range (0,rowCellCount): 
          localDialsResultDict["data"]["response"].append({'d_min': '-1.00',
                                                           'd_min_method_1': '-1.00',
                                                           'd_min_method_2': '-1.00',
                                                           'image': '',
                                                           'spot_count': '0',
                                                           'spot_count_no_ice': '0',
                                                           'total_intensity': '0',
                                                           'cellMapKey': 'cellMap_{}'.format(rowIndex*rowCellCount + jj + 1)})
        break
                                      
    else:
      break 
  for kk in range(0,rowCellCount):
    localDialsResultDict["data"]["response"][kk]["cellMapKey"] = 'cellMap_{}'.format(rowIndex*rowCellCount + kk + 1)
  rasterRowResultsList[rowIndex] = localDialsResultDict["data"]["response"]
  processedRasterRowCount+=1
  logger.info("leaving thread")

def generateGridMapFine(rasterRequest,rasterEncoderMap=None,rowsOfSubrasters=0,columnsOfSubrasters=0,rowsPerSubraster=0,cellsPerSubrasterRow=0):
  global rasterRowResultsList

  reqObj = rasterRequest["request_obj"]
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"])
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  filePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]
  rasterCellMap = {}
  os.system("mkdir -p " + reqObj["directory"])
  for i in range(len(rasterDef["rowDefs"])):
    numsteps = float(rasterDef["rowDefs"][i]["numsteps"])
#next 6 lines to differentiate horizontal vs vertical raster    
    startX = rasterDef["rowDefs"][i]["start"]["x"]
    endX = rasterDef["rowDefs"][i]["end"]["x"]
    startY = rasterDef["rowDefs"][i]["start"]["y"]
    endY = rasterDef["rowDefs"][i]["end"]["y"]
    deltaX = abs(endX-startX)
    deltaY = abs(endY-startY)

    if (deltaX>deltaY): #horizontal raster
      if (i%2 == 0): #left to right if even, else right to left - a snake attempt
        startX = rasterDef["rowDefs"][i]["start"]["x"]+(stepsize/2.0) #this is relative to center, so signs are reversed from motor movements.
      else:
        startX = (numsteps*stepsize) + rasterDef["rowDefs"][i]["start"]["x"]-(stepsize/2.0)
      startY = rasterDef["rowDefs"][i]["start"]["y"]+(stepsize/2.0)
      xRelativeMove = startX
      yzRelativeMove = startY*math.sin(omegaRad)
      yyRelativeMove = startY*math.cos(omegaRad)
      xMotAbsoluteMove = rasterStartX+xRelativeMove    
      yMotAbsoluteMove = rasterStartY-yyRelativeMove
      zMotAbsoluteMove = rasterStartZ-yzRelativeMove
      numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
      for j in range(numsteps):
        imIndexStr = str((i*numsteps)+j+1)        
        if (i%2 == 0): #left to right if even, else right to left - a snake attempt
          xMotCellAbsoluteMove = xMotAbsoluteMove+(j*stepsize)
        else:
          xMotCellAbsoluteMove = xMotAbsoluteMove-(j*stepsize)
        if (daq_utils.detector_id == "EIGER-16"):
          dataFileName = "%s_%06d.cbf" % (reqObj["directory"]+"/cbf/"+reqObj["file_prefix"]+"_Raster_"+str(i),(i*numsteps)+j+1)
        else:
          dataFileName = daq_utils.create_filename(filePrefix+"_Raster_"+str(i),(i*numsteps)+j+1)
        rasterCellCoords = {"x":xMotCellAbsoluteMove,"y":yMotAbsoluteMove,"z":zMotAbsoluteMove}
        rasterCellMap[dataFileName[:-4]] = rasterCellCoords
    else: #vertical raster
      if (i%2 == 0): #top to bottom if even, else bottom to top - a snake attempt
        startY = rasterDef["rowDefs"][i]["start"]["y"]+(stepsize/2.0) #this is relative to center, so signs are reversed from motor movements.
      else:
        startY = (numsteps*stepsize) + rasterDef["rowDefs"][i]["start"]["y"]-(stepsize/2.0)
      startX = rasterDef["rowDefs"][i]["start"]["x"]+(stepsize/2.0)
      xRelativeMove = startX
      yzRelativeMove = startY*math.sin(omegaRad)
      yyRelativeMove = startY*math.cos(omegaRad)
      xMotAbsoluteMove = rasterStartX+xRelativeMove    
      yMotAbsoluteMove = rasterStartY-yyRelativeMove
      zMotAbsoluteMove = rasterStartZ-yzRelativeMove
      numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
      for j in range(numsteps):
        imIndexStr = str((i*numsteps)+j+1)              
        if (i%2 == 0): #top to bottom if even, else bottom to top - a snake attempt
          yMotCellAbsoluteMove = yMotAbsoluteMove-(math.cos(omegaRad)*(j*stepsize))
          zMotCellAbsoluteMove = zMotAbsoluteMove-(math.sin(omegaRad)*(j*stepsize))          
        else:
          yMotCellAbsoluteMove = yMotAbsoluteMove+(math.cos(omegaRad)*(j*stepsize))
          zMotCellAbsoluteMove = zMotAbsoluteMove+(math.sin(omegaRad)*(j*stepsize))          
        if (daq_utils.detector_id == "EIGER-16"):
          dataFileName = "%s_%06d.cbf" % (reqObj["directory"]+"/cbf/"+reqObj["file_prefix"]+"_Raster_"+str(i),(i*numsteps)+j+1)
        else:
          dataFileName = daq_utils.create_filename(filePrefix+"_Raster_"+str(i),j+1)
        rasterCellCoords = {"x":xMotAbsoluteMove,"y":yMotCellAbsoluteMove,"z":zMotCellAbsoluteMove}
        rasterCellMap[dataFileName[:-4]] = rasterCellCoords

#commented out all of the processing, as this should have been done by the thread
  if (rasterEncoderMap!= None):
    rasterCellMap = rasterEncoderMap
  if ("parentReqID" in rasterRequest["request_obj"]):
    parentReqID = rasterRequest["request_obj"]["parentReqID"]
  else:
    parentReqID = -1
  logger.info("RASTER CELL RESULTS")
  if (rowsOfSubrasters != 0):
    cellsPerSubraster = rowsPerSubraster*cellsPerSubrasterRow
    subrastersPerCompositeRaster = rowsOfSubrasters*columnsOfSubrasters
    rowsPerCompositeRaster = rowsPerSubraster*rowsOfSubrasters
    cellsPerCompositeRasterRow = columnsOfSubrasters*cellsPerSubrasterRow
    cellsPerCompositeRaster = cellsPerSubraster*subrastersPerCompositeRaster
    subRasterListFlipped = []
    for ii in range (0,len(rasterRowResultsList)):
      subrasterFlipped = []  
      for i in range (0,rowsPerSubraster):
        for j in range (0,cellsPerSubrasterRow):
          origSubrasterIndex = (i*cellsPerSubrasterRow)+j                
          if (i%2 == 1): #odd,flip
            subrasterIndex = (i*cellsPerSubrasterRow)+(cellsPerSubrasterRow-j-1)
          else:
            subrasterIndex = origSubrasterIndex
          subrasterFlipped.append(rasterRowResultsList[ii][subrasterIndex])
      subRasterListFlipped.append(subrasterFlipped)
    dialsResultLocalList = []
    for ii in range (0,rowsOfSubrasters):
      for jj in range (0,rowsPerSubraster):          
        for i in range (0,columnsOfSubrasters):
          for j in range (0,cellsPerSubrasterRow):
            dialsResultLocalList.append(subRasterListFlipped[(ii*columnsOfSubrasters)+i][(jj*cellsPerSubrasterRow)+j]) #first dimension is easy, 
  else:
    dialsResultLocalList = []    
    for i in range (0,len(rasterRowResultsList)):
      for j in range (0,len(rasterRowResultsList[i])):
        try:
          dialsResultLocalList.append(rasterRowResultsList[i][j])
        except KeyError: #this is to deal with single cell row. Instead of getting back a list of one row, I get back just the row from Dials.
          dialsResultLocalList.append(rasterRowResultsList[i])
          break

  rasterResultObj = {"sample_id": rasterRequest["sample"],"parentReqID":parentReqID,"rasterCellMap":rasterCellMap,"rasterCellResults":{"type":"dozorRasterResult","resultObj":dialsResultLocalList}}
  rasterResultID = db_lib.addResultforRequest("rasterResult",rasterRequest["uid"], owner=daq_utils.owner,result_obj=rasterResultObj,proposalID=daq_utils.getProposalID(),beamline=daq_utils.beamline)
  rasterResult = db_lib.getResult(rasterResultID)
  return rasterResult

def getNodeName(node_type, row_index, num_nodes=8): #calculate node name based on row index
    node_number = row_index % num_nodes + 1
    node_config_name = f'{node_type}Node{node_number}'
    return getBlConfig(node_config_name)

def snakeRaster(rasterReqID,grain=""):
  scannerType = getBlConfig("scannerType")
  if (scannerType == "PI"):
    snakeRasterFine(rasterReqID,grain)
  else:
    if daq_utils.beamline == "nyx":
      yield from raster_plan_wrapped(rasterReqID)
    else:
      finalize_plan = finalize_wrapper(snakeRasterBluesky(rasterReqID,grain), bps.mv(raster_flyer.detector.cam.acquire, 0))
      yield from finalize_plan
    #RE(snakeRasterBluesky(rasterReqID,grain))

def snakeRasterNoTile(rasterReqID,grain=""):
  global dialsResultDict,rasterRowResultsList,processedRasterRowCount

  gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
  if not gov_status.success:
    return
  
  rasterRequest = db_lib.getRequestByID(rasterReqID)
  reqObj = rasterRequest["request_obj"]
  parentReqID = reqObj["parentReqID"]
  parentReqProtocol = ""
  
  if (parentReqID != -1):
    parentRequest = db_lib.getRequestByID(parentReqID)
    parentReqObj = parentRequest["request_obj"]
    parentReqProtocol = parentReqObj["protocol"]
    detDist = parentReqObj["detDist"]    
  data_directory_name = str(reqObj["directory"])
  os.system("mkdir -p " + data_directory_name)
  filePrefix = str(reqObj["file_prefix"])
  file_number_start = reqObj["file_number_start"]  
  dataFilePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]  
  exptimePerCell = reqObj["exposure_time"]
  img_width_per_cell = reqObj["img_width"]
  wave = reqObj["wavelength"]
  xbeam = getPvDesc("beamCenterX") * 0.075
  ybeam = getPvDesc("beamCenterY") * 0.075
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"]) #these are real sample motor positions
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  rowCount = len(rasterDef["rowDefs"])
  rasterRowResultsList = [{} for i in range(0,rowCount)]    
  processedRasterRowCount = 0
  rasterEncoderMap = {}
  totalImages = 0
#get the center of the raster, in screen view, mm, relative to center
  rows = rasterDef["rowDefs"]
  numrows = len(rows)
  rasterCenterScreenX = (rows[0]["start"]["x"]+rows[0]["end"]["x"])/2.0
  rasterCenterScreenY = ((rows[-1]["start"]["y"]+rows[0]["start"]["y"])/2.0)+(stepsize/2.0)
  xRelativeMove = rasterCenterScreenX
  yzRelativeMove = -(rasterCenterScreenY*math.sin(omegaRad))
  yyRelativeMove = -(rasterCenterScreenY*math.cos(omegaRad))

  xMotAbsoluteMove = rasterStartX+xRelativeMove #note we convert relative to absolute moves, using the raster center that was saved in x,y,z
  yMotAbsoluteMove = rasterStartY+yyRelativeMove
  zMotAbsoluteMove = rasterStartZ+yzRelativeMove
  

  beamline_lib.mvaDescriptor("sampleX",xMotAbsoluteMove,"sampleY",yMotAbsoluteMove,"sampleZ",zMotAbsoluteMove)
  
  #raster centered, now zero motors
  beamline_lib.mvaDescriptor("fineX",0,"fineY",0,"fineZ",0)  
  for i in range(len(rasterDef["rowDefs"])):
    numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
    totalImages = totalImages+numsteps
  rasterFilePrefix = dataFilePrefix + "_Raster"

  det_lib.detector_set_num_triggers(totalImages)
  det_lib.detector_set_trigger_mode(3)
  det_lib.detector_setImagesPerFile(numsteps)  
  daq_lib.detectorArm(omega,img_width_per_cell,totalImages,exptimePerCell,rasterFilePrefix,data_directory_name,file_number_start) #this waits

  zebraVecDaqSetup(omega,img_width_per_cell,exptimePerCell,totalImages,rasterFilePrefix,data_directory_name,file_number_start)
  procFlag = int(getBlConfig("rasterProcessFlag"))  
  generateRasterCoords4Traj(rasterRequest)
  total_exposure_time = exptimePerCell*totalImages    
    
  setPvDesc("zebraPulseMax",totalImages) 
  vectorSync()    
  setPvDesc("vectorStartOmega",omega)
  setPvDesc("vectorEndOmega",(img_width_per_cell*totalImages)+omega)
  setPvDesc("vectorframeExptime",exptimePerCell*1000.0)
  setPvDesc("vectorNumFrames",totalImages)
  rasterFilePrefix = dataFilePrefix + "_Raster_" + str(i)
  Gen_Commands.go_all()
  setPvDesc("vectorGo",1)
  vectorActiveWait()    
  vectorWait()
  zebraWait()
  #delete these
  time.sleep(2.0)
  det_lib.detector_stop_acquire()
  det_lib.detector_wait()
  beamline_lib.mvaDescriptor("fineX",0,"fineY",0,"fineZ",0)
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)      
  
  if (procFlag):
    if (daq_utils.beamline == "amx"):
      rasterRowEncoderVals = {"x":getPvDesc("zebraEncX"),"y":getPvDesc("zebraEncY"),"z":getPvDesc("zebraEncZ"),"omega":getPvDesc("zebraEncOmega")}
      for j in range (0,numsteps):
        dataFileName = "%s_%06d.cbf" % (reqObj["directory"]+"/cbf/"+reqObj["file_prefix"]+"_Raster_"+str(i),(i*numsteps)+j+1)
        imIndexStr = str((i*numsteps)+j+1)
        rasterEncoderMap[dataFileName[:-4]] = {"x":rasterRowEncoderVals["x"][j],"y":rasterRowEncoderVals["y"][j],"z":rasterRowEncoderVals["z"][j],"omega":rasterRowEncoderVals["omega"][j]}
    seqNum = int(det_lib.detector_get_seqnum())
    for i in range(len(rasterDef["rowDefs"])):  
      _thread.start_new_thread(runDialsThread,(rasterRequest["uid"], data_directory_name,filePrefix+"_Raster",i,numsteps,seqNum))
  else:
    rasterRequestID = rasterRequest["uid"]
    db_lib.updateRequest(rasterRequest)    
    db_lib.updatePriority(rasterRequestID,-1)  
    if (lastOnSample()):  
      gov_lib.setGovRobot(gov_robot, 'SA')
    return 1
      
  rasterTimeout = 600
  timerCount = 0
  while (1):
    timerCount +=1
    if (timerCount>rasterTimeout):
      break
    time.sleep(1)
    logger.info('rastering row processed: %s' % processedRasterRowCount)
    if (processedRasterRowCount == rowCount):
      break
  if (daq_utils.beamline == "amx"):                
    rasterResult = generateGridMap(rasterRequest,rasterEncoderMap) #I think rasterRequest is entire request, of raster type    
  else:
    rasterResult = generateGridMap(rasterRequest)     
  rasterRequest["request_obj"]["rasterDef"]["status"] = 2
  protocol = reqObj["protocol"]
  logger.info("protocol = " + protocol)
  if (protocol == "multiCol" or parentReqProtocol == "multiColQ"):
    if (parentReqProtocol == "multiColQ"):    
      multiColThreshold  = parentReqObj["diffCutoff"]
    else:
      multiColThreshold  = reqObj["diffCutoff"]         
    gotoMaxRaster(rasterResult,multiColThreshold=multiColThreshold) 
  rasterRequestID = rasterRequest["uid"]
  db_lib.updateRequest(rasterRequest)
  
  db_lib.updatePriority(rasterRequestID,-1)  
  daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
  if (lastOnSample()):    
    gov_lib.setGovRobot(gov_robot, 'SA')
  return 1

    

def snakeRasterFine(rasterReqID,grain=""): #12/19 - This is for the PI scanner. It was challenging to write. It was working the last time the scanner was on. 
  global dialsResultDict,rasterRowResultsList,processedRasterRowCount

  gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
  if not gov_status.success:
    return
  
  rasterRequest = db_lib.getRequestByID(rasterReqID)
  reqObj = rasterRequest["request_obj"]
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])  
  data_directory_name = str(reqObj["directory"])
  filePrefix = str(reqObj["file_prefix"])
  file_number_start = reqObj["file_number_start"]  
  dataFilePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]  
  wave = reqObj["wavelength"]
  xbeam = getPvDesc("beamCenterX")
  ybeam = getPvDesc("beamCenterY")
  processedRasterRowCount = 0
  totalImages = 0
#get the center of the raster, in screen view, mm, relative to center
  rows = rasterDef["rowDefs"]
  numrows = len(rows)
  origRasterCenterScreenX = (rows[0]["start"]["x"]+rows[0]["end"]["x"])/2.0
  origRasterCenterScreenY = ((rows[-1]["start"]["y"]+rows[0]["start"]["y"])/2.0)+(stepsize/2.0)
  beamline_lib.mvaDescriptor("fineX",0,"fineY",0,"fineZ",0)  
  exptimePerCell = reqObj["exposure_time"]
  img_width_per_cell = reqObj["img_width"]  
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"])
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  firstRow = rasterDef["rowDefs"][0]
  lastRow= rasterDef["rowDefs"][-1]
  sx1 = firstRow["start"]["x"] #startX
  sy1 = firstRow["start"]["y"]
  ex1 = lastRow["end"]["x"]   #endX
  ey1 = lastRow["end"]["y"]
  rasterLenX = ex1-sx1
  rasterLenY = ey1-sy1
  omegaLimit = 40.0
  xLimit = 180.0
  yLimit = 120.0
  if (rasterLenX<xLimit and rasterLenY<yLimit): #no need for tiling. Just do what was done before so we can have a heatmap
    snakeRasterNoTile(rasterReqID)
    return
  maxFramesOmega = int(omegaLimit/img_width_per_cell)
  maxFramesX = int(xLimit/stepsize)
  maxFramesY = int(yLimit/stepsize)  
  columnsOfSubrasters = int(math.ceil(rasterLenX/xLimit))
  subrasterLenX = rasterLenX/columnsOfSubrasters
  subrasterColumns = int(subrasterLenX/stepsize)
  
  maxRowsPerSubraster1 = int(maxFramesOmega/subrasterColumns) # we want this one to come up short, no ceil, worry about omega
  maxRowsPerSubraster2 = maxFramesY #worry about Y,Z travel
  maxRowsPerSubraster = min(maxRowsPerSubraster1,maxRowsPerSubraster2)
  
  totalRowsY = int(rasterLenY/stepsize)
  rowsOfSubrasters = int(math.ceil(float(totalRowsY)/float(maxRowsPerSubraster)))
  rowsPerSubraster = int(totalRowsY/rowsOfSubrasters)  
  subrasterLenY = rowsPerSubraster*stepsize
  newRasterLenX = columnsOfSubrasters*subrasterLenX
  newRasterLenY = subrasterLenY*rowsOfSubrasters
  numsteps_h = columnsOfSubrasters*subrasterColumns
  numsteps_v = rowsPerSubraster*rowsOfSubrasters
  newRasterDef = defineTiledRaster(rasterDef,numsteps_h,numsteps_v,origRasterCenterScreenX,origRasterCenterScreenY)
  reqObj["rasterDef"] = newRasterDef
  rasterDef = reqObj["rasterDef"]
  rasterRequest["request_obj"]  = reqObj


  daq_lib.set_field("xrecRasterFlag","100")
  db_lib.updateRequest(rasterRequest) #define new dimensions  
  time.sleep(1.0)
  daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"]) #draw the raster

  
  deltax = subrasterLenX
  deltay = subrasterLenY
  logger.info("omega start " + str(omega))
  logger.info("orig raster Len X = " + str(rasterLenX))
  logger.info("orig raster Len Y = " + str(rasterLenY))  

  xMotAbsoluteMove1 = -(deltax/2.0)
  xMotAbsoluteMove2 = deltax/2.0
  yMotAbsoluteMove1 = -(deltay*math.cos(omegaRad))/2.0
  yMotAbsoluteMove2 = (deltay*math.cos(omegaRad))/2.0
  zMotAbsoluteMove1 = -(deltay*math.sin(omegaRad))/2.0
  zMotAbsoluteMove2 = (deltay*math.sin(omegaRad))/2.0
  

  logger.info("columns of subrasters " + str(columnsOfSubrasters))
  logger.info("rows of subrasters " + str(rowsOfSubrasters))  
  logger.info("subraster columns " + str(subrasterColumns))
  logger.info("sub rows " + str(rowsPerSubraster))  
  logger.info("individual subraster vectors, all same for all subs (start xyz, end xyz")
  
  logger.info(xMotAbsoluteMove1)
  logger.info(yMotAbsoluteMove1)
  logger.info(zMotAbsoluteMove1)
  logger.info(xMotAbsoluteMove2)
  logger.info(yMotAbsoluteMove2)
  logger.info(zMotAbsoluteMove2)
  logger.info(stepsize)
  
  numberOfSubrasters = rowsOfSubrasters*columnsOfSubrasters
  rasterRowResultsList = [{} for i in range(0,numberOfSubrasters)]      
  cellsPerSubraster = rowsPerSubraster*subrasterColumns
  totalImages = numberOfSubrasters*cellsPerSubraster
  rasterFilePrefix = dataFilePrefix + "_Raster"
  logger.info("number of subrasters " + str(numberOfSubrasters))
  logger.info("cells per subrasters " + str(cellsPerSubraster))

  os.system("mkdir -p " + data_directory_name)
  
  det_lib.detector_set_num_triggers(totalImages)
  det_lib.detector_set_trigger_mode(3)
  det_lib.detector_setImagesPerFile(cellsPerSubraster)  

#this could be tricky, b/c omega is angle start that ends up in header, so if you want to arm once, this won't be right
  daq_lib.detectorArm(omega,img_width_per_cell,totalImages,exptimePerCell,rasterFilePrefix,data_directory_name,file_number_start) #this waits
  procFlag = int(getBlConfig("rasterProcessFlag"))  
  
  subrasters = []

  for i in range (0,rowsOfSubrasters): #this is very misleading, "end" not used? these are really the start coords of each sub?
    for j in range (0,columnsOfSubrasters): #for now, just make a list of subraster start, end coords.      
      subrasterStartX = sx1+(j*subrasterLenX)+(subrasterLenX/2.0)
      subrasterStartY = sy1+(i*subrasterLenY)+(subrasterLenY/2.0)
      subraster = {"startX":subrasterStartX,"startY":subrasterStartY,"endX":subrasterStartX+(subrasterLenX/2.0),"endy":subrasterStartY+(subrasterLenY/2.0)}
      subrasters.append(subraster)
      logger.info(subraster)
  
#assume we now have list of first row start, last row end of subs

#from the upper left hand corner of every subraster
  logger.info("main raster center " + str(rasterStartX) + " " + str(rasterStartY) + " " + str(rasterStartZ))  
  for i in range (0,len(subrasters)): # coarse move and go? but the zebra needs to be reset b/c it controls omega
#hey - these are all the same - just need to move the coarse stages, then every subraster is the same damn thing as far as the PI is concerned!
    genTraj = Gen_Traj_Square.gen_traj_square(xMotAbsoluteMove1, xMotAbsoluteMove2, yMotAbsoluteMove2, yMotAbsoluteMove1, zMotAbsoluteMove2, zMotAbsoluteMove1, subrasterColumns,rowsPerSubraster)
    Gen_Commands.gen_commands(genTraj,exptimePerCell)

    xRelativeMove = subrasters[i]["startX"]
    yzRelativeMove = subrasters[i]["startY"]*math.sin(omegaRad)
    yyRelativeMove = subrasters[i]["startY"]*math.cos(omegaRad)
    xMotAbsoluteMove = rasterStartX+xRelativeMove
    yMotAbsoluteMove = rasterStartY-yyRelativeMove
    zMotAbsoluteMove = rasterStartZ-yzRelativeMove
    logger.info("absolute corner moves " + str(xMotAbsoluteMove) + " " + str(yMotAbsoluteMove) + " " + str(zMotAbsoluteMove))    
    beamline_lib.mvaDescriptor("sampleX",xMotAbsoluteMove,"sampleY",yMotAbsoluteMove,"sampleZ",zMotAbsoluteMove)
    beamline_lib.mvaDescriptor("fineX",0,"fineY",0,"fineZ",0)
#file_number_start not used
    rasterFilePrefix = dataFilePrefix + "_Raster_" + str(i)
    zebraVecDaqSetup(omega,img_width_per_cell,exptimePerCell,cellsPerSubraster,rasterFilePrefix,data_directory_name,file_number_start)
    total_exposure_time = exptimePerCell*cellsPerSubraster
    setPvDesc("zebraPulseMax",cellsPerSubraster) 
    vectorSync()    
    setPvDesc("vectorStartOmega",omega)
    setPvDesc("vectorEndOmega",(img_width_per_cell*cellsPerSubraster)+omega)
    setPvDesc("vectorframeExptime",exptimePerCell*1000.0)
    setPvDesc("vectorNumFrames",cellsPerSubraster)
    Gen_Commands.go_all()
    setPvDesc("vectorGo",1)
    vectorActiveWait()    
    vectorWait()
    zebraWait()
    seqNum = int(det_lib.detector_get_seqnum())
    if (procFlag):    
      _thread.start_new_thread(runDialsThread,(rasterRequest["uid"], data_directory_name,filePrefix+"_Raster",i,cellsPerSubraster,seqNum))    
  #delete these
  time.sleep(2.0)
  det_lib.detector_stop_acquire()
  det_lib.detector_wait()
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)        
  beamline_lib.mvaDescriptor("fineX",0,"fineY",0,"fineZ",0)
  
  if not (procFlag):
    return 1
  rasterTimeout = 60
  timerCount = 0
  while (1):
    timerCount +=1
    if (timerCount>rasterTimeout):
      break
    time.sleep(1)
    logger.info(processedRasterRowCount)
    if (processedRasterRowCount == numberOfSubrasters):
      break
  rasterResult = generateGridMapFine(rasterRequest,rowsOfSubrasters=rowsOfSubrasters,columnsOfSubrasters=columnsOfSubrasters,rowsPerSubraster=rowsPerSubraster,cellsPerSubrasterRow=subrasterColumns)
    
  rasterRequest["request_obj"]["rasterDef"]["status"] = 2
  rasterRequestID = rasterRequest["uid"]
  db_lib.updateRequest(rasterRequest) #so that it will fill heatmap?
  db_lib.updatePriority(rasterRequestID,-1)
  daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
  if (lastOnSample()):    
    gov_lib.setGovRobot(gov_robot, 'SA')
  return 1

  

def snakeRasterNormal(rasterReqID,grain=""):
  global rasterRowResultsList,processedRasterRowCount

  if (daq_utils.beamline == "fmx"):
    setPvDesc("sampleProtect",0)
  setPvDesc("vectorGo", 0) #set to 0 to allow easier camonitoring vectorGo
  gov_lib.setGovRobot(gov_robot, "DA")
  rasterRequest = db_lib.getRequestByID(rasterReqID)
  reqObj = rasterRequest["request_obj"]
  parentReqID = reqObj["parentReqID"]
  parentReqProtocol = ""
  
  data_directory_name, filePrefix, file_number_start, dataFilePrefix, exptimePerCell, img_width_per_cell, wave, detDist, rasterDef, stepsize, omega, rasterStartX, rasterStartY, rasterStartZ, omegaRad, rowCount, numsteps, totalImages = params_from_raster_req_id(rasterReqID)

  rasterRowResultsList = [{} for i in range(0,rowCount)]    
  processedRasterRowCount = 0
  rasterEncoderMap = {}

  # a couple of items we can get independent of rasterReqID
  xbeam = getPvDesc("beamCenterX")
  ybeam = getPvDesc("beamCenterY")

  if (parentReqID != -1):
    parentRequest = db_lib.getRequestByID(parentReqID)
    parentReqObj = parentRequest["request_obj"]
    parentReqProtocol = parentReqObj["protocol"]
    detDist = parentReqObj["detDist"]    

  # now we do stuff with that info
  rasterFilePrefix = dataFilePrefix + "_Raster"
  total_exposure_time = exptimePerCell*totalImages
  # TODO decide - put everything below here into a function? how should the processing be handled?
  det_lib.detector_set_num_triggers(totalImages)
  det_lib.detector_set_trigger_mode(3)
  det_lib.detector_setImagesPerFile(numsteps)  
  daq_lib.detectorArm(omega,img_width_per_cell,totalImages,exptimePerCell,rasterFilePrefix,data_directory_name,file_number_start) #this waits
  try:
    gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
    if not gov_status.success:
      if (daq_utils.beamline == "fmx"):
        setPvDesc("sampleProtect",1)    
      raise Exception('not in DA state')      
    zebraVecDaqSetup(omega,img_width_per_cell,exptimePerCell,numsteps,rasterFilePrefix,data_directory_name,file_number_start) #TODO set up a bunch of stuff?
    procFlag = int(getBlConfig("rasterProcessFlag"))    
 
    spotFindThreadList = [] 
    for i in range(len(rasterDef["rowDefs"])):
      if (daq_lib.abort_flag == 1): # TODO better to do this in a catch/finally block?
        gov_lib.setGovRobot(gov_robot, 'SA')
        if (daq_utils.beamline == "fmx"):
          setPvDesc("sampleProtect",1)    
        raise Exception('raster aborted')
      # TODO surprisingly, no direct move to start position
      numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
      startX = rasterDef["rowDefs"][i]["start"]["x"]
      endX = rasterDef["rowDefs"][i]["end"]["x"]
      startY = rasterDef["rowDefs"][i]["start"]["y"]
      endY = rasterDef["rowDefs"][i]["end"]["y"]
      deltaX = abs(endX-startX)
      deltaY = abs(endY-startY)
      if ((deltaX != 0) and (deltaX>deltaY or not getBlConfig("vertRasterOn"))): #horizontal raster
        startY = startY + (stepsize/2.0)
        endY = startY
      else: #vertical raster
        startX = startX + (stepsize/2.0)
        endX = startX
     
      # TODO move all of this calculation stuff out
      xRelativeMove = startX

      yzRelativeMove = startY*math.sin(omegaRad)
      yyRelativeMove = startY*math.cos(omegaRad)
      logger.info("x rel move = " + str(xRelativeMove))
      xMotAbsoluteMove = rasterStartX+xRelativeMove #note we convert relative to absolute moves, using the raster center that was saved in x,y,z
      yMotAbsoluteMove = rasterStartY-yyRelativeMove
      zMotAbsoluteMove = rasterStartZ-yzRelativeMove
      xRelativeMove = endX-startX
      yRelativeMove = endY-startY
 
      yyRelativeMove = yRelativeMove*math.cos(omegaRad)
      yzRelativeMove = yRelativeMove*math.sin(omegaRad)

      xEnd = xMotAbsoluteMove + xRelativeMove
      yEnd = yMotAbsoluteMove - yyRelativeMove
      zEnd = zMotAbsoluteMove - yzRelativeMove

      if (i%2 != 0): #this is to scan opposite direction for snaking
        xEndSave = xEnd
        yEndSave = yEnd
        zEndSave = zEnd
        xEnd = xMotAbsoluteMove
        yEnd = yMotAbsoluteMove
        zEnd = zMotAbsoluteMove
        xMotAbsoluteMove = xEndSave
        yMotAbsoluteMove = yEndSave
        zMotAbsoluteMove = zEndSave
      zebraVecBluesky() # just do the vector scan part
      xMotAbsoluteMove, xEnd, yMotAbsoluteMove, yEnd, zMotAbsoluteMove, zEnd = raster_positions(rasterdef[i], stepsize, omegaRad, rasterStartX, rasterStartY, rasterStartZ, i)
      setPvDesc("zebraPulseMax",numsteps) #moved this      
      setPvDesc("vectorStartOmega",omega)
      if (img_width_per_cell != 0):
        setPvDesc("vectorEndOmega",(img_width_per_cell*numsteps)+omega)
      else:
        setPvDesc("vectorEndOmega",omega)      
      setPvDesc("vectorStartX",xMotAbsoluteMove)
      setPvDesc("vectorStartY",yMotAbsoluteMove)  
      setPvDesc("vectorStartZ",zMotAbsoluteMove)
      setPvDesc("vectorEndX",xEnd)
      setPvDesc("vectorEndY",yEnd)  
      setPvDesc("vectorEndZ",zEnd)  
      setPvDesc("vectorframeExptime",exptimePerCell*1000.0)
      setPvDesc("vectorNumFrames",numsteps)
      rasterFilePrefix = dataFilePrefix + "_Raster_" + str(i)
      scanWidth = float(numsteps)*img_width_per_cell
      logger.info('raster done setting up')
      vectorWaitForGo(source="snakeRasterNormal")
      vectorWait()
      zebraWait()
      zebraWaitDownload(numsteps)
      logger.info('done raster')

      # processing
      if (procFlag):    
        if (daq_utils.detector_id == "EIGER-16"):
          seqNum = int(det_lib.detector_get_seqnum())
        else:
          seqNum = -1
        logger.info('beginning raster processing with dozor spot_level at %s'
                     % getBlConfig(RASTER_DOZOR_SPOT_LEVEL))
        spotFindThread = Thread(target=runDozorThread,args=(data_directory_name, #TODO this can't move outside of the thread checking block
                                                            ''.join([filePrefix,"_Raster"]),
                                                            i,
                                                            numsteps,
                                                            seqNum,
                                                            reqObj,
                                                            rasterReqID))
        spotFindThread.start()
        spotFindThreadList.append(spotFindThread)
      send_kafka_message(f'{daq_utils.beamline}.lsdc.documents', event='event', uuid=rasterReqID, protocol="raster", row=i, proc_flag=procFlag)


    """governor transitions:
    initiate transitions here allows for GUI sample/heat map image to update
    after moving to known position"""
    logger.debug(f'lastOnSample(): {lastOnSample()} autoRasterFlag: {autoRasterFlag}')
    if (lastOnSample() and not autoRasterFlag):
      govStatus = gov_lib.setGovRobot(gov_robot, 'SA', wait=False)  # TODO standardize naming of govStatus and gov_status objects
      targetGovState = 'SA'
    else:
      govStatus = gov_lib.setGovRobot(gov_robot, 'DI')
      targetGovState = 'DI'

    # priorities:
    # 1. make heat map visible to users correctly aligned with sample
    # 2. take snapshot for ISPyB with heat map and sample visible (governor moved to
    #    a position with backlight in) and aligned

    #data acquisition is finished, now processing and sample positioning
    if not procFlag:
      #must go to known position to account for windup dist. 
      logger.info("moving to raster start")
      gonio.put(rasterStartX, rasterStartY, rasterStartZ, omega)
      logger.info("done moving to raster start")

    if (procFlag):
      if daq_lib.abort_flag != 1:
        [thread.join(timeout=120) for thread in spotFindThreadList]
      else:
        logger.info("raster aborted, do not wait for spotfind threads")
      logger.info(str(processedRasterRowCount) + "/" + str(rowCount))      
      rasterResult = generateGridMap(rasterRequest)
  
      logger.info(f'protocol = {reqObj["protocol"]}')
      if (reqObj["protocol"] == "multiCol" or parentReqProtocol == "multiColQ"):
        if (parentReqProtocol == "multiColQ"):    
          multiColThreshold  = parentReqObj["diffCutoff"]
        else:
          multiColThreshold  = reqObj["diffCutoff"]         
        gotoMaxRaster(rasterResult,multiColThreshold=multiColThreshold) 
      else:
        try:
          # go to start omega for faster heat map display
          gotoMaxRaster(rasterResult,omega=omega)
        except ValueError:
          #must go to known position to account for windup dist.
          logger.info("moving to raster start")
          beamline_lib.mvaDescriptor("sampleX",rasterStartX,
                                     "sampleY",rasterStartY,
                                     "sampleZ",rasterStartZ,
                                     "omega",omega)
          logger.info("done moving to raster start")

      """change request status so that GUI only fills heat map when
      xrecRasterFlag PV is set"""
      rasterRequest["request_obj"]["rasterDef"]["status"] = (
          RasterStatus.READY_FOR_FILL.value
      )
      db_lib.updateRequest(rasterRequest)
      daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
      logger.info(f'setting xrecRasterFlag to: {rasterRequest["uid"]}')
  except Exception as e:
    logger.error(f'Exception while rastering: {e}')
    return
  finally:
  #use this required pause to allow GUI time to fill map and for db update
    logger.info('stopping detector')
    det_lib.detector_stop_acquire()
  det_lib.detector_wait()  
  logger.info('detector finished waiting')

  """change request status so that GUI only takes a snapshot of
  sample plus heat map for ispyb when xrecRasterFlag PV is set"""
  rasterRequestID = rasterRequest["uid"]
  rasterRequest["request_obj"]["rasterDef"]["status"] = (
      RasterStatus.READY_FOR_SNAPSHOT.value
  )
  db_lib.updateRequest(rasterRequest)  
  db_lib.updatePriority(rasterRequestID,-1)

  #ensure gov transitions have completed successfully
  timeout = 20
  gov_lib.waitGov(govStatus, timeout)
  if not(govStatus.success) or not(govs.gov.robot.state == targetGovState):
    logger.error(f"gov status check failed, did not achieve {targetGovState}")

  if (procFlag):
    """if sleep too short then black ispyb image, timing affected by speed
    of governor transition. Sleep constraint can be relaxed with gov
    transitions and concomitant GUI moved to an earlier stage."""
    if (rasterRequest["request_obj"]["rasterDef"]["numCells"]
        > getBlConfig(RASTER_NUM_CELLS_DELAY_THRESHOLD)):
      #larger rasters can delay GUI scene update
      time.sleep(getBlConfig(RASTER_LONG_SNAPSHOT_DELAY))
    else:
      time.sleep(getBlConfig(RASTER_SHORT_SNAPSHOT_DELAY))
    daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
    time.sleep(getBlConfig(RASTER_POST_SNAPSHOT_DELAY))
  if (daq_utils.beamline == "fmx"):
    setPvDesc("sampleProtect",1)
  return 1

def raster_positions(currentRow, stepsize, omegaRad, rasterStartX, rasterStartY, rasterStartZ, index):
    numsteps = int(currentRow["numsteps"])
    startX = currentRow["start"]["x"]
    endX = currentRow["end"]["x"]
    startY = currentRow["start"]["y"]
    endY = currentRow["end"]["y"]
    deltaX = abs(endX-startX)
    deltaY = abs(endY-startY)
    if ((deltaX != 0) and (deltaX>deltaY or not getBlConfig("vertRasterOn"))): #horizontal raster
        startY = startY + (stepsize/2.0)
        endY = startY
    else: #vertical raster
        startX = startX + (stepsize/2.0)
        endX = startX
      
    xRelativeMove = startX

    yzRelativeMove = startY*math.sin(omegaRad)
    yyRelativeMove = startY*math.cos(omegaRad)
    logger.info("x rel move = " + str(xRelativeMove))
    xMotAbsoluteMove = rasterStartX+xRelativeMove #note we convert relative to absolute moves, using the raster center that was saved in x,y,z
    yMotAbsoluteMove = rasterStartY-yyRelativeMove
    zMotAbsoluteMove = rasterStartZ-yzRelativeMove
    xRelativeMove = endX-startX
    yRelativeMove = endY-startY

    yyRelativeMove = yRelativeMove*math.cos(omegaRad)
    yzRelativeMove = yRelativeMove*math.sin(omegaRad)

    xEnd = xMotAbsoluteMove + xRelativeMove
    yEnd = yMotAbsoluteMove - yyRelativeMove
    zEnd = zMotAbsoluteMove - yzRelativeMove

    if (index%2 != 0): #this is to scan opposite direction for snaking
        xEndSave = xEnd
        yEndSave = yEnd
        zEndSave = zEnd
        xEnd = xMotAbsoluteMove
        yEnd = yMotAbsoluteMove
        zEnd = zMotAbsoluteMove
        xMotAbsoluteMove = xEndSave
        yMotAbsoluteMove = yEndSave
        zMotAbsoluteMove = zEndSave
    return xMotAbsoluteMove, xEnd, yMotAbsoluteMove, yEnd, zMotAbsoluteMove, zEnd

def params_from_raster_req_id(rasterReqID):
    rasterRequest = db_lib.getRequestByID(rasterReqID)
    reqObj = rasterRequest["request_obj"]

    data_directory_name = str(reqObj["directory"])
    os.system("mkdir -p " + data_directory_name)
    os.system("chmod -R 777 " + data_directory_name)  
    filePrefix = str(reqObj["file_prefix"])
    file_number_start = reqObj["file_number_start"]  
    dataFilePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]  
    exptimePerCell = reqObj["exposure_time"]
    img_width_per_cell = reqObj["img_width"]
#r  eally should read these two from hardware  
    wave = reqObj["wavelength"]
    detDist = reqObj["detDist"]
    rasterDef = reqObj["rasterDef"]
    stepsize = float(rasterDef["stepsize"])
    omega = float(rasterDef["omega"])
    rasterStartX = float(rasterDef["x"]) #these are real sample motor positions
    rasterStartY = float(rasterDef["y"])
    rasterStartZ = float(rasterDef["z"])
    omegaRad = math.radians(omega)
    rowCount = len(rasterDef["rowDefs"])

    totalImages = 0
    for i in range(len(rasterDef["rowDefs"])):  # TODO assume rectangular for current hardware?
        numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
        totalImages = totalImages+numsteps
    return data_directory_name, filePrefix, file_number_start, dataFilePrefix, exptimePerCell, img_width_per_cell, wave, detDist, rasterDef, stepsize, omega, rasterStartX, rasterStartY, rasterStartZ, omegaRad, rowCount, numsteps, totalImages, rasterDef["rowDefs"]

    
def reprocessRaster(rasterReqID):
  global rasterRowResultsList,processedRasterRowCount

  rasterRequest = db_lib.getRequestByID(rasterReqID)
  reqObj = rasterRequest["request_obj"]
  data_directory_name = str(reqObj["directory"])
  filePrefix = str(reqObj["file_prefix"])
  file_number_start = reqObj["file_number_start"]  
  dataFilePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]  
  exptimePerCell = reqObj["exposure_time"]
  img_width_per_cell = reqObj["img_width"]
  wave = reqObj["wavelength"]
  xbeam = getPvDesc("beamCenterX")
  ybeam = getPvDesc("beamCenterY")
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"]) #these are real sample motor positions
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  rowCount = len(rasterDef["rowDefs"])
  rasterRowResultsList = [{} for i in range(0,rowCount)]    
  processedRasterRowCount = 0
  rasterEncoderMap = {}
  totalImages = 0
  for i in range(len(rasterDef["rowDefs"])):
    numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
    totalImages = totalImages+numsteps
  rasterFilePrefix = dataFilePrefix + "_Raster"
  total_exposure_time = exptimePerCell*totalImages
  procFlag = 1
  
  for i in range(len(rasterDef["rowDefs"])):
    currentRow = rasterDef["rowDefs"][i]
    time.sleep(0.5) 
    numsteps = int(currentRow["numsteps"])
    startX = currentRow["start"]["x"]
    endX = currentRow["end"]["x"]
    startY = currentRow["start"]["y"]
    endY = currentRow["end"]["y"]
    deltaX = abs(endX-startX)
    deltaY = abs(endY-startY)
    if ((deltaX != 0) and (deltaX>deltaY or not getBlConfig("vertRasterOn"))): #horizontal raster
      startY = startY + (stepsize/2.0)
      endY = startY
    else: #vertical raster
      startX = startX + (stepsize/2.0)
      endX = startX
      
    xRelativeMove = startX

    yzRelativeMove = startY*math.sin(omegaRad)
    yyRelativeMove = startY*math.cos(omegaRad)
    xMotAbsoluteMove = rasterStartX+xRelativeMove #note we convert relative to absolute moves, using the raster center that was saved in x,y,z
    yMotAbsoluteMove = rasterStartY-yyRelativeMove
    zMotAbsoluteMove = rasterStartZ-yzRelativeMove
    xRelativeMove = endX-startX
    yRelativeMove = endY-startY
    
    yyRelativeMove = yRelativeMove*math.cos(omegaRad)
    yzRelativeMove = yRelativeMove*math.sin(omegaRad)

    xEnd = xMotAbsoluteMove + xRelativeMove
    yEnd = yMotAbsoluteMove - yyRelativeMove
    zEnd = zMotAbsoluteMove - yzRelativeMove

    if (i%2 != 0): #this is to scan opposite direction for snaking
      xEndSave = xEnd
      yEndSave = yEnd
      zEndSave = zEnd
      xEnd = xMotAbsoluteMove
      yEnd = yMotAbsoluteMove
      zEnd = zMotAbsoluteMove
      xMotAbsoluteMove = xEndSave
      yMotAbsoluteMove = yEndSave
      zMotAbsoluteMove = zEndSave
    rasterFilePrefix = dataFilePrefix + "_Raster_" + str(i)
    scanWidth = float(numsteps)*img_width_per_cell
    if (procFlag):    
      #if (daq_utils.detector_id == "EIGER-16"):
      #  seqNum = int(det_lib.detector_get_seqnum())
      #else:
      #  seqNum = -1
      _thread.start_new_thread(runDialsThread,(rasterReqID, data_directory_name,
                                               filePrefix+"_Raster",
                                               i,
                                               numsteps,
                                               int(det_lib.detector_get_seqnum()))) #note the -1 last param. That eliminates rerun of eiger2cbf.
#I guess this starts the gather loop
  if (procFlag):
    rasterTimeout = 300
    timerCount = 0
    while (1):
      timerCount +=1
      if (daq_lib.abort_flag == 1):
        logger.error("caught abort waiting for raster!")
        break
      if (timerCount>rasterTimeout):
        logger.error("Raster timeout!")
        break
      time.sleep(1)
      logger.info(str(processedRasterRowCount) + "/" + str(rowCount))      
      if (processedRasterRowCount == rowCount):
        break
    rasterResult = generateGridMap(rasterRequest)     
    rasterRequest["request_obj"]["rasterDef"]["status"] = (
        RasterStatus.READY_FOR_REPROCESS.value
    )
    protocol = reqObj["protocol"]
    logger.info("protocol = " + protocol)
    try:
      gotoMaxRaster(rasterResult)
    except ValueError:
      logger.info("reprocessRaster: no max raster found, did not move gonio")
      
  rasterRequestID = rasterRequest["uid"]
  db_lib.updateRequest(rasterRequest)
  db_lib.updatePriority(rasterRequestID,-1)

  if (procFlag):
    """sleep allows for map update after gonio move, slightly longer
    than 2 sec sleep for normal raster because no gov transition here"""
    time.sleep(2.5)    
    daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
  return 1

def snakeRasterBluesky(rasterReqID, grain=""):
    global rasterRowResultsList,processedRasterRowCount

    if (daq_utils.beamline == "fmx"):
      setPvDesc("sampleProtect",0)
    setPvDesc("vectorGo", 0) #set to 0 to allow easier camonitoring vectorGo
    data_directory_name, filePrefix, file_number_start, dataFilePrefix, exptimePerCell, img_width_per_cell, wave, detDist, rasterDef, stepsize, omega, rasterStartX, rasterStartY, rasterStartZ, omegaRad, rowCount, numsteps, totalImages, rows = params_from_raster_req_id(rasterReqID)
    rasterRowResultsList = [{} for i in range(0,rowCount)]
    processedRasterRowCount = 0
    rasterEncoderMap = {}

    # a couple of items we can get independent of rasterReqID
    xbeam = getPvDesc("beamCenterX")
    ybeam = getPvDesc("beamCenterY")
    # now we do stuff with that info

    rasterRequest = db_lib.getRequestByID(rasterReqID)
    reqObj = rasterRequest["request_obj"]
    parentReqID = reqObj["parentReqID"]
    parentReqProtocol = ""
    if (parentReqID != -1):
      parentRequest = db_lib.getRequestByID(parentReqID)
      parentReqObj = parentRequest["request_obj"]
      parentReqProtocol = parentReqObj["protocol"]
      detDist = parentReqObj["detDist"]

    rasterFilePrefix = dataFilePrefix + "_Raster"
    total_exposure_time = exptimePerCell*totalImages
    detDist /= 1000  # TODO find a way to standardize detector distance settings

    if raster_flyer.detector.cam.armed.get() == 1:
        daq_lib.gui_message('Detector is in armed state from previous collection! Stopping detector, but the user '
                            'should check the most recent collection to determine if it was successful. Cancelling'
                            'this collection, retry when ready.')
        logger.warning("Detector was in the armed state prior to this attempted collection.")
        return 0
    start_time = time.time()
    arm_status = raster_flyer.detector_arm(angle_start=omega, img_width=img_width_per_cell, total_num_images=totalImages, exposure_period_per_image=exptimePerCell, file_prefix=rasterFilePrefix,
                       data_directory_name=data_directory_name, file_number_start=file_number_start, x_beam=xbeam, y_beam=ybeam, wavelength=wave, det_distance_m=detDist,
                       num_images_per_file=numsteps)
    govStatus = gov_lib.setGovRobot(gov_robot, "DA")
    arm_status.wait()
    logger.info(f"Governor move to DA and synchronous arming took {time.time() - start_time} seconds.")
    if govStatus.exception():
      logger.error(f"Problem during start-of-raster governor move, aborting! exception: {govStatus.exception()}")
      return
    raster_flyer.configure_detector(file_prefix=rasterFilePrefix, data_directory_name=data_directory_name)
    raster_flyer.detector.stage()
    procFlag = int(getBlConfig("rasterProcessFlag"))
    spotFindThreadList = []
    for row_index, row in enumerate(rows):  # since we have vectors in rastering, don't move between each row
        xMotAbsoluteMove, xEnd, yMotAbsoluteMove, yEnd, zMotAbsoluteMove, zEnd = raster_positions(row, stepsize, omegaRad, rasterStartX, rasterStartY, rasterStartZ, row_index)
        vector = {'x': (xMotAbsoluteMove, xEnd), 'y': (yMotAbsoluteMove, yEnd), 'z': (zMotAbsoluteMove, zEnd)}
        yield from zebraDaqRasterBluesky(raster_flyer, omega, numsteps, img_width_per_cell * numsteps, img_width_per_cell, exptimePerCell, rasterFilePrefix,
            data_directory_name, file_number_start, row_index, vector)
        raster_flyer.zebra.reset.put(1)  # reset after every row to make sure it is clear for the next row
        time.sleep(0.2)  # necessary for reliable row processing - see comment in commit 6793f4
        # processing
        if (procFlag):    
          if (daq_utils.detector_id == "EIGER-16"):
            seqNum = int(raster_flyer.detector.file.sequence_id.get())
          else:
            seqNum = -1
          logger.info('beginning raster processing with dozor spot_level at %s'
                       % getBlConfig(RASTER_DOZOR_SPOT_LEVEL))
          spotFindThread = Thread(target=runDozorThread,args=(data_directory_name, #TODO this can't move outside of the thread checking block
                                                              ''.join([filePrefix,"_Raster"]),
                                                              row_index,
                                                              numsteps,
                                                              seqNum,
                                                              reqObj,
                                                              rasterReqID))
          spotFindThread.start()
          spotFindThreadList.append(spotFindThread)
        send_kafka_message(f'{daq_utils.beamline}.lsdc.documents', event='event', uuid=rasterReqID, protocol="raster", row=row_index, proc_flag=procFlag)
        logger.info('row complete')
    """governor transitions:
    initiate transitions here allows for GUI sample/heat map image to update
    after moving to known position"""
    logger.debug(f'lastOnSample(): {lastOnSample()} autoRasterFlag: {autoRasterFlag}')
    if (lastOnSample() and not autoRasterFlag):
      govStatus = gov_lib.setGovRobot(gov_robot, 'SA', wait=False)
      if govStatus.exception():
        logger.error(f"Problem during end-of-raster governor move, aborting! exception: {govStatus.exception()}")
        return

      targetGovState = 'SA'
    else:
      govStatus = gov_lib.setGovRobot(gov_robot, 'DA')
      if govStatus.exception():
        logger.error(f"Problem during end-of-raster governor move, aborting! exception: {govStatus.exception()}")
        return

      targetGovState = 'DA'

    # priorities:
    # 1. make heat map visible to users correctly aligned with sample
    # 2. take snapshot for ISPyB with heat map and sample visible (governor moved to
    #    a position with backlight in) and aligned

    #data acquisition is finished, now processing and sample positioning
    if not procFlag:  # no, no processing. just move to raster start
      #must go to known position to account for windup dist. 
      logger.info("moving to raster start")
      yield from bps.mv(gonio.x, rasterStartX)
      yield from bps.mv(gonio.y, rasterStartY)
      yield from bps.mv(gonio.z, rasterStartZ)
      yield from bps.mv(gonio.omega, omega)
      logger.info("done moving to raster start")

    else:  # yes, do row processing
      if daq_lib.abort_flag != 1:
        [thread.join(timeout=120) for thread in spotFindThreadList]
      else:
        logger.info("raster aborted, do not wait for spotfind threads")
      logger.info(str(processedRasterRowCount) + "/" + str(rowCount))
      rasterResult = generateGridMap(rasterRequest)

      logger.info(f'protocol = {reqObj["protocol"]}')
      if (reqObj["protocol"] == "multiCol" or parentReqProtocol == "multiColQ"):
        if (parentReqProtocol == "multiColQ"):
          multiColThreshold  = parentReqObj["diffCutoff"]
        else:
          multiColThreshold  = reqObj["diffCutoff"]         
        gotoMaxRaster(rasterResult,multiColThreshold=multiColThreshold) 
      else:
        try:
          # go to start omega for faster heat map display
          gotoMaxRaster(rasterResult,omega=omega, rasterRequest=rasterRequest)
        except ValueError:
          #must go to known position to account for windup dist.
          logger.info("moving to raster start because of value error in gotoMaxRaster")
          yield from bps.mv(gonio.x, rasterStartX)
          yield from bps.mv(gonio.y, rasterStartY)
          yield from bps.mv(gonio.z, rasterStartZ)
          yield from bps.mv(gonio.omega, omega)
          logger.info("done moving to raster start")

      """change request status so that GUI only fills heat map when
      xrecRasterFlag PV is set"""
      rasterRequest["request_obj"]["rasterDef"]["status"] = (
          RasterStatus.READY_FOR_FILL.value
      )
      db_lib.updateRequest(rasterRequest)
      daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
      logger.info(f'setting xrecRasterFlag to: {rasterRequest["uid"]}')
    raster_flyer.detector.unstage()
    logger.info('stopping detector')

    """change request status so that GUI only takes a snapshot of
    sample plus heat map for ispyb when xrecRasterFlag PV is set"""
    rasterRequestID = rasterRequest["uid"]
    rasterRequest["request_obj"]["rasterDef"]["status"] = (
        RasterStatus.READY_FOR_SNAPSHOT.value
    )
    db_lib.updateRequest(rasterRequest)
    db_lib.updatePriority(rasterRequestID,-1)

    #ensure gov transitions have completed successfully
    timeout = 20
    gov_lib.waitGov(govStatus, timeout)
    if not(govStatus.success) or not(govs.gov.Robot.state.get() == targetGovState):
      logger.error(f"gov status check failed, did not achieve {targetGovState}")

    if (procFlag):
      """if sleep too short then black ispyb image, timing affected by speed
      of governor transition. Sleep constraint can be relaxed with gov
      transitions and concomitant GUI moved to an earlier stage."""
      if (rasterRequest["request_obj"]["rasterDef"]["numCells"]
          > getBlConfig(RASTER_NUM_CELLS_DELAY_THRESHOLD)):
        #larger rasters can delay GUI scene update
        time.sleep(getBlConfig(RASTER_LONG_SNAPSHOT_DELAY))
      else:
        time.sleep(getBlConfig(RASTER_SHORT_SNAPSHOT_DELAY))
      daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])
      time.sleep(getBlConfig(RASTER_POST_SNAPSHOT_DELAY))
    if (daq_utils.beamline == "fmx"):
      setPvDesc("sampleProtect",1)
    return 1


def snakeStepRaster(rasterReqID,grain=""): #12/19 - only tested recently, but apparently works. I'm not going to remove any commented lines.
  gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
  if not gov_status.success:
    return
  rasterRequest = db_lib.getRequestByID(rasterReqID)
  reqObj = rasterRequest["request_obj"]
  sweep_start_angle = reqObj["sweep_start"]
  sweep_end_angle = reqObj["sweep_end"]
  range_degrees = sweep_end_angle-sweep_start_angle
  imgWidth = reqObj["img_width"]
  numImagesPerStep = int((sweep_end_angle - sweep_start_angle) / imgWidth)  
  data_directory_name = str(reqObj["directory"])
  os.system("mkdir -p " + data_directory_name)
  filePrefix = str(reqObj["file_prefix"])
  file_number_start = reqObj["file_number_start"]  
  dataFilePrefix = reqObj["directory"]+"/"+reqObj["file_prefix"]  
  exptimePerCell = reqObj["exposure_time"]
  img_width_per_cell = reqObj["img_width"]
#really should read these two from hardware  
  wave = reqObj["wavelength"]
  xbeam = getPvDesc("beamCenterX")
  ybeam = getPvDesc("beamCenterY")
  rasterDef = reqObj["rasterDef"]
  stepsize = float(rasterDef["stepsize"])
  omega = float(rasterDef["omega"])
  rasterStartX = float(rasterDef["x"]) #these are real sample motor positions
  rasterStartY = float(rasterDef["y"])
  rasterStartZ = float(rasterDef["z"])
  omegaRad = math.radians(omega)
  totalImages = 0
  for i in range(len(rasterDef["rowDefs"])): #just counting images here for single detector arm
    numsteps = int(rasterDef["rowDefs"][i]["numsteps"]*numImagesPerStep)
    totalImages = totalImages+numsteps
  logger.info("total images = " + str(totalImages))
  rasterFilePrefix = dataFilePrefix
  detector_dead_time = det_lib.detector_get_deadtime()  
  total_exposure_time = exptimePerCell*totalImages
  exposureTimePerImage =  exptimePerCell - detector_dead_time
  det_lib.detector_set_num_triggers(totalImages)
  det_lib.detector_set_period(exptimePerCell)
  det_lib.detector_set_exposure_time(exposureTimePerImage)
  det_lib.detector_set_trigger_mode(3)
  det_lib.detector_setImagesPerFile(numImagesPerStep)
  daq_lib.detectorArm(sweep_start_angle,img_width_per_cell,totalImages,exptimePerCell,filePrefix,data_directory_name,file_number_start) #this waits
  
  for i in range(len(rasterDef["rowDefs"])):
    if (daq_lib.abort_flag == 1):
      return 0
    numsteps = int(rasterDef["rowDefs"][i]["numsteps"])
    startX = rasterDef["rowDefs"][i]["start"]["x"]
    endX = rasterDef["rowDefs"][i]["end"]["x"]
    startY = rasterDef["rowDefs"][i]["start"]["y"]
    endY = rasterDef["rowDefs"][i]["end"]["y"]
    deltaX = abs(endX-startX)
    deltaY = abs(endY-startY)
    if (deltaX>deltaY): #horizontal raster - I think this was decided in the rasterDefine, and we're just checking
      startY = startY + (stepsize/2.0)
      endY = startY
    else: #vertical raster
      startX = startX + (stepsize/2.0)
      endX = startX
      
    xRelativeMove = startX

    yzRelativeMove = startY*math.sin(omegaRad)
    yyRelativeMove = startY*math.cos(omegaRad)
    logger.info("x rel move = " + str(xRelativeMove))
    xMotAbsoluteMove = rasterStartX+xRelativeMove #note we convert relative to absolute moves, using the raster center that was saved in x,y,z
    yMotAbsoluteMove = rasterStartY-yyRelativeMove
    zMotAbsoluteMove = rasterStartZ-yzRelativeMove
    xRelativeMove = endX-startX
    yRelativeMove = endY-startY
    
    yyRelativeMove = yRelativeMove*math.cos(omegaRad)
    yzRelativeMove = yRelativeMove*math.sin(omegaRad)

    xEnd = xMotAbsoluteMove + xRelativeMove
    yEnd = yMotAbsoluteMove - yyRelativeMove
    zEnd = zMotAbsoluteMove - yzRelativeMove

    if (i%2 != 0): #this is to scan opposite direction for snaking
      xEndSave = xEnd
      yEndSave = yEnd
      zEndSave = zEnd
      xEnd = xMotAbsoluteMove
      yEnd = yMotAbsoluteMove
      zEnd = zMotAbsoluteMove
      xMotAbsoluteMove = xEndSave
      yMotAbsoluteMove = yEndSave
      zMotAbsoluteMove = zEndSave
    if (deltaX>deltaY): #horizontal raster - I think this was decided in the rasterDefine, and we're just checking      
      stepX = (xEnd-xMotAbsoluteMove)/numsteps
      stepY = (yEnd-yMotAbsoluteMove)/numsteps
      stepZ = (zEnd-zMotAbsoluteMove)/numsteps
    else:
      stepX = -(xEnd-xMotAbsoluteMove)/numsteps
      stepY = -(yEnd-yMotAbsoluteMove)/numsteps
      stepZ = -(zEnd-zMotAbsoluteMove)/numsteps
      
    for j in range (0,numsteps): #so maybe I have everything here and just need to bump the appropriate motors each step increment, not sure about signs
      beamline_lib.mvaDescriptor("sampleX",xMotAbsoluteMove+(j*stepX)+(stepX/2.0),"sampleY",yMotAbsoluteMove-(j*stepY)-(stepY/2.0),"sampleZ",zMotAbsoluteMove-(j*stepZ)-(stepZ/2.0))
      vectorSync()
      if (j == 0):
        RE(zebraDaqNoDet(sweep_start_angle,range_degrees,img_width_per_cell,exptimePerCell,filePrefix,data_directory_name,file_number_start,3))
      else:
        angle_start = sweep_start_angle
        scanWidth = range_degrees
        angle_end = angle_start+scanWidth        
        setPvDesc("vectorStartOmega",angle_start)
        setPvDesc("vectorEndOmega",angle_end)
        
        setPvDesc("vectorGo",1)
        vectorActiveWait()  
        vectorWait()
        zebraWait()
        setPvDesc("vectorBufferTime",3)      

  det_lib.detector_stop_acquire()
  det_lib.detector_wait()
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)      
  
  db_lib.updatePriority(rasterReqID,-1)  
  if (lastOnSample()):  
    gov_lib.setGovRobot(gov_robot, 'SA')
  return 1


def setGridRasterParams(xsep,ysep,xstep,ystep,sizex,sizey,stepsize):
  """setGridRasterParams(xsep,ysep,xstep,ystep,sizex,sizey,stepsize)"""
  db_lib.setBeamlineConfigParam("fmx","gridRasterXSep",float(xsep))
  db_lib.setBeamlineConfigParam("fmx","gridRasterYSep",float(ysep))
  db_lib.setBeamlineConfigParam("fmx","gridRasterXStep",int(xstep))
  db_lib.setBeamlineConfigParam("fmx","gridRasterYStep",int(ystep))
  db_lib.setBeamlineConfigParam("fmx","gridRasterSizeX",float(sizex))
  db_lib.setBeamlineConfigParam("fmx","gridRasterSizeY",float(sizey))
  db_lib.setBeamlineConfigParam("fmx","gridRasterStepsize",float(stepsize))

def printGridRasterParams():
  """printGridRasterParams()"""

  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterXSep"))
  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterYSep"))
  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterXStep"))
  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterYStep"))
  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterSizeX"))
  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterSizeY"))
  logger.info(db_lib.getBeamlineConfigParam("fmx","gridRasterStepsize"))
  

def gridRaster(currentRequest):
  gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
  if not gov_status.success:
    return
  
  sampleID = currentRequest["sample"]  
  reqObj = currentRequest["request_obj"]
  omega = beamline_lib.motorPosFromDescriptor("omega")
  omegaRad = math.radians(omega)
  xwells = int(db_lib.getBeamlineConfigParam("fmx","gridRasterXStep"))
  ywells = int(db_lib.getBeamlineConfigParam("fmx","gridRasterYStep"))        
  xsep = float(db_lib.getBeamlineConfigParam("fmx","gridRasterXSep"))
  ysep = float(db_lib.getBeamlineConfigParam("fmx","gridRasterYSep"))
  sizex = float(db_lib.getBeamlineConfigParam("fmx","gridRasterSizeX"))
  sizey = float(db_lib.getBeamlineConfigParam("fmx","gridRasterSizeY"))        
  stepsize = float(db_lib.getBeamlineConfigParam("fmx","gridRasterStepsize"))
  rasterStartX = beamline_lib.motorPosFromDescriptor("sampleX") #these are real sample motor positions
  rasterStartY = beamline_lib.motorPosFromDescriptor("sampleY")
  rasterStartZ = beamline_lib.motorPosFromDescriptor("sampleZ")
  yzRelativeMove = ysep*math.sin(omegaRad)
  yyRelativeMove = ysep*math.cos(omegaRad)
  for i in range (0,ywells):
    for j in range (0,xwells):
      beamline_lib.mvaDescriptor("sampleX",rasterStartX+(j*xsep),"sampleY",rasterStartY+(i*yyRelativeMove),"sampleZ",rasterStartZ+(i*yzRelativeMove))
      beamline_lib.mvaDescriptor("omega",omega)      
      rasterReqID = defineRectRaster(currentRequest,sizex,sizey,stepsize)      
      RE(snakeRaster(rasterReqID))


def runRasterScan(currentRequest,rasterType="", width=0, height=0, step_size=10, omega_rel=0): #this actually defines and runs
  sampleID = currentRequest["sample"]
  if (rasterType=="Fine"):
    daq_lib.set_field("xrecRasterFlag","100")    
    rasterReqID = defineRectRaster(currentRequest,90,90,10)
    RE(snakeRaster(rasterReqID))
  elif (rasterType=="Coarse"):
    daq_lib.set_field("xrecRasterFlag","100")    
    rasterReqID = defineRectRaster(currentRequest,630,390,30)     
    RE(snakeRaster(rasterReqID))
  elif (rasterType=="autoVector"):
    daq_lib.set_field("xrecRasterFlag","100")    
    rasterReqID = defineRectRaster(currentRequest,615,375,15)     
    RE(snakeRaster(rasterReqID))
  elif (rasterType=="Line"):  
    daq_lib.set_field("xrecRasterFlag","100")    
    beamline_lib.mvrDescriptor("omega",90)
    rasterReqID = defineRectRaster(currentRequest,10,290,10)    
    RE(snakeRaster(rasterReqID))
    daq_lib.set_field("xrecRasterFlag","100")    
  elif (rasterType=="Custom"):
    daq_lib.set_field("xrecRasterFlag","100")
    beamline_lib.mvrDescriptor("omega",omega_rel)
    rasterReqID = defineRectRaster(currentRequest, width+step_size, height+step_size, step_size)
    RE(snakeRaster(rasterReqID))
  else:
    rasterReqID = getXrecLoopShape(currentRequest)
    logger.info("snake raster " + str(rasterReqID))
    time.sleep(1) #I think I really need this, not sure why
    RE(snakeRaster(rasterReqID))

def get_score_vals(cellResults, scoreOption):
  """
  Returns a numpy 1d-array that stores the selected scores as a flattened array
  """
  score_vals = np.zeros(len(cellResults))
  for i, res in enumerate(cellResults):
    try:
      score_vals[i] = float(res[scoreOption])
    except TypeError:
      logger.debug(f"Option {scoreOption} not found for {res=}")
  return score_vals

def get_score_index(score_vals: "np.ndarray", scoreOption, indices=None):
  """
  Returns the maximum or minimum score value in the 1d array of scores and the corresponding index
  If specific indices are provided the max/min score will be selected from those indices

  """
  if indices:
    score_vals = score_vals[indices]
  if scoreOption == "d_min":
    # If value is -1 replace with inf so that it is not considered for np.min
    score_vals = np.where(score_vals == -1, np.inf, score_vals) 
    scoreVal = np.min(score_vals)
    max_index = np.argmin(score_vals)
  else:
    scoreVal = np.max(score_vals)
    max_index = np.argmax(score_vals)
  
  max_index = max_index if not indices else indices[max_index] 

  return scoreVal, max_index

def get_gonio_pos_from_raster_result(cell_results, raster_map, index):
  """
  Returns the motor positions and the cell which corresponds to the index 
  given in the cell_results list
  """
  hot_file = cell_results[index]["cellMapKey"]
  hot_coords = raster_map[hot_file]     
  x = hot_coords["x"]
  y = hot_coords["y"]
  z = hot_coords["z"]
  logger.info("goto " + str(x) + " " + str(y) + " " + str(z))
  return hot_file, (x, y, z)

def gotoMaxRaster(rasterResult,multiColThreshold=None,**kwargs):
  global autoVectorCoarseCoords,autoVectorFlag, max_col, face_on_max_coords, ortho_max_coords
  
  requestID = rasterResult["request"]
  if (rasterResult["result_obj"]["rasterCellResults"]['resultObj'] == None):
    logger.info("no raster result!!\n")
    raise ValueError("raster result object is None")
  logger.info("in gotomax")
  
  cellResults = rasterResult["result_obj"]["rasterCellResults"]['resultObj']
  rasterMap = rasterResult["result_obj"]["rasterCellMap"]  
  rasterScoreFlag = int(db_lib.beamlineInfo(daq_utils.beamline,'rasterScoreFlag')["index"])
  if (rasterScoreFlag==0):
    scoreOption = "spot_count_no_ice"
  elif (rasterScoreFlag==1):
    scoreOption = "d_min"
  else:
    scoreOption = "total_intensity"
  max_index = None
  score_vals = get_score_vals(cellResults, scoreOption)
  score_val, max_index = get_score_index(score_vals, scoreOption)

  if multiColThreshold is not None:
    logger.info("doing multicol")
    for index in np.where(score_vals > multiColThreshold)[0]:
      hitFile = cellResults[index]["cellMapKey"]
      hitCoords = rasterMap[hitFile]
      parent_req_id = rasterResult['result_obj']["parentReqID"]
      if parent_req_id == -1:
        addMultiRequestLocation(requestID, hitCoords, index)
      else:
        addMultiRequestLocation(parent_req_id, hitCoords, index)

  
  if max_index:
    x, y, z = run_auto_raster(max_index, score_vals, scoreOption, cellResults, rasterMap, **kwargs)
    if 'omega' in kwargs:
      beamline_lib.mvaDescriptor("sampleX",x,
                                 "sampleY",y,
                                 "sampleZ",z,
                                 "omega",kwargs['omega'])
    else: beamline_lib.mvaDescriptor("sampleX",x,"sampleY",y,"sampleZ",z)

    if (autoVectorFlag): #if we found a hotspot, then look again at cellResults for coarse vector start and end
      run_auto_vector(score_val, cellResults, scoreOption, rasterMap)

  else:
    raise ValueError("No max position found for gonio move")

def run_auto_raster(max_index, score_vals, scoreOption, cellResults, rasterMap, **kwargs):
  global max_col, face_on_max_coords, ortho_max_coords
  hotFile, (x, y, z) = get_gonio_pos_from_raster_result(cellResults, rasterMap, max_index)
  if "rasterRequest" in kwargs and autoRasterFlag:
    # Update the raster request with the location of the max raster image and co-ordinates.
    # NOTE: In the optimized autoraster, two 2D rasters are collected, face on and orthogonal.
    # Both rasters have the same number of columns, we save the column number of the hot cell (max_col)
    # in the face on raster then look for the hot cell in the orthogonal raster in the same 
    # column. This is to emulate the original autoraster but leaves room for other ways of selecting
    # points for standard collection
    rasterDef = kwargs["rasterRequest"]["request_obj"]["rasterDef"]

    col = get_raster_max_col(rasterDef, max_index)

    
    # Set the column index for the face on raster
    if max_col is None:
      max_col = col
      face_on_max_coords = (x, y, z)
    else: 
      # max_col should be available for orthogonal rasters
      # Find maximum in col defined in max_col and then reset max_col
      indices = get_flattened_indices_of_max_col(rasterDef, max_col)
      score_val, max_index = get_score_index(score_vals, scoreOption, indices)
      hotFile, (x, y, z) = get_gonio_pos_from_raster_result(cellResults, rasterMap, max_index)
      ortho_max_coords = (x, y, z)
      logger.info(f"ORTHO DEBUG: {max_col=}\n {indices=}\n {max_index=}\n {ortho_max_coords=}")
      max_col = None

    kwargs["rasterRequest"]["request_obj"]["max_raster"] = {
      "file" : hotFile,
      "coords": [x, y, z],
      "index": int(max_index)
    }
    if "omega" in kwargs:
      kwargs["rasterRequest"]["request_obj"]["max_raster"]["omega"] = kwargs["omega"]

    db_lib.updateRequest(kwargs["rasterRequest"])

    req = db_lib.getRequestByID(kwargs["rasterRequest"]["uid"])
    logger.info(f'MAX RASTER INFO: {req["request_obj"]["max_raster"]["file"]} {req["request_obj"]["max_raster"]["coords"]}')
  return x, y, z


def run_auto_vector(ceiling, cellResults, scoreOption, rasterMap):
  xminColumn = [] #these are the "line rasters" of the ends of threshold points determined by the first pass on the raster results
  xmaxColumn = []
  vectorThreshold = 0.7*ceiling
  xmax = -1000000
  xmin = 1000000
  ymin = 0
  ymax = 0
  zmin = 0
  zmax = 0
  for i in range (0,len(cellResults)): #first find the xmin and xmax of threshold (left and right ends of vector)
    try:
      scoreVal = float(cellResults[i][scoreOption])
    except TypeError:
      scoreVal = 0.0
    if (scoreVal > vectorThreshold):
      hotFile = cellResults[i]["cellMapKey"]
      hotCoords = rasterMap[hotFile]             
      x = hotCoords["x"]
      if (x<xmin):
        xmin = x
      if (x>xmax):
        xmax = x
  for i in range (0,len(cellResults)): #now grab the columns of cells on xmin and xmax, like line scan results on the ends
    fileKey = cellResults[i]["cellMapKey"]
    coords = rasterMap[fileKey]
    x = coords["x"]
    if (x == xmin): #cell is in left column
      xEdgeCellResult = {"coords":coords,"processingResults":cellResults[i]}
      xminColumn.append(xEdgeCellResult)
    if (x == xmax):
      xEdgeCellResult = {"coords":coords,"processingResults":cellResults[i]}
      xmaxColumn.append(xEdgeCellResult)
  maxIndex = -10000
  minIndex = 10000
  for i in range (0,len(xminColumn)): #find the midpoint of the left column that is in the threshold range
    try:
      scoreVal = float(xminColumn[i]["processingResults"][scoreOption])
    except TypeError:
      scoreVal = 0.0
    if (scoreVal > vectorThreshold):
      if (minIndex<0): #you only need the first one that beats the threshold
        minIndex = i
      if (i>maxIndex):
        maxIndex = i
  middleIndex = int((minIndex+maxIndex)/2)
  xmin = xminColumn[middleIndex]["coords"]["x"]
  ymin = xminColumn[middleIndex]["coords"]["y"]
  zmin = xminColumn[middleIndex]["coords"]["z"]                            
  for i in range (0,len(xmaxColumn)): #do same as above for right column
    try:
      scoreVal = float(xmaxColumn[i]["processingResults"][scoreOption])
    except TypeError:
      scoreVal = 0.0
    if (scoreVal > vectorThreshold):
      if (minIndex<0):
        minIndex = i
      if (i>maxIndex):
        maxIndex = i
  middleIndex = int((minIndex+maxIndex)/2)
  xmax = xmaxColumn[middleIndex]["coords"]["x"]
  ymax = xmaxColumn[middleIndex]["coords"]["y"]
  zmax = xmaxColumn[middleIndex]["coords"]["z"]                            
      
  autoVectorCoarseCoords = {"start":{"x":xmin,"y":ymin,"z":zmin},"end":{"x":xmax,"y":ymax,"z":zmax}}

def addMultiRequestLocation(parentReqID,hitCoords,locIndex): #rough proto of what to pass here for details like how to organize data
  parentRequest = db_lib.getRequestByID(parentReqID)
  sampleID = parentRequest["sample"]

  logger.info(str(sampleID))
  logger.info(hitCoords)
  currentOmega = round(beamline_lib.motorPosFromDescriptor("omega"),2)
  dataDirectory = parentRequest["request_obj"]['directory']+"multi_"+str(locIndex)
  runNum = parentRequest["request_obj"]['runNum']
  tempnewStratRequest = daq_utils.createDefaultRequest(sampleID)
  ss = parentRequest["request_obj"]["sweep_start"]
  sweepStart = ss - 2.5
  sweepEnd = ss + 2.5
  imgWidth = parentRequest["request_obj"]['img_width']
  exptime = parentRequest["request_obj"]['exposure_time']
  currentDetDist = parentRequest["request_obj"]['detDist']
  
  newReqObj = tempnewStratRequest["request_obj"]
  newReqObj["sweep_start"] = sweepStart
  newReqObj["sweep_end"] = sweepEnd
  newReqObj["img_width"] = imgWidth
  newReqObj["exposure_time"] = exptime
  newReqObj["detDist"] = currentDetDist
  newReqObj["directory"] = dataDirectory  
  newReqObj["pos_x"] = hitCoords['x']
  newReqObj["pos_y"] = hitCoords['y']
  newReqObj["pos_z"] = hitCoords['z']
  newReqObj["fastDP"] = True
  newReqObj["fastEP"] = False
  newReqObj["dimple"] = False    
  newReqObj["xia2"] = False
  newReqObj["runNum"] = runNum
  newRequestUID = db_lib.addRequesttoSample(sampleID,newReqObj["protocol"],daq_utils.owner,newReqObj,priority=6000,proposalID=daq_utils.getProposalID()) # a higher priority
  
    
#these next three differ a little from the gui. the gui uses isChecked, b/c it was too intense to keep hitting the pv, also screen pix vs image pix
#careful here, I'm hardcoding the view I think we'll use for definePolyRaster, which is only routine that uses this. 
def getCurrentFOV(): #used only by 4 routines below - BUT THIS IS A GUESS! 
  fov = {"x":0.0,"y":0.0}
  fov["x"] = daq_utils.lowMagFOVx/2.0 #low mag zoom for xrecloopfind
  fov["y"] = daq_utils.lowMagFOVy/2.0
  
  return fov


def screenXmicrons2pixels(microns):
  fov = getCurrentFOV()
  fovX = fov["x"]
  return int(round(microns*(daq_utils.lowMagPixX/fovX)))

def screenYmicrons2pixels(microns):
  fov = getCurrentFOV()
  fovY = fov["y"]
  return int(round(microns*(daq_utils.lowMagPixY/fovY)))  


def screenXPixels2microns(pixels):
  fov = getCurrentFOV()
  fovX = fov["x"]
  return float(pixels)*(fovX/daq_utils.lowMagPixX)

def screenYPixels2microns(pixels):
  fov = getCurrentFOV()
  fovY = fov["y"]
  return float(pixels)*(fovY/daq_utils.lowMagPixY)

def defineTiledRaster(rasterDef,numsteps_h,numsteps_v,origRasterCenterScreenX,origRasterCenterScreenY): #I need this to redefine composite for tiling. Much of the reqObf can stay same.
  
  rasterDef["rowDefs"] = []
  stepsize = rasterDef["stepsize"]
  point_offset_x = origRasterCenterScreenX-(numsteps_h*stepsize)/2.0
  point_offset_y = origRasterCenterScreenY-(numsteps_v*stepsize)/2.0
  if (numsteps_v > numsteps_h): #vertical raster
    for i in range(numsteps_h):
      vectorStartX = point_offset_x+(i*stepsize)
      vectorEndX = vectorStartX
      vectorStartY = point_offset_y
      vectorEndY = vectorStartY + (numsteps_v*stepsize)
      newRowDef = {"start":{"x": vectorStartX,"y":vectorStartY},"end":{"x":vectorEndX,"y":vectorEndY},"numsteps":numsteps_v}
      rasterDef["rowDefs"].append(newRowDef)
  else: #horizontal raster
    for i in range(numsteps_v):
      vectorStartX = point_offset_x
      vectorEndX = vectorStartX + (numsteps_h*stepsize)
      vectorStartY = point_offset_y+(i*stepsize)
      vectorEndY = vectorStartY
      newRowDef = {"start":{"x": vectorStartX,"y":vectorStartY},"end":{"x":vectorEndX,"y":vectorEndY},"numsteps":numsteps_h}
      rasterDef["rowDefs"].append(newRowDef)
  rasterDef["status"] = RasterStatus.DRAWN.value # this will tell clients that the raster should be displayed.      
  return rasterDef

def defineRectRaster(currentRequest,raster_w_s,raster_h_s,stepsizeMicrons_s,xoff=0.0,yoff=0.0,zoff=0.0): #maybe point_x and point_y are image center? #everything can come as microns, make this a horz vector scan, note this never deals with pixels.
  
  sampleID = currentRequest["sample"]
  sample = db_lib.getSampleByID(sampleID)
  try:
    propNum = sample["proposalID"]
  except KeyError:
    propNum = 999999
  raster_h = float(raster_h_s)
  raster_w = float(raster_w_s)
  stepsize = float(stepsizeMicrons_s)
  beamWidth = stepsize
  beamHeight = stepsize
  rasterDef = {"beamWidth":beamWidth,"beamHeight":beamHeight,"status":RasterStatus.NEW.value,"x":beamline_lib.motorPosFromDescriptor("sampleX")+xoff,"y":beamline_lib.motorPosFromDescriptor("sampleY")+yoff,"z":beamline_lib.motorPosFromDescriptor("sampleZ")+zoff,"omega":beamline_lib.motorPosFromDescriptor("omega"),"stepsize":stepsize,"rowDefs":[]} 
  numsteps_h = int(raster_w/stepsize)
  numsteps_v = int(raster_h/stepsize) #the numsteps is decided in code, so is already odd
  rasterDef["numCells"] = numsteps_h * numsteps_v
  point_offset_x = -(numsteps_h*stepsize)/2.0
  point_offset_y = -(numsteps_v*stepsize)/2.0
  if (numsteps_v > numsteps_h): #vertical raster
    for i in range(numsteps_h):
      vectorStartX = point_offset_x+(i*stepsize)
      vectorEndX = vectorStartX
      vectorStartY = point_offset_y
      vectorEndY = vectorStartY + (numsteps_v*stepsize)
      newRowDef = {"start":{"x": vectorStartX,"y":vectorStartY},"end":{"x":vectorEndX,"y":vectorEndY},"numsteps":numsteps_v}
      rasterDef["rowDefs"].append(newRowDef)
  else: #horizontal raster
    for i in range(numsteps_v):
      vectorStartX = point_offset_x
      vectorEndX = vectorStartX + (numsteps_h*stepsize)
      vectorStartY = point_offset_y+(i*stepsize)
      vectorEndY = vectorStartY
      newRowDef = {"start":{"x": vectorStartX,"y":vectorStartY},"end":{"x":vectorEndX,"y":vectorEndY},"numsteps":numsteps_h}
      rasterDef["rowDefs"].append(newRowDef)

  tempnewRasterRequest = daq_utils.createDefaultRequest(sampleID, basePath=currentRequest["request_obj"]["basePath"])
  reqObj = tempnewRasterRequest["request_obj"]
  reqObj["protocol"] = "raster"
  reqObj["exposure_time"] = getBlConfig("rasterDefaultTime")
  reqObj["img_width"] = getBlConfig("rasterDefaultWidth")
  reqObj["attenuation"] = getBlConfig("rasterDefaultTrans")
  reqObj["directory"] = reqObj["directory"]+"/rasterImages/"
  if (numsteps_h == 1): #column raster
    reqObj["file_prefix"] = reqObj["file_prefix"]+"_l"
    rasterDef["rasterType"] = "column"
  else:
    reqObj["file_prefix"] = reqObj["file_prefix"]+"_r"
    rasterDef["rasterType"] = "normal"
  reqObj["rasterDef"] = rasterDef #should this be something like self.currentRasterDef?
  reqObj["rasterDef"]["status"] = RasterStatus.DRAWN.value # this will tell clients that the raster should be displayed.
  runNum = db_lib.incrementSampleRequestCount(sampleID)
  reqObj["runNum"] = runNum
  reqObj["parentReqID"] = currentRequest["uid"]
  reqObj["xbeam"] = currentRequest['request_obj']["xbeam"]
  reqObj["ybeam"] = currentRequest['request_obj']["ybeam"]
  reqObj["wavelength"] = currentRequest['request_obj']["wavelength"]
  # request params to save the file and location of max_raster cell
  # This data is saved as part of the raster request and not result is because analysisstore does not allow updating
  reqObj["max_raster"] = {
    "file": None, 
    "coords": [None, None, None],
    "index": None,
    "omega": None,
  }
  newRasterRequestUID = db_lib.addRequesttoSample(sampleID,reqObj["protocol"],daq_utils.owner,reqObj,priority=5000,proposalID=propNum)
  daq_lib.set_field("xrecRasterFlag",newRasterRequestUID)
  time.sleep(1)
  return newRasterRequestUID



def collectSpec(filename,gotoSA=True):
  """collectSpec(filenamePrefix) : collect a spectrum, save to file"""  
  gov_lib.setGovRobot(gov_robot, 'XF')
  daq_lib.open_shutter()
  setPvDesc("mercuryEraseStart",1)
  while (1):
    if (getPvDesc("mercuryReadStat") == 0):
      break
    time.sleep(0.05)
  specArray = getPvDesc("mercurySpectrum")
  plt.plot(specArray)
  plt.show(block=False)
  nowtime_s = str(int(time.time()))
  specFileName = filename + "_" + nowtime_s + ".txt"
  specFile = open(specFileName,"w+")
  channelCount = len(specArray)
  for i in range (0,channelCount):
    if (i == 0):
      specFile.write(str(specArray[i]))
    else:
      specFile.write("," + str(specArray[i]))
  specFile.close()
  daq_lib.close_shutter()
  if (gotoSA):
    gov_lib.setGovRobot(gov_robot, 'SA')

    
def eScan(energyScanRequest):
  plt.clf()
  sampleID = energyScanRequest["sample"]
  reqObj = energyScanRequest["request_obj"]
  exptime = reqObj['exposure_time']
  targetEnergy = reqObj['scanEnergy'] *1000.0
  stepsize = reqObj['stepsize']
  steps = reqObj['steps']
  left = -((steps-1)*stepsize)/2  # there are actually (steps-1) intervals
  right = ((steps-1)*stepsize)/2
  mcaRoiLo = reqObj['mcaRoiLo']
  mcaRoiHi = reqObj['mcaRoiHi']
  setPvDesc("mcaRoiLo",mcaRoiLo)
  setPvDesc("mcaRoiHi",mcaRoiHi)      
  
  logger.info("energy scan for " + str(targetEnergy))
  scan_element = reqObj['element']
  beamline_lib.mvaDescriptor("energy",targetEnergy)
  gov_status = gov_lib.setGovRobot(gov_robot, 'XF')
  if not gov_status.success:
    daq_lib.gui_message('Governor did not reach XF state')
    return
  daq_lib.open_shutter()
  scanID = RE(bp.rel_scan([mercury],vdcm.e,left,right,steps),[LivePlot("mercury_mca_rois_roi0_count")])
  daq_lib.close_shutter()
  if (lastOnSample()):  
    gov_lib.setGovRobot(gov_robot, 'SA')
  scanData = db[scanID[0]]
  for ev in scanData.events():
    if ('mercury_mca_spectrum' in ev['data']):
      logger.info('%s %s' % (ev['seq_num'], sum(ev['data']['mercury_mca_spectrum'])))
      
  scanDataTable = scanData.table()
#these next lines only make sense for the mca
  nowtime_s = str(int(time.time()))
  specFileName = "spectrumData_" + nowtime_s + ".txt"
  specFile = open(specFileName,"w+")
  specFile.write(str(len(scanDataTable.mercury_mca_rois_roi0_count)) + "\n")
  for i in range (0,len(scanDataTable.mercury_mca_rois_roi0_count)):
    specFile.write(str(scanDataTable.vdcm_e[i+1]) + " " + str(scanDataTable.mercury_mca_rois_roi0_count[i+1]))
    specFile.write("\n")
  specFile.close()
  eScanResultObj = {}
  eScanResultObj["databrokerID"] = scanID
  eScanResultObj["sample_id"] = sampleID  
  eScanResultID = db_lib.addResultforRequest("eScanResult",energyScanRequest["uid"], daq_utils.owner,result_obj=eScanResultObj,proposalID=daq_utils.getProposalID(),beamline=daq_utils.beamline)
  eScanResult = db_lib.getResult(eScanResultID)
  logger.info(scanDataTable)
  if (reqObj["runChooch"]):
    chooch_prefix = "choochData1_" + nowtime_s
    choochOutfileName = chooch_prefix+".efs"
    choochInputFileName = specFileName    
    comm_s = "chooch -e %s -o %s %s" % (scan_element, choochOutfileName,choochInputFileName)
    logger.info(comm_s)
    choochInputData_x = []
    choochInputData_y = []
    infl = 0
    peak = 0
    f2prime_infl = 0
    fprime_infl = 0
    f2prime_peak = 0
    fprime_peak = 0
    choochInputFile = open(choochInputFileName,"r")
    for outputLine in choochInputFile.readlines():
      tokens = outputLine.split()
      if (len(tokens) == 2): #not a very elegant way to get past the first two lines that I don't need.    
        choochInputData_x.append(float(tokens[0]))
        choochInputData_y.append(float(tokens[1]))
    choochInputFile.close()
    for outputline in os.popen(comm_s).readlines():
      logger.info(outputline)
      tokens = outputline.split()    
      if (len(tokens)>4):
        if (tokens[1] == "peak"):
          peak = float(tokens[3])
          fprime_peak = float(tokens[7])
          f2prime_peak = float(tokens[5])        
        elif (tokens[1] == "infl"):
          infl = float(tokens[3])
          fprime_infl = float(tokens[7])
          f2prime_infl = float(tokens[5])        
        else:
          pass
    choochResultObj = {}
    choochResultObj["infl"] = infl
    choochResultObj["peak"] = peak
    choochResultObj["f2prime_infl"] = f2prime_infl
    choochResultObj["fprime_infl"] = fprime_infl
    choochResultObj["f2prime_peak"] = f2prime_peak
    choochResultObj["fprime_peak"] = fprime_peak
    choochResultObj["sample_id"] = sampleID
    if (not os.path.exists(choochOutfileName)):
      logger.error(f'chooch could not successfully produce a file called {choochOutfileName}. not drawing a plot.')
      return
    else:
      choochOutFile = open(choochOutfileName,"r")    
    chooch_graph_x = []
    chooch_graph_y1 = []
    chooch_graph_y2 = []
    for outLine in choochOutFile.readlines():
      tokens = outLine.split()
      chooch_graph_x.append(float(tokens[0]))
      chooch_graph_y1.append(float(tokens[1]))
      chooch_graph_y2.append(float(tokens[2]))
    choochOutFile.close()
    choochResultObj["choochOutXAxis"] = chooch_graph_x
    choochResultObj["choochOutY1Axis"] = chooch_graph_y1
    choochResultObj["choochOutY2Axis"] = chooch_graph_y2
    choochResultObj["choochInXAxis"] = choochInputData_x
    choochResultObj["choochInYAxis"] = choochInputData_y  
    choochResultID = db_lib.addResultforRequest("choochResult",energyScanRequest["uid"], daq_utils.owner,result_obj=choochResultObj,proposalID=daq_utils.getProposalID(),beamline=daq_utils.beamline)
    choochResult = db_lib.getResult(choochResultID)
    daq_lib.set_field("choochResultFlag",choochResultID)

def vectorZebraScan(vecRequest):
  scannerType = getBlConfig("scannerType")
  if (scannerType == "PI"):
    vectorZebraScanFine(vecRequest)
  else:
    finalize_plan = finalize_wrapper(vectorZebraScanNormal(vecRequest), bps.mv(flyer.detector.cam.acquire, 0))
    yield from finalize_plan

    
def vectorZebraScanFine(vecRequest):
  gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
  if not gov_status.success:
    return
  
  reqObj = vecRequest["request_obj"]
  file_prefix = str(reqObj["file_prefix"])
  data_directory_name = str(reqObj["directory"])
  file_number_start = reqObj["file_number_start"]
  
  sweep_start_angle = reqObj["sweep_start"]
  sweep_end_angle = reqObj["sweep_end"]
  imgWidth = reqObj["img_width"]
  expTime = reqObj["exposure_time"]
  numImages = int((sweep_end_angle - sweep_start_angle) / imgWidth)
  x_vec_start=reqObj["vectorParams"]["vecStart"]["x"]
  y_vec_start=reqObj["vectorParams"]["vecStart"]["y"]
  z_vec_start=reqObj["vectorParams"]["vecStart"]["z"]
  x_vec_end=reqObj["vectorParams"]["vecEnd"]["x"]
  y_vec_end=reqObj["vectorParams"]["vecEnd"]["y"]
  z_vec_end=reqObj["vectorParams"]["vecEnd"]["z"]

  xCenterCoarse = (x_vec_end+x_vec_start)/2.0
  yCenterCoarse = (y_vec_end+y_vec_start)/2.0
  zCenterCoarse = (z_vec_end+z_vec_start)/2.0
  beamline_lib.mvaDescriptor("sampleX",xCenterCoarse,"sampleY",yCenterCoarse,"sampleZ",zCenterCoarse)
  xRelLen = x_vec_end-x_vec_start
  xRelStart = -xRelLen/2.0
  xRelEnd = -xRelStart
  yRelLen = y_vec_end-y_vec_start
  yRelStart = -yRelLen/2.0
  yRelEnd = -yRelStart
  zRelLen = z_vec_end-z_vec_start
  zRelStart = -zRelLen/2.0
  zRelEnd = -zRelStart

  det_lib.detector_set_num_triggers(numImages)
  det_lib.detector_set_trigger_mode(3)
  det_lib.detector_setImagesPerFile(1000)  
  daq_lib.detectorArm(sweep_start_angle,imgWidth,numImages,expTime,file_prefix,data_directory_name,file_number_start) #this waits

  zebraVecDaqSetup(sweep_start_angle,imgWidth,expTime,numImages,file_prefix,data_directory_name,file_number_start)  
  

  total_exposure_time=expTime*numImages
  trajPoints = int(total_exposure_time/.005)
  totalScanWidthX = xRelLen
  totalScanWidthY = yRelLen
  totalScanWidthZ = zRelLen
  xRelativeMoveFine = xRelStart
  yRelativeMoveFine = yRelStart
  zRelativeMoveFine = zRelStart
  beamline_lib.mvaDescriptor("fineX",xRelativeMoveFine,"fineY",yRelativeMoveFine,"fineZ",zRelativeMoveFine)      
  setPvDesc("fineXPoints",trajPoints)
  setPvDesc("fineYPoints",trajPoints)
  setPvDesc("fineZPoints",trajPoints)
  setPvDesc("fineXAmp",totalScanWidthX)
  setPvDesc("fineYAmp",totalScanWidthY)
  setPvDesc("fineZAmp",totalScanWidthZ)
  setPvDesc("fineXOffset",xRelativeMoveFine)
  setPvDesc("fineYOffset",yRelativeMoveFine)
  setPvDesc("fineZOffset",zRelativeMoveFine)
  setPvDesc("fineXSendWave",1)
  time.sleep(0.1)    
  setPvDesc("fineYSendWave",1)
  time.sleep(0.1)    
  setPvDesc("fineZSendWave",1)
  time.sleep(0.1)    
  #move xyz fine mots to relative from centered raster
  setPvDesc("fineXVecGo",1)
  time.sleep(0.1)            
  setPvDesc("fineYVecGo",1)
  time.sleep(0.1)            
  setPvDesc("fineZVecGo",1)    
  time.sleep(0.1)        
  setPvDesc("zebraPulseMax",numImages) #moved this
  vectorSync()
  setPvDesc("vectorStartOmega",sweep_start_angle)
  setPvDesc("vectorEndOmega",sweep_end_angle)
  setPvDesc("vectorframeExptime",expTime*1000.0)
  setPvDesc("vectorNumFrames",numImages)
  setPvDesc("vectorGo",1)
  vectorActiveWait()    
  vectorWait()
  zebraWait()
  zebraWaitDownload(numImages)
  time.sleep(2.0)
  det_lib.detector_stop_acquire()
  det_lib.detector_wait()
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)      
  
  #raster centered, now zero motors
  beamline_lib.mvaDescriptor("fineX",0,"fineY",0,"fineZ",0)  
  
  if (lastOnSample()):  
    gov_lib.setGovRobot(gov_robot, 'SA')
    

def vectorZebraScanNormal(vecRequest): 
  reqObj = vecRequest["request_obj"]
  file_prefix = str(reqObj["file_prefix"])
  data_directory_name = str(reqObj["directory"])
  data_path = str(reqObj["dataPath"])
  file_number_start = reqObj["file_number_start"]
  
  sweep_start_angle = reqObj["sweep_start"]
  sweep_end_angle = reqObj["sweep_end"]
  imgWidth = reqObj["img_width"]
  expTime = reqObj["exposure_time"]
  numImages = int((sweep_end_angle - sweep_start_angle) / imgWidth)
  scanWidth = float(numImages)*imgWidth

  x_beam = getPvDesc("beamCenterX")
  y_beam = getPvDesc("beamCenterY")
  wavelength = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)
  det_distance_m = beamline_lib.motorPosFromDescriptor("detectorDist")
  # TODO replace this area with gatherStandardVectorParams
  det_distance_m /= 1000  # on all beamlines, detectorDist is in mm so convert distance to m
  if daq_utils.beamline in ("nyx", "fmx"):
      transmission = getPvDesc("RI_Atten_SP")
  else:
      transmission = getPvDesc("transmissionRBV")

  reqObj["vectorParams"]["x_beam"]=x_beam
  reqObj["vectorParams"]["y_beam"]=y_beam
  reqObj["vectorParams"]["wavelength"]=wavelength
  reqObj["vectorParams"]["det_distance_m"]=det_distance_m
  reqObj["vectorParams"]["transmission"]=transmission

  yield from zebraDaqBluesky(flyer,sweep_start_angle,numImages,scanWidth,imgWidth,expTime,file_prefix,data_directory_name,file_number_start, reqObj["vectorParams"], data_path)
  if (lastOnSample()):  
    gov_lib.setGovRobot(gov_robot, 'SA')

def vectorZebraStepScan(vecRequest):
  gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
  if not gov_status.success:
    return
  
  reqObj = vecRequest["request_obj"]
  file_prefix = str(reqObj["file_prefix"])
  data_directory_name = str(reqObj["directory"])
  file_number_start = reqObj["file_number_start"]  
  sweep_start_angle = reqObj["sweep_start"]
  sweep_end_angle = reqObj["sweep_end"]
  imgWidth = reqObj["img_width"]
  expTime = reqObj["exposure_time"]
  numImages = int((sweep_end_angle - sweep_start_angle) / imgWidth)
  x_vec_start=reqObj["vectorParams"]["vecStart"]["x"]
  y_vec_start=reqObj["vectorParams"]["vecStart"]["y"]
  z_vec_start=reqObj["vectorParams"]["vecStart"]["z"]
  x_vec_end=reqObj["vectorParams"]["vecEnd"]["x"]
  y_vec_end=reqObj["vectorParams"]["vecEnd"]["y"]
  z_vec_end=reqObj["vectorParams"]["vecEnd"]["z"]
  x_vec = reqObj["vectorParams"]["x_vec"]
  y_vec = reqObj["vectorParams"]["y_vec"]
  z_vec = reqObj["vectorParams"]["z_vec"]  
  numVecSteps = reqObj["vectorParams"]["fpp"]
  scanWidthPerStep = (sweep_end_angle-sweep_start_angle)/float(numVecSteps)
  xvecStep = x_vec/float(numVecSteps)
  yvecStep = y_vec/float(numVecSteps)
  zvecStep = z_vec/float(numVecSteps)
  numImagesPerStep = numImages/float(numVecSteps)
  detector_dead_time = det_lib.detector_get_deadtime()
  exposureTimePerImage =  expTime - detector_dead_time  
  det_lib.detector_set_num_triggers(numImages)
  det_lib.detector_set_period(expTime)
  det_lib.detector_set_exposure_time(exposureTimePerImage)
  det_lib.detector_set_trigger_mode(3)
  det_lib.detector_setImagesPerFile(500)
  daq_lib.detectorArm(sweep_start_angle,imgWidth,numImages,expTime,file_prefix,data_directory_name,file_number_start) #this waits  
  for i in range (0,numVecSteps):
    setPvDesc("vectorStartOmega",sweep_start_angle+(i*scanWidthPerStep))
    setPvDesc("vectorEndOmega",sweep_end_angle+(i*scanWidthPerStep)+scanWidthPerStep)  
    setPvDesc("vectorStartX",x_vec_start+(i*xvecStep)+(xvecStep/2.0))
    setPvDesc("vectorStartY",y_vec_start+(i*yvecStep)+(yvecStep/2.0))  
    setPvDesc("vectorStartZ",z_vec_start+(i*zvecStep)+(zvecStep/2.0))  
    setPvDesc("vectorEndX",x_vec_start+(i*xvecStep)+(xvecStep/2.0))
    setPvDesc("vectorEndY",y_vec_start+(i*yvecStep)+(yvecStep/2.0))  
    setPvDesc("vectorEndZ",z_vec_start+(i*zvecStep)+(zvecStep/2.0))  
    setPvDesc("vectorframeExptime",expTime*1000.0)
    setPvDesc("vectorNumFrames",numImagesPerStep)
    RE(zebraDaqNoDet(sweep_start_angle+(i*scanWidthPerStep),scanWidthPerStep,imgWidth,expTime,file_prefix,data_directory_name,file_number_start))
  if (lastOnSample()):  
    gov_lib.setGovRobot(gov_robot, 'SA')
  det_lib.detector_stop_acquire()
  det_lib.detector_wait()
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)      
  
  setPvDesc("vectorBufferTime",3)      



def dna_execute_collection3(dna_startIgnore,dna_range,dna_number_of_images,dna_exptime,dna_directory,prefix,start_image_number,overlap,dna_run_num,charRequest):
  global collect_and_characterize_success,dna_have_strategy_results,dna_have_index_results,picture_taken
  global dna_strategy_exptime,dna_strategy_start,dna_strategy_range,dna_strategy_end,dna_strat_dist
  global screeningoutputid
  global ednaActiveFlag

  ednaActiveFlag = 1
  dna_start = charRequest["request_obj"]["sweep_start"]
  characterizationParams = charRequest["request_obj"]["characterizationParams"]
  dna_res = float(characterizationParams["aimed_resolution"])
  logger.info("dna_res = " + str(dna_res))
  dna_filename_list = []
  logger.info("number of images " + str(dna_number_of_images) + " overlap = " + str(overlap) + " dna_start " + str(dna_start) + " dna_range " + str(dna_range) + " prefix " + prefix + " start number " + str(start_image_number) + "\n")
  collect_and_characterize_success = 0
  dna_have_strategy_results = 0
  dna_have_index_results = 0  
  if (daq_utils.detector_id == "ADSC-Q315"):
    det_radius = 157.5
  elif (daq_utils.detector_id == "ADSC-Q210"):
    det_radius = 105.0
  elif (daq_utils.detector_id == "PILATUS-6"):
    det_radius = 212.0
  elif daq_utils.detector_id == "EIGER-16" and daq_utils.beamline in ("amx", "nyx"):
    det_radius = 233.1  # Eiger2-9M
  elif daq_utils.detector_id == "EIGER-16":  # FMX
    det_radius = 311.1  # Eiger2-16M
  else: #default Pilatus
    det_radius = 212.0
  theta_radians = 0.0
  wave = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)
  dx = det_radius/(math.tan(2.0*(math.asin(wave/(2.0*dna_res)))-theta_radians))
  logger.info("distance = %s" % dx)
#skinner - could move distance and wave and scan axis here, leave wave alone for now
  logger.info("skinner about to take reference images.")
  dna_image_info = {}
  for i in range(0,int(dna_number_of_images)): # 7/17 no idea what this is
    logger.info("skinner prefix7 = " + prefix[0:7] +  " " + str(start_image_number) + "\n")
  #skinner roi - maybe I can measure and use that for dna_start so that first image is face on.
    colstart = float(dna_start) + (i*(abs(overlap)+float(dna_range)))
    dna_prefix = "ref-"+prefix
    image_number = start_image_number+i
    dna_prefix_long = os.path.join(dna_directory, 'cbf', dna_prefix)
    beamline_lib.mvaDescriptor("omega",float(colstart))
    charRequest["request_obj"]["sweep_start"] = colstart
    if (i == int(dna_number_of_images)-1): # a temporary crap kludge to keep the governor from SA when more images are needed.
      ednaActiveFlag = 0
    imagesAttempted = daq_lib.collect_detector_seq_hw(colstart,dna_range,dna_range,dna_exptime,dna_prefix,dna_directory,image_number,charRequest)
    seqNum = int(det_lib.detector_get_seqnum())
    hdfSampleDataPattern = dna_prefix_long
    filename = hdfSampleDataPattern + "_master.h5"
    dna_image_info[seqNum] = {'uuid': charRequest["uid"], 'seq_num': seqNum}
    
    dna_filename_list.append(filename) #TODO actually contains directory structure for cbf, but filename of h5
    picture_taken = 1
  edna_energy_ev = beamline_lib.motorPosFromDescriptor("energy") * 1000.0
  if (daq_utils.beamline == "fmx"):   # a kludge b/c edna wants a square beam, so where making a 4x4 micron beam be the sqrt(1*1.5) for x and y on fmx
    xbeam_size = .004
    ybeam_size = .004
  else:
    xbeam_size = .0089
    ybeam_size = .0089
  aimed_completeness = characterizationParams['aimed_completeness']
  aimed_multiplicity = characterizationParams['aimed_multiplicity']
  aimed_resolution = characterizationParams['aimed_resolution']
  aimed_ISig = characterizationParams['aimed_ISig']
  timeout_check = 0;
  while(not os.path.exists(dna_filename_list[len(dna_filename_list)-1])): #this waits for edna images
    timeout_check = timeout_check + 1
    time.sleep(1.0)
    if (timeout_check > 10):
      break
  flux = getPvDesc("sampleFlux")    


  node = getBlConfig("spotNode1")          
  cbfList = []
  logger.info(f'filenames for edna: {dna_filename_list}')
  for key, info in dna_image_info.items():
    seq_num = info['seq_num']
    uuid = info['uuid']
    comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}eiger2cbf.sh {uuid} 1 1 0 {seq_num}\""
    CBF_conversion_pattern = dna_filename_list[i][0:len(dna_filename_list[i])-10]+"_"
    cbfList.append(f'{CBF_conversion_pattern}{seq_num}_000001.cbf')
    logger.info(comm_s)
    os.system(comm_s)
  time.sleep(2.0)
  ednaHost = f'{getBlConfig("hostnameBase")}-fastproc'
  comm_s = f"ssh -q {ednaHost} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}edna.sh {dna_directory} {charRequest['uid']} {cbfList[0]} {cbfList[1]} {getPvDesc('transmissionRBV')*100.0} {flux} {xbeam_size} {ybeam_size}\""
  logger.info(comm_s)
  os.system(comm_s)
  logger.info("EDNA DONE\n")
  try:
    fEdnaLogFile = open(dna_directory+"/edna.log", "r" )
  except FileNotFoundError:
    logger.error(f"File {dna_directory}/edna.log not found")
    return 0
  ednaLogLines = fEdnaLogFile.readlines()
  fEdnaLogFile.close()
  collect_and_characterize_success = 0
  for outline in ednaLogLines:
    logger.info(outline)
    if (outline.find("EdnaDir")!= -1):
      (param,dirname) = outline.split('=')
      strXMLFileName = dirname[0:len(dirname)-1]+"/ControlInterfacev1_2/Characterisation/ControlCharacterisationv1_3_dataOutput.xml"
    if (outline.find("characterisation successful!")!= -1):
      collect_and_characterize_success = 1
  if (not collect_and_characterize_success):
    dna_comment =  "Characterize Failure"
    logger.error(dna_comment)
    return 0
  else:
    xsDataCharacterisation = XSDataResultCharacterisation.parseFile( strXMLFileName )
    xsDataIndexingResult = xsDataCharacterisation.getIndexingResult()
    xsDataIndexingSolutionSelected = xsDataIndexingResult.getSelectedSolution()
    xsDataStatisticsIndexing = xsDataIndexingSolutionSelected.getStatistics()
    numSpotsFound  = xsDataStatisticsIndexing.getSpotsTotal().getValue()
    numSpotsUsed  = xsDataStatisticsIndexing.getSpotsUsed().getValue()
    numSpotsRejected = numSpotsFound-numSpotsUsed
    beamShiftX = xsDataStatisticsIndexing.getBeamPositionShiftX().getValue()
    beamShiftY = xsDataStatisticsIndexing.getBeamPositionShiftY().getValue()
    spotDeviationR = xsDataStatisticsIndexing.getSpotDeviationPositional().getValue()
    try:
      spotDeviationTheta = xsDataStatisticsIndexing.getSpotDeviationAngular().getValue()
    except AttributeError:
      spotDeviationTheta = 0.0
    diffractionRings = 0 #for now, don't see this in xml except message string        
    reflections_used = 0 #for now
    reflections_used_in_indexing = 0 #for now
    rejectedReflections = 0 #for now
    xsDataOrientation = xsDataIndexingSolutionSelected.getOrientation()
    xsDataMatrixA = xsDataOrientation.getMatrixA()
    rawOrientationMatrix_a_x = xsDataMatrixA.getM11()
    rawOrientationMatrix_a_y = xsDataMatrixA.getM12()
    rawOrientationMatrix_a_z = xsDataMatrixA.getM13()
    rawOrientationMatrix_b_x = xsDataMatrixA.getM21()
    rawOrientationMatrix_b_y = xsDataMatrixA.getM22()
    rawOrientationMatrix_b_z = xsDataMatrixA.getM23()
    rawOrientationMatrix_c_x = xsDataMatrixA.getM31()
    rawOrientationMatrix_c_y = xsDataMatrixA.getM32()
    rawOrientationMatrix_c_z = xsDataMatrixA.getM33()
    xsDataCrystal = xsDataIndexingSolutionSelected.getCrystal()
    xsDataCell = xsDataCrystal.getCell()
    unitCell_alpha = xsDataCell.getAngle_alpha().getValue()
    unitCell_beta = xsDataCell.getAngle_beta().getValue()
    unitCell_gamma = xsDataCell.getAngle_gamma().getValue()
    unitCell_a = xsDataCell.getLength_a().getValue()
    unitCell_b = xsDataCell.getLength_b().getValue()
    unitCell_c = xsDataCell.getLength_c().getValue()
    mosaicity = xsDataCrystal.getMosaicity().getValue()
    xsSpaceGroup = xsDataCrystal.getSpaceGroup()
    spacegroup_name = xsSpaceGroup.getName().getValue()
    pointGroup = spacegroup_name #for now
    bravaisLattice = pointGroup #for now
    statusDescription = "ok" #for now
    try:
      spacegroup_number = xsSpaceGroup.getITNumber().getValue()
    except AttributeError:
      spacegroup_number = 0
    dna_comment =  "spacegroup = " + str(spacegroup_name) + " mosaicity = " + str(mosaicity) + " cell_a = " + str(unitCell_a) + " cell_b = " + str(unitCell_b) + " cell_c = " + str(unitCell_c) + " cell_alpha = " + str(unitCell_alpha) + " cell_beta = " + str(unitCell_beta) + " cell_gamma = " + str(unitCell_gamma) + " status = " + str(statusDescription)
    logger.info("\n\n skinner " + dna_comment + "\n") 
    xsStrategyResult = xsDataCharacterisation.getStrategyResult()
    resolutionObtained = -999
    if (xsStrategyResult != None):
      dna_have_strategy_results = 1
      xsCollectionPlan = xsStrategyResult.getCollectionPlan()
      xsStrategySummary = xsCollectionPlan[0].getStrategySummary()
      resolutionObtained = xsStrategySummary.getRankingResolution().getValue()
      xsCollectionStrategy = xsCollectionPlan[0].getCollectionStrategy()
      xsSubWedge = xsCollectionStrategy.getSubWedge()
      for i in range (0,len(xsSubWedge)):
        xsExperimentalCondition = xsSubWedge[i].getExperimentalCondition()
        xsGoniostat = xsExperimentalCondition.getGoniostat()
        xsDetector = xsExperimentalCondition.getDetector()
        xsBeam = xsExperimentalCondition.getBeam()
        newTrans_s = "%.2f" % (xsBeam.getTransmission().getValue()/100.0)
        newTrans = float(newTrans_s)
        logger.info("\n new trans = " + str(newTrans) + "\n")
        dna_strategy_start = xsGoniostat.getRotationAxisStart().getValue()
        dna_strategy_start = dna_strategy_start-(dna_strategy_start%.1)
        dna_strategy_range = xsGoniostat.getOscillationWidth().getValue()
        dna_strategy_range = dna_strategy_range-(dna_strategy_range%.1)
        dna_strategy_end = xsGoniostat.getRotationAxisEnd().getValue()
        dna_strategy_end = (dna_strategy_end-(dna_strategy_end%.1)) + dna_strategy_range
        dna_strat_dist = xsDetector.getDistance().getValue()
        dna_strat_dist = dna_strat_dist-(dna_strat_dist%1)
        dna_strategy_exptime = xsBeam.getExposureTime().getValue()
    program = "edna-1.0" # for now
    dna_comment =  "spacegroup = " + str(spacegroup_name) + " mosaicity = " + str(mosaicity) + " resolutionHigh = " + str(resolutionObtained) + " cell_a = " + str(unitCell_a) + " cell_b = " + str(unitCell_b) + " cell_c = " + str(unitCell_c) + " cell_alpha = " + str(unitCell_alpha) + " cell_beta = " + str(unitCell_beta) + " cell_gamma = " + str(unitCell_gamma) + " status = " + str(statusDescription)
    logger.info("\n\n skinner " + dna_comment + "\n") 
    if (dna_have_strategy_results):
      dna_strat_comment = "\ndna Strategy results: Start=" + str(dna_strategy_start) + " End=" + str(dna_strategy_end) + " Width=" + str(dna_strategy_range) + " Time=" + str(dna_strategy_exptime) + " Dist=" + str(dna_strat_dist) + " Transmission= " + str(newTrans)
      characterizationResultObj = {}
      characterizationResultObj = {"strategy":{"start":dna_strategy_start,"end":dna_strategy_end,"width":dna_strategy_range,"exptime":dna_strategy_exptime,"detDist":dna_strat_dist,"transmission":newTrans}}
      db_lib.addResultforRequest("characterizationStrategy",charRequest["uid"], daq_utils.owner,result_obj=characterizationResultObj,proposalID=daq_utils.getProposalID(),beamline=daq_utils.beamline)
      xsStrategyStatistics = xsCollectionPlan[0].getStatistics()
      xsStrategyResolutionBins = xsStrategyStatistics.getResolutionBin()
      now = time.time()
      edna_isig_plot_filename = dirname[0:len(dirname)-1] + "/edna_isig_res.txt"
      isig_plot_file = open(edna_isig_plot_filename,"w")
      for i in range (0,len(xsStrategyResolutionBins)-1):
        i_over_sigma_bin = xsStrategyResolutionBins[i].getIOverSigma().getValue()
        maxResolution_bin = xsStrategyResolutionBins[i].getMaxResolution().getValue()
        logger.info(str(maxResolution_bin) + " " + str(i_over_sigma_bin))
        isig_plot_file.write(str(maxResolution_bin) + " " + str(i_over_sigma_bin)+"\n")
      isig_plot_file.close()
    if (dna_have_strategy_results):
      logger.info(dna_strat_comment)      
  

  return 1

def setTrans(transmission): #where transmission = 0.0-1.0
  if (daq_utils.beamline in ["fmx", "nyx"]):  
    if (getBlConfig("attenType") == "RI"):
      setPvDesc("RIattenEnergySP",beamline_lib.motorPosFromDescriptor("energy"))
      setPvDesc("RI_Atten_SP",transmission)      
      setPvDesc("RI_Atten_SET",1)
      
    else:
      setPvDesc("transmissionSet",transmission)
      setPvDesc("transmissionGo",1)
      
  else:
    setPvDesc("transmissionSet",transmission)
    setPvDesc("transmissionGo",1)
  time.sleep(0.5)
  if daq_utils.beamline != "nyx":  # transmissionDone not available on NYX
    while (not getPvDesc("transmissionDone")):
      time.sleep(0.1)
  
  
  

def setAttens(transmission): #where transmission = 0.0-1.0
  attenValList = []
  attenValList = attenCalc.RIfoils(beamline_lib.get_mono_energy(),transmission)
  for i in range (0,len(attenValList)):
    pvVal = attenValList[i]
    pvKeyName = "Atten%02d-%d" % (i+1,pvVal)    
    setPvDesc(pvKeyName,1)
    logger.info(pvKeyName)

def importSpreadsheet(fname, owner=None):
  if owner is None:
    owner = daq_utils.owner
  parseSheet.importSpreadsheet(fname, owner)


def zebraDaqPrep():

  setPvDesc("zebraReset",1)
  time.sleep(2.0)
  setPvDesc("zebraTTlSel",31)

  setPvDesc("zebraM1SetPosProc",1)
  setPvDesc("zebraM2SetPosProc",1)
  setPvDesc("zebraM3SetPosProc",1)
  setPvDesc("zebraArmTrigSource",1)


def zebraArm():
  setPvDesc("zebraArm",1)
  while(1):
    time.sleep(.1)
    if (getPvDesc("zebraArmOut") == 1):
      break

def zebraWaitOld():
  while(1):
    time.sleep(.1)
    if (getPvDesc("zebraDownloading") == 0):
      break

def zebraWait(timeoutCheck=True):
  timeoutLimit = 20.0
  downloadStart = time.time()  
  while(1):
    now = time.time()
    if (now > (downloadStart+timeoutLimit) and timeoutCheck):
      setPvDesc("zebraReset",1)
      logger.error("timeout in zebra wait!")
      daq_lib.gui_message("Timeout in Trigger Wait! Call Staff!!")
      break
    time.sleep(.1)
    if (getPvDesc("zebraDownloading") == 0):
      break

def zebraWaitDownload(numsteps):

  timeoutLimit = 5.0  
  downloadStart = time.time()  
  while(1):
    now = time.time()
    if (now > (downloadStart+timeoutLimit)):
      setPvDesc("zebraReset",1)
      logger.error("timeout in zebra wait download!")
      break
    time.sleep(.1)
    if (getPvDesc("zebraDownloadCount") == numsteps):
      break
    
def loop_center_mask():
  os.system("cp $CONFIGDIR/bkgrnd.jpg .")
  beamline_lib.mvrDescriptor("omega",90.0)
  daq_utils.take_crystal_picture(filename="findslice_0")
  comm_s = f'{C3D_SEARCH_BASE}find_loopslice.txt'
  logger.debug(f'loop_center_mask: {comm_s}')
  os.system(comm_s)
  os.system("dos2unix res0.txt")
  os.system("echo \"\n\">>res0.txt")    
  c3d_out_file = open("res0.txt","r")
  line = c3d_out_file.readline()
  loop_line = c3d_out_file.readline()
  c3d_out_file.close()    
  loop_tokens = loop_line.split()
  logger.info(loop_tokens)
  loop_found = int(loop_tokens[2])
#crash here if loop not found
  if (loop_found > 0):
    x = float(loop_tokens[9])
    y = float(loop_tokens[10])
    logger.info("x = " + str(x) + " y = " + str(y))
    fovx = daq_utils.lowMagFOVx
    fovy = daq_utils.lowMagFOVy
    daq_lib.center_on_click(320.0,y,fovx,fovy,source="macro")
  beamline_lib.mvrDescriptor("omega",-90.0)    

def getLoopSize():
  os.system("cp $CONFIGDIR/bkgrnd.jpg .")
  daq_utils.take_crystal_picture(filename="findsize_0")
  comm_s = f'{C3D_SEARCH_BASE}find_loopSize.txt'
  logger.debug(f'getLoopSize: {comm_s}')
  os.system(comm_s)
  os.system("dos2unix loopSizeOut0.txt")
  os.system("echo \"\n\">>loopSizeOut0.txt")    
  c3d_out_file = open("loopSizeOut0.txt","r")
  line = c3d_out_file.readline()
  loop_line = c3d_out_file.readline()
  c3d_out_file.close()    
  loop_tokens = loop_line.split()
  logger.info(loop_tokens)
  loop_found = int(loop_tokens[2])
#crash here if loop not found
  if (loop_found > 0):
    v = float(loop_tokens[7])
    h = float(loop_tokens[8])
    logger.info("v = " + str(v) + " h = " + str(h))
    return [v,h]
  return []

  
def clean_up_files(pic_prefix, output_file):
  try:
    os.remove(output_file) 
  except FileNotFoundError:
    pass #if erased or not present, not a problem
  images = glob.glob(f'{pic_prefix}*.jpg')
  for filename in images:
    try:
      os.remove(filename)
    except FileNotFoundError:
      pass #if erased or not present, not a problem
    except Exception as e:
      logger.error(f'Exception while removing file {filename}: {e}')

def loop_center_xrec():
  global face_on

  daq_lib.abort_flag = 0    
  pic_prefix = "findloop"
  output_file = 'xrec_result.txt'
  clean_up_files(pic_prefix, output_file)
  if daq_utils.beamline=='nyx':
    print('post clean')
    xrec_no_zebra(0)
    print('post no zebra')
  else: 
    zebraCamDaq(0,360,40,.4,pic_prefix,getBlConfig("visitDirectory"),0)
  comm_s = f'xrec {os.environ["CONFIGDIR"]}/xrec_360_40Fast.txt {output_file}'
  logger.info(comm_s)
  try:
    os.system(comm_s)
    xrec_out_file = open(output_file,"r")
  except FileNotFoundError:
    logger.error(f'{output_file} not found, halting loop_center_xrec()')
    return 0
  target_angle = 0.0
  radius = 0
  x_centre = 0
  y_centre = 0
  reliability = 0
  for result_line in xrec_out_file.readlines():
    logger.info(result_line)
    tokens = result_line.split()
    tag = tokens[0]
    val = tokens[1]
    if (tag == "TARGET_ANGLE"):
      target_angle = float(val )
    elif (tag == "RADIUS"):
      radius = float(val )
    elif (tag == "Y_CENTRE"):
      y_centre_xrec = float(val )
    elif (tag == "X_CENTRE"):
      x_centre_xrec = float(val )
    elif (tag == "RELIABILITY"):
      reliability = int(val )
    elif (tag == "FACE"):
      face_on = float(tokens[3])
  xrec_out_file.close()
  xrec_check_file = open("Xrec_check.txt","r")  
  check_result =  int(xrec_check_file.read(1))
  logger.info("result = " + str(check_result))
  xrec_check_file.close()
  if (reliability < 70 or check_result == 0): #bail if xrec couldn't align loop
    return 0
  beamline_lib.mvaDescriptor("omega",target_angle)
  x_center = getPvDesc("lowMagCursorX")
  y_center = getPvDesc("lowMagCursorY")
  
  logger.info("center on click " + str(x_center) + " " + str(y_center-radius))
  logger.info("center on click " + str((x_center*2) - y_centre_xrec) + " " + str(x_centre_xrec))
  fovx = daq_utils.lowMagFOVx
  fovy = daq_utils.lowMagFOVy
  
  daq_lib.center_on_click(x_center,y_center-radius,fovx,fovy,source="macro")
  daq_lib.center_on_click((x_center*2) - y_centre_xrec,x_centre_xrec,fovx,fovy,source="macro")
  beamline_lib.mvaDescriptor("omega",face_on)
  #now try to get the loopshape starting from here
  return 1

def xrec_no_zebra(angle_start):
  print(f'xrec_no_zebra{angle_start}')
  beamline_lib.mvaDescriptor("omega", angle_start)
  for omega_target in range (angle_start, angle_start+360, 40):
    beamline_lib.mvaDescriptor("omega", omega_target)
    logger.info(f'taking image at {omega_target}')
    timeout = 5
    # change image mode to single(0)
    setPvDesc("lowMagImMode",0)
    # start camera
    setPvDesc("lowMagAcquire",1)
    try:
      with urllib.request.urlopen(daq_utils.lowMagCamURL, timeout=timeout) as response:
        logger.info("xnz: read")
        image_data = response.read()
        logger.info("xnz: read")
      with open(getBlConfig("visitDirectory")+"findloop_"+str(omega_target//40)+".jpg", "wb") as filename:
        logger.info("xnz: write file")
        filename.write(image_data)
        logger.info("xnz: write file")
    except urllib.error.URLError as e:
      print("Error:", e)
    logger.info("xnz: sleep")
    time.sleep(1)
    # change image mode to continuous(2)
    setPvDesc("lowMagImMode",2)
    # start camera
    setPvDesc("lowMagAcquire",1)
 

def zebraCamDaq(angle_start,scanWidth,imgWidth,exposurePeriodPerImage,filePrefix,data_directory_name,file_number_start,scanEncoder=3): #scan encoder 0=x, 1=y,2=z,3=omega
#careful - there's total exposure time, exposure period, exposure time

#imgWidth will be something like 40 for xtalCenter
  vectorSync()
  setPvDesc("vectorExpose",0)  
  angle_end = angle_start+scanWidth
  numImages = int(round(scanWidth/imgWidth))
  setPvDesc("vectorStartOmega",angle_start)
  setPvDesc("vectorEndOmega",angle_end)
  setPvDesc("vectorNumFrames",numImages)    
  setPvDesc("vectorframeExptime",exposurePeriodPerImage*1000.0)
  setPvDesc("vectorHold",0)
  zebraDaqPrep()
  setPvDesc("zebraEncoder",scanEncoder)
  setPvDesc("zebraDirection",0)  #direction 0 = positive
  setPvDesc("zebraGateSelect",0)
  setPvDesc("zebraGateStart",angle_start) #this will change for motors other than omega
  setPvDesc("zebraGateWidth",imgWidth/2) #why divide by 2 here and not elsewhere?
  setPvDesc("zebraGateStep",imgWidth)
  setPvDesc("zebraGateNumGates",numImages)  

  setPvDesc("lowMagAcquire",0,wait=False)
  time.sleep(1.0) #this sleep definitely needed
  setPvDesc("lowMagTrigMode",1)
  setPvDesc("lowMagJpegNumImages",numImages)
  setPvDesc("lowMagJpegFilePath",data_directory_name)
  setPvDesc("lowMagJpegFileName",filePrefix)
  setPvDesc("lowMagJpegFileNumber",1)
  setPvDesc("lowMagJpegCapture",1,wait=False)
  setPvDesc("lowMagAcquire",1,wait=False)
  vectorWaitForGo(source="zebraCamDaq")
  vectorWait()
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)      
  
  setPvDesc("lowMagTrigMode",0)

def gatherStandardVectorParams():
    logger.info("gathering vector parameters")
    current_x = beamline_lib.motorPosFromDescriptor("sampleX")
    current_y = beamline_lib.motorPosFromDescriptor("sampleY")
    current_z = beamline_lib.motorPosFromDescriptor("sampleZ")
    vectorParams={}
    vectorParams["vecStart"]={}
    vectorParams["vecEnd"]={}
    vectorParams["vecStart"]["x"]=current_x
    vectorParams["vecStart"]["y"]=current_y
    vectorParams["vecStart"]["z"]=current_z
    vectorParams["vecEnd"]["x"]=current_x
    vectorParams["vecEnd"]["y"]=current_y
    vectorParams["vecEnd"]["z"]=current_z
 
    x_beam = getPvDesc("beamCenterX")
    y_beam = getPvDesc("beamCenterY")
    wavelength = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)
    det_distance_m = beamline_lib.motorPosFromDescriptor("detectorDist") / 1000
    if daq_utils.beamline in ("nyx", "fmx"):
        transmission = getPvDesc("RI_Atten_SP")
    else:
        transmission = getPvDesc("transmissionRBV")
    vectorParams["x_beam"]=x_beam
    vectorParams["y_beam"]=y_beam
    vectorParams["wavelength"]=wavelength
    vectorParams["det_distance_m"]=det_distance_m
    vectorParams["transmission"]=transmission
    return vectorParams

def standard_zebra_plan(flyer,angle_start,num_images,scanWidth,imgWidth,exposurePeriodPerImage,filePrefix,data_directory_name,file_number_start, vector_params, data_path):
    final_plan = finalize_wrapper(zebraDaqBluesky(flyer, angle_start, num_images, scanWidth, imgWidth, exposurePeriodPerImage, filePrefix, data_directory_name, file_number_start, vector_params, data_path), bps.mv(flyer.detector.cam.acquire, 0))
    yield from final_plan

def standard_plan_wrapped(currentRequest):
    yield from finalize_wrapper(standardDaq(currentRequest), clean_up_collection())

def vector_plan_wrapped(currentRequest):
    yield from finalize_wrapper(vectorDaq(currentRequest), clean_up_collection())

def raster_plan_wrapped(rasterReqID):
    yield from finalize_wrapper(rasterDaq(rasterReqID), clean_up_collection())
    #time.sleep(15)
    #rasterRequest = db_lib.getRequestByID(rasterReqID)
    #rasterResult = generateGridMap(rasterRequest)
    #rasterRequest["request_obj"]["rasterDef"]["status"] = (
    #    RasterStatus.READY_FOR_SNAPSHOT.value
    #)
    #db_lib.updateRequest(rasterRequest)
    #db_lib.updatePriority(rasterReqID,-1)
    #daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])



def standardDaq(currentRequest):
    # collect all parameters
    # perform preparatory movements
    # arm the detector
    # perform governor and phase transitions
    # update flyer parameters
    # fly
    x_beam = getPvDesc("beamCenterX")
    y_beam = getPvDesc("beamCenterY")
    wavelength = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)
    det_distance_m = beamline_lib.motorPosFromDescriptor("detectorDist") / 1000
    reqObj = currentRequest["request_obj"]
    file_prefix = str(reqObj["file_prefix"])
    data_directory_name = str(reqObj["directory"])
    file_number_start = reqObj["file_number_start"]
    sweep_start_angle = reqObj["sweep_start"]
    sweep_end_angle = reqObj["sweep_end"]
    file_prefix = str(reqObj["file_prefix"])
    data_directory_name = str(reqObj["directory"])
    file_number_start = reqObj["file_number_start"]
    img_width = reqObj["img_width"]
    exposure_per_image = reqObj["exposure_time"]
    total_num_images = int(round(((sweep_end_angle - sweep_start_angle) / img_width), 4))
    total_exposure_time = exposure_per_image * total_num_images
    scan_range = float(total_num_images)*img_width
    angle_start = sweep_start_angle
    wavelength = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)

    yield from bps.mv(beamstop.distance_preset, 20.0)
    md2.save_center()
    if det_move_done.get() != 1:
        def det_move_done_callback(value, old_value, **kwargs):
            return (old_value!=1 and value ==1)
        det_move_status = SubscriptionStatus(det_move_done, det_move_done_callback, run=False)
        det_move_status.wait()
    if flyer.detector.cam.armed.get() == 1:
        daq_lib.gui_message('Detector is in armed state from previous collection! Stopping detector, but the user '
                            'should check the most recent collection to determine if it was successful. Cancelling'
                            'this collection, retry when ready.')
        logger.warning("Detector was in the armed state prior to this attempted collection.")
        return 0
    start_time = time.time()
    logger.info(f"Configuring detector for standard collection with file_prefix {file_prefix} and data_directory_name {data_directory_name}")
    flyer.configure_detector(file_prefix, data_directory_name)
    logger.info(f"Arming detector for standard collection with angle_start {angle_start}, img_width {img_width}, total_num_images {total_num_images}, exposure_per_image {exposure_per_image}, file_prefix {file_prefix}, data_directory_name {data_directory_name}, file_number_start {file_number_start}, x_beam {x_beam}, y_beam {y_beam}, wavelength {wavelength}, det_distance_m {det_distance_m}")
    flyer.detector_arm(angle_start, img_width, total_num_images, exposure_per_image, 
                     file_prefix, data_directory_name, file_number_start, x_beam, y_beam, 
                     wavelength, det_distance_m)
    def armed_callback(value, old_value, **kwargs):
        return (old_value == 0 and value == 1)
    arm_status = SubscriptionStatus(flyer.detector.cam.armed, armed_callback, run=False)
    flyer.detector.cam.acquire.put(1)
    govStatus = gov_lib.setGovRobot(gov_robot, "DA")
    try:
        arm_status.wait(timeout=20)
        govStatus.wait(timeout=20)
    except WaitTimeoutError:
        logger.error("Timeout during arming or governor move, aborting collection")
        return
    logger.info(f"Governor move to DA and synchronous arming took {time.time()-start_time} seconds.")
    if govStatus.exception():
        logger.error(f"Problem during start-of-collection governor move, aborting! exception: {govStatus.exception()}")
        return
    flyer.detector.stage()
    start_time = time.time()
    yield from bps.mv(md2.phase, 2) # TODO: Enum for MD2 phases and states
    try:
        md2.ready_status().wait(timeout=10)
    except WaitTimeoutError:
        logger.error("timeout: md2 failed to enter ready state, aborting collection")
        return
    logger.info(f"MD2 phase transition to 2-DataCollection took {time.time()-start_time} seconds.")
    flyer.update_parameters(total_num_images, angle_start, scan_range, total_exposure_time)
    logger.info(f"flyer handoff")
    yield from bp.fly([flyer])
    logger.info(f"fly complete")

def vectorDaq(currentRequest):
    # collect all parameters
    # perform preparatory movements
    # arm the detector
    # perform governor and phase transitions
    # update flyer parameters
    # fly
    x_beam = getPvDesc("beamCenterX")
    y_beam = getPvDesc("beamCenterY")
    wavelength = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)
    det_distance_m = beamline_lib.motorPosFromDescriptor("detectorDist") / 1000
    reqObj = currentRequest["request_obj"]
    file_prefix = str(reqObj["file_prefix"])
    data_directory_name = str(reqObj["directory"])
    file_number_start = reqObj["file_number_start"]
    sweep_start_angle = reqObj["sweep_start"]
    sweep_end_angle = reqObj["sweep_end"]
    file_prefix = str(reqObj["file_prefix"])
    data_directory_name = str(reqObj["directory"])
    file_number_start = reqObj["file_number_start"]
    img_width = reqObj["img_width"]
    exposure_per_image = reqObj["exposure_time"]
    total_num_images = int(round(((sweep_end_angle - sweep_start_angle) / img_width), 4))
    total_exposure_time = reqObj["exposure_time"] * total_num_images
    scan_range = float(total_num_images)*img_width
    angle_start = sweep_start_angle
    wavelength = daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6)

    vector_params = reqObj["vectorParams"]
    start_y=vector_params["vecStart"]["y"]
    start_z=vector_params["vecStart"]["z"]
    start_cx=vector_params["vecStart"]["finex"]
    start_cy=vector_params["vecStart"]["finey"]
    stop_cx=vector_params["vecEnd"]["finex"]
    stop_cy=vector_params["vecEnd"]["finey"]
    stop_y=vector_params["vecEnd"]["y"]
    stop_z=vector_params["vecEnd"]["z"]
    if det_move_done.get() != 1:
        def det_move_done_callback(value, old_value, **kwargs):
            return (old_value!=1 and value ==1)
        det_move_status = SubscriptionStatus(det_move_done, det_move_done_callback, run=False)
        det_move_status.wait()

    md2.save_center()
    yield from bps.mv(beamstop.distance_preset, 20.0)

    if vector_flyer.detector.cam.armed.get() == 1:
        daq_lib.gui_message('Detector is in armed state from previous collection! Stopping detector, but the user '
                            'should check the most recent collection to determine if it was successful. Cancelling'
                            'this collection, retry when ready.')
        logger.warning("Detector was in the armed state prior to this attempted collection.")
        return 0
    start_time = time.time()
    vector_flyer.configure_detector(file_prefix, data_directory_name)
    vector_flyer.detector_arm(angle_start, img_width, total_num_images, exposure_per_image, 
                     file_prefix, data_directory_name, file_number_start, x_beam, y_beam, 
                     wavelength, det_distance_m)
    def armed_callback(value, old_value, **kwargs):
        return (old_value == 0 and value == 1)
    arm_status = SubscriptionStatus(vector_flyer.detector.cam.armed, armed_callback, run=False)
    vector_flyer.detector.cam.acquire.put(1)
    govStatus = gov_lib.setGovRobot(gov_robot, "DA")
    try:
        arm_status.wait(timeout=10)
        govStatus.wait(timeout=20)
    except WaitTimeoutError:
        logger.error("Timeout reached during arming or governor move, aborting")
        return
    logger.info(f"Governor move to DA and synchronous arming took {time.time()-start_time} seconds.")
    if govStatus.exception():
        logger.error(f"Problem during start-of-collection governor move, aborting! exception: {govStatus.exception()}")
        return
    flyer.detector.stage()
    start_time = time.time()
    yield from bps.mv(md2.phase, 2) # TODO: Enum for MD2 phases and states
    try:
        md2.ready_status().wait(timeout=10)
    except WaitTimeoutError:
        logger.error("timeout: md2 failed to reach ready state, aborting")
        return
    logger.info(f"MD2 phase transition to 2-DataCollection took {time.time()-start_time} seconds.")
    vector_flyer.update_parameters(angle_start, scan_range, total_exposure_time, start_y, start_z, stop_y, stop_z, start_cx, start_cy, stop_cx, stop_cy)
    yield from bp.fly([vector_flyer])

def rasterDaq(rasterReqID):
    global rasterRowResultsList,processedRasterRowCount
    data_directory_name, file_prefix, file_number_start, dataFilePrefix, exposure_per_image, img_width_per_cell, wavelength, detDist, rasterDef, stepsize, start_omega, start_x, start_y, start_z, omegaRad, number_of_lines, numsteps, total_num_images, rows = params_from_raster_req_id(rasterReqID)
    rasterRowResultsList = [{} for i in range(0,number_of_lines)]
    processedRasterRowCount = 0
    rasterRequest = db_lib.getRequestByID(rasterReqID)
    reqObj = rasterRequest["request_obj"]
    parentReqID = reqObj["parentReqID"]
    
    xbeam = getPvDesc("beamCenterX")
    ybeam = getPvDesc("beamCenterY")
    if (parentReqID != -1):
      parentRequest = db_lib.getRequestByID(parentReqID)
      parentReqObj = parentRequest["request_obj"]
      detDist = parentReqObj["detDist"]

    rasterFilePrefix = dataFilePrefix # + "_Raster"

    logger.info(f"prepping raster with: {rasterFilePrefix}, {data_directory_name}, {file_number_start}, {dataFilePrefix}, {exposure_per_image}, {img_width_per_cell}, {wavelength}, {detDist}, {rasterDef}, {stepsize}, {start_omega}, {start_x}, {start_y}, {start_z}, {omegaRad}, {number_of_lines}, {numsteps}, {total_num_images}, {rows}")
    #logger.info(f"req_obj: {reqObj}")
    i = 0
    xMotAbsoluteMove, xEnd, yMotAbsoluteMove, yEnd, zMotAbsoluteMove, zEnd = raster_positions(rows[i], stepsize, (start_omega*0), start_x, start_y, start_z, i)
    stepsize /= 1000 # MD2 wants mm
    logger.info(f"move calculations:  {xMotAbsoluteMove}, {xEnd}, {yMotAbsoluteMove}, {yEnd}, {zMotAbsoluteMove}, {zEnd}")
    line_range = stepsize * numsteps
    total_uturn_range = stepsize * number_of_lines
    start_y = start_y - (xEnd / 1000)
    start_z = start_z - (yMotAbsoluteMove / 1000)
    #start_z = start_z - (xEnd / 1000)
    start_cx = md2.cx.val()# + (xEnd/1000)
    start_cy = md2.cy.val()
    frames_per_line = numsteps
    total_exposure_time = exposure_per_image * frames_per_line
    invert_direction = False
    use_centring_table = True
    use_fast_mesh_scans = True
    omega_range = 0
    logger.info(f"TASK INFO: {md2.task_info.get()}")
    logger.info(f"TASK INFO[6]: {md2.task_info.get()[6]=='1'}")
    logger.info(f"TASK OUTPUT: {md2.task_output}")
    logger.info(f"omega_range = {omegaRad}")
    logger.info(f"line_range = {line_range}")
    logger.info(f"total_uturn_range = {total_uturn_range}")
    logger.info(f"start_omega = {start_omega}")
    logger.info(f"start_y = {start_y}")
    logger.info(f"current yzcxcy: {md2.y.get()}, {md2.z.get()}, {md2.cx.get()}, {md2.cy.get()}")
    logger.info(f"start_z = {start_z}")
    logger.info(f"start_cx = {start_cx}")
    logger.info(f"start_cy = {start_cy}")
    logger.info(f"number_of_lines = {number_of_lines}")
    logger.info(f"frames_per_line = {frames_per_line}")
    logger.info(f"total_exposure_time = {total_exposure_time}")
    logger.info(f"invert_direction = {invert_direction}")
    logger.info(f"use_centring_table = {use_centring_table}")
    logger.info(f"use_fast_mesh_scans = {use_fast_mesh_scans}")
    if det_move_done.get() != 1:
        def det_move_done_callback(value, old_value, **kwargs):
            return (old_value!=1 and value ==1)
        det_move_status = SubscriptionStatus(det_move_done, det_move_done_callback, run=False)
        det_move_status.wait()

    md2.save_center()
    yield from bps.mv(beamstop.distance_preset, 20.0)

    if raster_flyer.detector.cam.armed.get() == 1:
        daq_lib.gui_message('Detector is in armed state from previous collection! Stopping detector, but the user '
                            'should check the most recent collection to determine if it was successful. Cancelling'
                            'this collection, retry when ready.')
        logger.warning("Detector was in the armed state prior to this attempted collection.")
        return 0
    start_time = time.time()
    raster_flyer.configure_detector(rasterFilePrefix, data_directory_name)
    raster_flyer.detector_arm(start_omega, img_width_per_cell, total_num_images, exposure_per_image, 
                     file_prefix, data_directory_name, file_number_start, xbeam, ybeam, 
                     wavelength, detDist)
    def armed_callback(value, old_value, **kwargs):
        return (old_value == 0 and value == 1)
    arm_status = SubscriptionStatus(raster_flyer.detector.cam.armed, armed_callback, run=False)
    raster_flyer.detector.cam.acquire.put(1)
    govStatus = gov_lib.setGovRobot(gov_robot, "DA")
    try:
        arm_status.wait(timeout=10)
        govStatus.wait(timeout=20)
    except WaitTimeoutError:
        logger.error("arming or governor status failure")
        return
    logger.info(f"Governor move to DA and synchronous arming took {time.time()-start_time} seconds.")
    if govStatus.exception():
        logger.error(f"Problem during start-of-collection governor move, aborting! exception: {govStatus.exception()}")
        return
    flyer.detector.stage()
    start_time = time.time()
    yield from bps.mv(md2.phase, 2) # TODO: Enum for MD2 phases and states
    try:
        md2.ready_status().wait(timeout=10)
    except:
        logger.error("md2 failed to reach ready state, aborting collection")
        return
    logger.info(f"MD2 phase transition to 2-DataCollection took {time.time()-start_time} seconds.")
    raster_flyer.update_parameters(omega_range, line_range, total_uturn_range, start_omega, start_y, start_z, start_cx, start_cy, number_of_lines, frames_per_line, total_exposure_time, invert_direction, use_centring_table, use_fast_mesh_scans)
    yield from bp.fly([raster_flyer])
    spotFindThreadList = []
    row_index = 1
    logger.info(f"raster prefix {rasterFilePrefix}")
    rasterFilePrefix = rasterFilePrefix.split("/")[-1]
    logger.info(f"raster prefix {rasterFilePrefix}")
    for i in range(0, number_of_lines):
        time.sleep(1.0)
        row_index = i
        logger.info(f'spot finding for row {i}')
        seqNum = raster_flyer.detector.cam.sequence_id.get()
        spotFindThread = Thread(target=runDozorThread,args=(data_directory_name, #TODO this can't move outside of the thread checking block
                                                              rasterFilePrefix,
                                                              row_index,
                                                              numsteps,
                                                              seqNum,
                                                              reqObj,
                                                              rasterReqID))
        spotFindThread.start()
        spotFindThreadList.append(spotFindThread)
    [thread.join(timeout=120) for thread in spotFindThreadList]
    logger.info(str(processedRasterRowCount) + "/" + str(number_of_lines))
    rasterResult = generateGridMap(rasterRequest)
    rasterRequestID = rasterRequest["uid"]
    rasterRequest["request_obj"]["rasterDef"]["status"] = (
        RasterStatus.READY_FOR_SNAPSHOT.value
    )
    db_lib.updateRequest(rasterRequest)
    db_lib.updatePriority(rasterRequestID,-1)
    if (rasterRequest["request_obj"]["rasterDef"]["numCells"]
          > getBlConfig(RASTER_NUM_CELLS_DELAY_THRESHOLD)):
        #larger rasters can delay GUI scene update
        time.sleep(getBlConfig(RASTER_LONG_SNAPSHOT_DELAY))
    else:
        time.sleep(getBlConfig(RASTER_SHORT_SNAPSHOT_DELAY))
    daq_lib.set_field("xrecRasterFlag",rasterRequest["uid"])



  

def clean_up_collection():
    # this is a plan that should will always be run after a collection is complete
    start_time = time.time()
    yield from bps.mv(flyer.detector.cam.acquire, 0)
    flyer.detector.unstage()
    if (lastOnSample()):
        gov_status = gov_lib.setGovRobot(gov_robot, 'SA', wait=False)
        gov_status.wait(timeout=30)
    yield from bps.mv(md2.phase, 0)
    md2.ready_status().wait(timeout= 20)
    # trigger processing here
    logger.info(f"clean_up took {time.time()-start_time} seconds.")

def zebraDaqBluesky(flyer, angle_start, num_images, scanWidth, imgWidth, exposurePeriodPerImage, filePrefix, data_directory_name, file_number_start, vector_params, data_path, scanEncoder=3, changeState=True):

    logger.info("in Zebra Daq Bluesky #1")
    logger.info(f" with vector: {vector_params}")

    x_vec_start=vector_params["vecStart"]["x"]
    y_vec_start=vector_params["vecStart"]["y"]
    z_vec_start=vector_params["vecStart"]["z"]
    x_vec_end=vector_params["vecEnd"]["x"]
    y_vec_end=vector_params["vecEnd"]["y"]
    z_vec_end=vector_params["vecEnd"]["z"]
    if beamline == "nyx":
      x_vec_start *= 1000
      y_vec_start *= 1000
      z_vec_start *= 1000
      x_vec_end *= 1000
      y_vec_end *= 1000
      z_vec_end *= 1000

    try: 
      detectorDeadTime=flyer.detector.cam.dead_time.get()
    except AttributeError as e:
      logger.error("Vector Aborted: failed to get dead_time from detector.cam object")
      return 

    if flyer.detector.cam.armed.get() == 1:
        daq_lib.gui_message('Detector is in armed state from previous collection! Stopping detector, but the user '
                            'should check the most recent collection to determine if it was successful. Cancelling'
                            'this collection, retry when ready.')
        logger.warning("Detector was in the armed state prior to this attempted collection.")
        return 0

    required_parameters = {'angle_start':angle_start, 'scan_width':scanWidth, 'img_width':imgWidth,
                           'num_images':num_images, 'exposure_period_per_image':exposurePeriodPerImage,
                           'x_start_um':x_vec_start, 'y_start_um':y_vec_start, 'z_start_um':z_vec_start,
                           'x_end_um':x_vec_end, 'y_end_um':y_vec_end, 'z_end_um':z_vec_end, 'file_prefix':filePrefix,
                           'data_directory_name':data_directory_name, 'file_number_start':file_number_start,
                           'x_beam':vector_params["x_beam"], 'y_beam':vector_params["y_beam"],
                           'wavelength':vector_params["wavelength"], 'det_distance_m':vector_params["det_distance_m"],
                           'detector_dead_time':detectorDeadTime, 'scan_encoder':scanEncoder,
                           'change_state':changeState, 'transmission':vector_params["transmission"],
                           'data_path':data_path}
    start_time = time.time()
    arm_status = flyer.detector_arm(**required_parameters)
    govStatus = gov_lib.setGovRobot(gov_robot, "DA")
    arm_status.wait()
    logger.info(f"Governor move to DA and synchronous arming took {time.time()-start_time} seconds.")
    if govStatus.exception():
      logger.error(f"Problem during start-of-collection governor move, aborting! exception: {govStatus.exception()}")
      return

    flyer.update_parameters(**required_parameters)

    yield from bp.fly([flyer])

    logger.info("vector Done")
    if lastOnSample() and changeState:
        govStatus = gov_lib.setGovRobot(gov_robot, 'SA', wait=False)
        if govStatus.exception():
          logger.error(f"Problem during end-of-collection governor move, aborting! exception: {govStatus.exception()}")
          return

    logger.info("stop det acquire")
    logger.info("zebraDaq Done")

def zebraDaqRasterBluesky(flyer, angle_start, num_images, scanWidth, imgWidth, exposurePeriodPerImage, filePrefix, data_directory_name, file_number_start, row_index, vector, scanEncoder=3, changeState=True):  # TODO should be raster flyer

    logger.info("in Zebra Daq Raster Bluesky #1")
    logger.info(f" with vector: {vector}")

    x_vec_start=vector["x"][0]
    y_vec_start=vector["y"][0]
    z_vec_start=vector["z"][0]
    x_vec_end=vector["x"][1]
    y_vec_end=vector["y"][1]
    z_vec_end=vector["z"][1]
    if beamline == "nyx":
      x_vec_start *= 1000
      y_vec_start *= 1000
      z_vec_start *= 1000
      x_vec_end *= 1000
      y_vec_end *= 1000
      z_vec_end *= 1000

    try:
      detectorDeadTime=flyer.detector.cam.dead_time.get()
    except AttributeError as e:
      logger.error("Vector Aborted: failed to get dead_time from detector.cam object")
      return

    raster_flyer.update_parameters(angle_start=angle_start, scan_width=scanWidth, img_width=imgWidth, num_images=num_images, exposure_period_per_image=exposurePeriodPerImage, \
                   num_images_per_file=num_images, \
                   x_start_um=x_vec_start, y_start_um=y_vec_start, z_start_um=z_vec_start, \
                   x_end_um=x_vec_end, y_end_um=y_vec_end, z_end_um=z_vec_end, \
                   file_prefix=filePrefix, data_directory_name=data_directory_name,\
                   detector_dead_time=detectorDeadTime, scan_encoder=scanEncoder, change_state=changeState,\
                   row_index=row_index, transmission=1, protocol="raster")
    yield from bp.fly([raster_flyer])

    logger.info("vector Done")
    logger.info("zebraDaqRasterBluesky Done")

def zebraDaq(vector_program,angle_start,scanWidth,imgWidth,exposurePeriodPerImage,filePrefix,data_directory_name,file_number_start,scanEncoder=3,changeState=True): #scan encoder 0=x, 1=y,2=z,3=omega
#careful - there's total exposure time, exposure period, exposure time

  logger.info("in Zebra Daq #1 " + str(time.time()))      
  yield from bps.mv(eiger.fw_num_images_per_file, IMAGES_PER_FILE)
  gov_lib.setGovRobot(gov_robot, "DA")
  yield from bps.mv(vector_program.expose, 1)

  if (imgWidth == 0):
    angle_end = angle_start
    numImages = scanWidth
  else:
    angle_end = angle_start+scanWidth    
    numImages = int(round(scanWidth/imgWidth))
  total_exposure_time = exposurePeriodPerImage*numImages
  if (total_exposure_time < 1.0):
    yield from bps.mv(vector_program.buffer_time, 1000)
  else:
    yield from bps.mv(vector_program.buffer_time, 3)
    pass
  logger.info("in Zebra Daq #2 " + str(time.time()))        
  yield from setup_eiger_exposure(eiger, exposurePeriodPerImage, exposurePeriodPerImage)
  detector_dead_time = eiger.dead_time.get()
  exposureTimePerImage =  exposurePeriodPerImage - detector_dead_time  
  yield from setup_vector_program(vector_program=vector_program, num_images=numImages,
                                  angle_start=angle_start,
                                  angle_end=angle_end,
                                  exposure_period_per_image=exposurePeriodPerImage)
  logger.info("zebra_daq_prep " + str(time.time()))        
  yield from zebra_daq_prep(zebra)
  logger.info("done zebra_daq_prep " + str(time.time()))        
  time.sleep(1.0)


  PW=(exposurePeriodPerImage-detector_dead_time)*1000.0
  PS=(exposurePeriodPerImage)*1000.0
  GW=scanWidth-(1.0-(PW/PS))*(imgWidth/2.0)
  yield from setup_zebra_vector_scan(zebra=zebra, angle_start=angle_start, gate_width=GW, scan_width=scanWidth, pulse_width=PW, pulse_step=PS,
                       exposure_period_per_image=exposurePeriodPerImage, num_images=numImages, is_still=imgWidth==0)
  logger.info("zebraDaq - setting and arming detector " + str(time.time()))      

  yield from setup_eiger_triggers(eiger, EXTERNAL_TRIGGER, 1, exposureTimePerImage)
  logger.info("detector arm " + str(time.time()))        
  yield from setup_eiger_arming(eiger, angle_start,imgWidth,numImages,exposurePeriodPerImage,filePrefix,data_directory_name,file_number_start) #this waits
  try:
    logger.info("detector done arm, timed in zebraDaq " + str(time.time()))          

    startArm = time.time()
    gov_status = gov_lib.setGovRobot(gov_robot, 'DA')
    if not gov_status.success:
      return
    endArm = time.time()
    armTime = endArm-startArm
    logger.info("gov wait time = " + str(armTime) +"\n")
  
    logger.info("vector Go " + str(time.time()))        
    yield from bps.mv(vector_program.go, 1)
    try:
      vectorActiveWait()  
    except TimeoutError:
      logger.info("caught TimeoutError in zebraDaq, proceeded with collection")
    vectorWait()
    zebraWait()
    logger.info("vector Done " + str(time.time()))          
    if (daq_utils.beamline == "amxz"):  
      setPvDesc("zebraReset",1)      
  
    if (lastOnSample() and changeState):
      gov_lib.setGovRobot(gov_robot, 'SA', wait=False)
  except Exception as e:
    logger.error(f'Exception while collecting data: {e}')
    return
  finally:
    logger.info("stop det acquire")
    yield from setup_eiger_stop_acquire_and_wait(eiger)
  
  yield from bps.mv(vector_program.buffer_time, 3)
  try:
    logger.info("detector done arm, timed in zebraDaq " + str(time.time()))          
    startArm = time.time()
    if not (daq_lib.setGovRobot('DA')):
      raise Exception('not in DA state, stopping collection')
    endArm = time.time()
    armTime = endArm-startArm
    logger.info("gov wait time = " + str(armTime) +"\n")
  
    logger.info("vector Go " + str(time.time()))        
    try:
      vectorWaitForGo(source="zebraDaq",timeout_trials=1)
    except TimeoutError:
       logger.info("caught TimeoutError in zebraDaq, proceeded with collection")
    vectorWait()
    zebraWait()
    logger.info("vector Done " + str(time.time()))          
    if (daq_utils.beamline == "amxz"):  
      setPvDesc("zebraReset",1)      
  
    if (lastOnSample() and changeState):
      daq_lib.setGovRobotSA_nowait()    
    logger.info("stop det acquire")
  except Exception as e:
    logger.error(f'Exception while collecting data: {e}')
    return
  finally:
    det_lib.detector_stop_acquire()
  det_lib.detector_wait()
  setPvDesc("vectorBufferTime",3)
  logger.info("zebraDaq Done " + str(time.time()))            


def zebraDaqNoDet(angle_start,scanWidth,imgWidth,exposurePeriodPerImage,filePrefix,data_directory_name,file_number_start,scanEncoder=3): #scan encoder 0=x, 1=y,2=z,3=omega
#careful - there's total exposure time, exposure period, exposure time


  setPvDesc("vectorExpose",1)
  if (imgWidth == 0):
    angle_end = angle_start
    numImages = scanWidth
  else:
    angle_end = angle_start+scanWidth    
    numImages = int(round(scanWidth/imgWidth))
  total_exposure_time = exposurePeriodPerImage*numImages
  if (total_exposure_time < 1.0):
    setPvDesc("vectorBufferTime",1000)
  else:
    setPvDesc("vectorBufferTime",3)    
  detector_dead_time = det_lib.detector_get_deadtime()
  exposureTimePerImage =  exposurePeriodPerImage - detector_dead_time  
  setPvDesc("vectorNumFrames",numImages)  
  setPvDesc("vectorStartOmega",angle_start)
  setPvDesc("vectorEndOmega",angle_end)
  setPvDesc("vectorframeExptime",exposurePeriodPerImage*1000.0)
  setPvDesc("vectorHold",0)
  yield from zebra_daq_prep(zebra)
  setPvDesc("zebraEncoder",scanEncoder)
  time.sleep(1.0)
  setPvDesc("zebraDirection",0)  #direction 0 = positive
  setPvDesc("zebraGateSelect",0)
  setPvDesc("zebraGateStart",angle_start) #this will change for motors other than omega
  if (imgWidth != 0):    
    setPvDesc("zebraGateWidth",scanWidth)
    setPvDesc("zebraGateStep",scanWidth+.01)
  setPvDesc("zebraGateNumGates",1)
  setPvDesc("zebraPulseTriggerSource",1)
  setPvDesc("zebraPulseStart",0)
  setPvDesc("zebraPulseWidth",(exposurePeriodPerImage-detector_dead_time)*1000.0)      
  setPvDesc("zebraPulseStep",(exposurePeriodPerImage)*1000.0)
  setPvDesc("zebraPulseDelay",((exposurePeriodPerImage)/2.0)*1000.0)
  setPvDesc("zebraPulseMax",numImages)
  setPvDesc("vectorGo",1)
  vectorActiveWait()  
  vectorWait()
  zebraWait()
  if (daq_utils.beamline == "amxz"):  
    setPvDesc("zebraReset",1)      
  
  setPvDesc("vectorBufferTime",3)      
  

def setAttenBCU():
  """setAttenBCU() : set attenuators to BCU (fmx only)"""
  setBlConfig("attenType","BCU")
  setPvDesc("RI_Atten_SP",1.0)      
  setPvDesc("RI_Atten_SET",1)
  daq_lib.gui_message("Attenuators set to BCU. Restart LSDC GUI!")  
  

def setAttenRI():
  """setAttenRI() : set attenuators to RI (fmx only)"""
  setBlConfig("attenType","RI")
  setPvDesc("transmissionSet",1.0)
  setPvDesc("transmissionGo",1)
  daq_lib.gui_message("Attenuators set to RI. Restart LSDC GUI!")    
  

  
def robotOn():
  """robotOn() : use the robot to mount samples"""
  setBlConfig("robot_online",1)


def robotOff():
  """robotOff() : fake mounting samples"""  
  setBlConfig("robot_online",0)


def zebraVecDaqSetup(angle_start,imgWidth,exposurePeriodPerImage,numImages,filePrefix,data_directory_name,file_number_start,scanEncoder=3): #scan encoder 0=x, 1=y,2=z,3=omega
#careful - there's total exposure time, exposure period, exposure time
#this is called in raster before the row processing loop

  setPvDesc("vectorExpose",1)
  detector_dead_time = det_lib.detector_get_deadtime()
  total_exposure_time = exposurePeriodPerImage*numImages
  exposureTimePerImage =  exposurePeriodPerImage - detector_dead_time
  yield from zebra_daq_prep(zebra)

  yield from setup_zebra_vector_scan_for_raster(zebra=zebra, angle_start=angle_start, image_width=imgWidth, exposure_time_per_image=exposureTimePerImage,
                                exposure_period_per_image=exposurePeriodPerImage, detector_dead_time=detector_dead_time,
                                num_images=numImages, scan_encoder=scan_encoder)
  logger.info("exp tim = " + str(exposureTimePerImage))  

  setPvDesc("vectorHold",0)  

def zebraVecDaqSetupBluesky(angle_start,imgWidth,exposurePeriodPerImage,numImages,filePrefix,data_directory_name,file_number_start,scanEncoder=3): #scan encoder 0=x, 1=y,2=z,3=omega
  detector_dead_time = det_lib.detector_get_deadtime()
  total_exposure_time = exposurePeriodPerImage*numImages
  exposureTimePerImage =  exposurePeriodPerImage - detector_dead_time
  yield from zebra_daq_prep(zebra)

  yield from setup_zebra_vector_scan_for_raster(zebra=zebra, angle_start=angle_start, image_width=imgWidth, exposure_time_per_image=exposureTimePerImage,
                                exposure_period_per_image=exposurePeriodPerImage, detector_dead_time=detector_dead_time,
                                num_images=numImages, scan_encoder=scan_encoder)
  logger.info("exp tim = " + str(exposureTimePerImage))

  setPvDesc("vectorHold",0)
  
def setProcRam():
  if (daq_utils.beamline == "amx"):
    db_lib.setBeamlineConfigParam("amx","spotNode1","xf17id1-srv1")
    db_lib.setBeamlineConfigParam("amx","spotNode2","xf17id1-srv1")
    db_lib.setBeamlineConfigParam("amx","cbfComm","eiger2cbf")
    db_lib.setBeamlineConfigParam("amx","dialsComm","dials.find_spots_client")        
  else:
    db_lib.setBeamlineConfigParam("fmx","spotNode1","xf17id2-ws6")
    db_lib.setBeamlineConfigParam("fmx","spotNode2","xf17id2-ws6")
    db_lib.setBeamlineConfigParam("fmx","cbfComm","eiger2cbf")
    db_lib.setBeamlineConfigParam("fmx","dialsComm","dials.find_spots_client")        
    

def setProcGPFS():
  if (daq_utils.beamline == "amx"):
    db_lib.setBeamlineConfigParam("amx","spotNode1","uranus-cpu002")
    db_lib.setBeamlineConfigParam("amx","spotNode2","uranus-cpu003")
    db_lib.setBeamlineConfigParam("amx","spotNode3","uranus-cpu002")
    db_lib.setBeamlineConfigParam("amx","spotNode4","uranus-cpu003")
    db_lib.setBeamlineConfigParam("amx","spotNode5","uranus-cpu002")
    db_lib.setBeamlineConfigParam("amx","spotNode6","uranus-cpu003")    
    db_lib.setBeamlineConfigParam("amx","cbfComm","eiger2cbf")
    db_lib.setBeamlineConfigParam("amx","dialsComm","dials.find_spots_client")
    
  else:
    db_lib.setBeamlineConfigParam("fmx","spotNode1","uranus-cpu007")
    db_lib.setBeamlineConfigParam("fmx","spotNode2","uranus-cpu008")
    db_lib.setBeamlineConfigParam("fmx","spotNode3","uranus-cpu009")
    db_lib.setBeamlineConfigParam("fmx","spotNode4","uranus-cpu010")
    db_lib.setBeamlineConfigParam("fmx","spotNode5","uranus-cpu008")
    db_lib.setBeamlineConfigParam("fmx","spotNode6","uranus-cpu004")        
    db_lib.setBeamlineConfigParam("amx","cbfComm","eiger2cbf")
    db_lib.setBeamlineConfigParam("amx","dialsComm","dials.find_spots_client")
    


def setFastDPNode(nodeName):
  setBlConfig("fastDPNode",nodeName)

def setDimpleNode(nodeName):
  setBlConfig("dimpleNode",nodeName)

def setDimpleCommand(commName):
  setBlConfig("dimpleComm",commName)
  

    
def lastOnSample():
  if (ednaActiveFlag == 1):
    return False
  current_sample = db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')['sampleID']
  logger.info(f'number of requests for current sample: {len(db_lib.getRequestsBySampleID(current_sample))}')
  if len(db_lib.getRequestsBySampleID(current_sample)) > 1:  # quickly check if there are other requests for this sample
    r = db_lib.popNextRequest(daq_utils.beamline)  # do comparison above to avoid this time-expensive call
    if r:
      logger.info(f'next sample: {r["sample"]} current_sample:{current_sample}')
      logger.info(f"Priority: {r['priority']}, Request type: {r['request_type']}, UID: {r['uid']}")
      if (r["sample"] == db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')['sampleID']):
        return False
  return True

def homePins():
  setPvDesc("homePinY",1)
  setPvDesc("homePinZ",1)
  time.sleep(2)  
  setPvDesc("syncPinY",1)
  setPvDesc("syncPinZ",1)    
  
def restartEMBL():
    emblserverName = f'{getBlConfig("hostnameBase")}-emblserver'
    os.system(f"ssh -q -X {emblserverName} \"runEMBL\"&")


def queueCollectOn():
  """queueCollectOn() : allow for creating requests for samples that are not mounted"""
  setBlConfig("queueCollect",1)

def queueCollectOff():
  """queueCollectOff() : do not allow creating requests for samples that are not mounted"""  
  setBlConfig("queueCollect",0)

def guiLocal(): #monitor omega RBV
  """guiLocal() : show the readback of the Omega motor as it's moving. Can lead to lags when operating remotely with reduced bandwidth."""
  setBlConfig("omegaMonitorPV","RBV")

def guiRemote(): #monitor omega VAL
  """guiRemote() : show the setpoint of the Omega motor, instead of the constant readback. This can be used to reduce video lags when operating remotely with reduced bandwidth"""
  setBlConfig("omegaMonitorPV","VAL")

def spotNodes(*args):
  """spotNodes(*args) : Set the dials spotfinding nodes. You must give 8 nodes. Example: spotNodes(4,5,7,8,12,13,14,15)"""
  if (len(args) != SPOT_MIN_NODES):
    logger.error(f"C'mon, I need {SPOT_MIN_NODES} nodes. No change. Try again.")
  else:
    for i in range (0,len(args)):
      setBlConfig("spotNode"+str(i+1),"uranus-cpu%03d" % args[i])

def fastDPNodes(*args):
  """fastDPNodes(*args) : Set the fastDP nodes. You must give 4 nodes. Example: fastDPNodes(4,5,7,8)"""  
  if (len(args) != FAST_DP_MIN_NODES):
    logger.error(f"C'mon, I need {FAST_DP_MIN_NODES} nodes. No change. Try again.")
  else:
    for i in range (0,len(args)):
      setBlConfig("fastDPNode"+str(i+1),"uranus-cpu%03d" % args[i])

def setVisitName(vname):
  setBlConfig("visitName",str(vname))

def setScannerType(s_type): #either "PI" or "Normal"
  """setScannerType(s_type): #either PI or Normal"""
  setBlConfig("scannerType",str(s_type))

def getVisitName(beamline):
  return db_lib.getBeamlineConfigParam(beamline,"visitName")


def setWarmupInterval(interval):
  """setWarmupInterval(interval) : set the number of mounts between automatic robot warmups"""
  setBlConfig("robotWarmupInterval",int(interval))

def setAutoRasterDelay(interval):
  """setAutoRasterDelay(delayTime) : set delay time before autoRaster in Q-collect"""
  setBlConfig("autoRasterDelay",float(interval))
  
def procOn():
  """procOn() : Turns on raster heatmap generation"""  
  setBlConfig("rasterProcessFlag",1)

def procOff():
  """procOff() : Turns off raster heatmap generation"""
  setBlConfig("rasterProcessFlag",0)

def backoffDetector():
  if (daq_utils.beamline == "amx"):
    beamline_lib.mvaDescriptor("detectorDist",700.0)
  else:
    beamline_lib.mvaDescriptor("detectorDist",1000.0)

def disableMount():
  """disableMount() : turn off robot mounting. Usually done in an error situation where we want staff intervention before resuming."""
  setBlConfig("mountEnabled",0)

def enableMount():
  """enableMount() : allow robot mounting"""
  setBlConfig("mountEnabled",1)

def set_beamsize(sizeV, sizeH):
  if (sizeV == 'V0'):
    setPvDesc("CRL_V2A_OUT",1)
    setPvDesc("CRL_V1A_OUT",1)
    setPvDesc("CRL_V1B_OUT",1)
    setPvDesc("CRL_VS_OUT",1)        
  elif (sizeV == 'V1'):
    setPvDesc("CRL_VS_IN",1)    
    setPvDesc("CRL_V2A_OUT",1)
    setPvDesc("CRL_V1A_IN",1)
    setPvDesc("CRL_V1B_OUT",1)
  else:
    logger.error("Error: Vertical size argument has to be \'V0\' or  \'V1\'")
  if (sizeH == 'H0'):  
    setPvDesc("CRL_H4A_OUT",1)
    setPvDesc("CRL_H2A_OUT",1)
    setPvDesc("CRL_H1A_OUT",1)
    setPvDesc("CRL_H1B_OUT",1)
  elif (sizeH == 'H1'):  
    setPvDesc("CRL_H4A_OUT",1)
    setPvDesc("CRL_H2A_IN",1)
    setPvDesc("CRL_H1A_IN",1)
    setPvDesc("CRL_H1B_IN",1)
  else:
    logger.error("Error: Horizontal size argument has to be \'H0\' or  \'H1\'")
  for index, key in enumerate(BEAMSIZE_OPTIONS.keys()):
    if BEAMSIZE_OPTIONS[key] == [sizeV, sizeH]:
      daq_lib.set_field("size_mode", index)
  

  
def vertRasterOn():
  """vertRasterOn() : raster vertically when rasters are taller than they are wide"""
  setBlConfig("vertRasterOn",1)

def vertRasterOff():
  """vertRasterOff() : only raster vertically for single-column (line) rasters"""
  setBlConfig("vertRasterOn",0)


def logMe():
  """logMe() : Edwin asked for this"""
  print(time.ctime())
  print("governor: " + str(getPvDesc("governorMessage")))
  print("SampleX: " + str(beamline_lib.motorPosFromDescriptor("sampleX")) + " SampleY: " + str(beamline_lib.motorPosFromDescriptor("sampleY")) + "SampleZ: " + str(beamline_lib.motorPosFromDescriptor("sampleZ")))
  print("CryoXY: " + str(beamline_lib.motorPosFromDescriptor("cryoXY")))
  print("Gripper Temp: " + str(getPvDesc("gripTemp")))
  print("Dewar Position: " + str(beamline_lib.motorPosFromDescriptor("dewarRot")))
  print("Force Torque Sensor Status: " + str(getPvDesc("robotFTSensorStat")))
  print("Force Torque X " + str(getPvDesc("robotForceX")) + " Y: " + str(getPvDesc("robotForceY")) + " Z: " + str(getPvDesc("robotForceZ")))
  

def setSlit1X(mval):
  beamline_lib.mvaDescriptor("slit1XGap",float(mval))

def setSlit1Y(mval):
  beamline_lib.mvaDescriptor("slit1YGap",float(mval))
  
def emptyQueue():
  """emptyQueue() : Intended to recover from corrupted requests when GUI won't start"""
  reqList = list(db_lib.getQueue(daq_utils.beamline))
  for i in range (0,len(reqList)):
    db_lib.deleteRequest(reqList[i]["uid"])
  

def topViewCheckOn():
  setBlConfig(TOP_VIEW_CHECK,1)

def anneal(annealTime=1.0):
    if daq_utils.beamline == 'fmx':
      annealer = fmxAnnealer
    elif daq_utils.beamline == 'amx':
      annealer = amxAnnealer
    else:
      daq_lib.gui_message('Annealer code only available in AMX, FMX')
      return -1

    if not govStatusGet('SA'):
      daq_lib.gui_message('Not in Governor state SA, exiting')
      return -1

    if govStateSet('CB') == -1:
      logger.error("not able to get to CB governor state")
      return -1

    annealer.anneal(annealTime)

    if govStateSet('SA') == -1:
      logger.error("not able to return to SA governor state")
      return -1
  
def fmx_expTime_to_10MGy(beamsizeV = 3.0, beamsizeH = 5.0, vectorL = 100, energy = 12.7, wedge = 180, flux = 1e12, verbose = True):
  if (not os.path.exists("2vb1.pdb")):
    os.system("ln -s $CONFIGDIR/2vb1.pdb .")
    os.system("mkdir rd3d")
  raddoseLib.fmx_expTime(beamsizeV = beamsizeV, beamsizeH = beamsizeH, vectorL = vectorL, energy = energy, wedge = wedge, flux = flux, verbose = verbose)
#  why doesn't this work? raddoseLib.fmx_expTime_to_10MGy(beamsizeV, beamsizeH, vectorL, energy, wedge, flux, verbose)

def unlockGUI():
  """unlockGUI() : unlock lsdcGui"""
  
  daq_lib.unlockGUI()

def lockGUI():
  """lockGUI() : lock lsdcGui"""
  
  daq_lib.lockGUI()
  
def beamCheckOn():
  setBlConfig(BEAM_CHECK,1)

def beamCheckOff():
  setBlConfig(BEAM_CHECK,0)

def HePathOff():
  setBlConfig("HePath",0)

def HePathOn():
  setBlConfig("HePath",1)
  

def lsdcHelp():
  print(setGridRasterParams.__doc__)
  print(printGridRasterParams.__doc__)                   
  print(robotOn.__doc__)
  print(robotOff.__doc__)
  print(procOn.__doc__)
  print(procOff.__doc__)
  print(queueCollectOn.__doc__)
  print(queueCollectOff.__doc__)
  print(spotNodes.__doc__)
  print(fastDPNodes.__doc__)
  print(setWarmupInterval.__doc__)
  print(setAutoRasterDelay.__doc__)  
  print(disableMount.__doc__)
  print(enableMount.__doc__)
  print(vertRasterOn.__doc__)
  print(vertRasterOff.__doc__)
  print(emptyQueue.__doc__)
  print(logMe.__doc__)
  print(setAttenBCU.__doc__)
  print(setAttenRI.__doc__)
  print(unlockGUI.__doc__)
  print(collectSpec.__doc__)
  print(setScannerType.__doc__)            
  print("recoverRobot()")
  print("setFastDPNode(nodeName)")
  print("setDimpleNode(nodeName)")
  print("setDimpleCommand(commandString)")
  print("beamCheckOn()")
  print("beamCheckOff()")
  print("HePathOn()")
  print("HePathOff()")  
  print("homePins()")
  
  



  
  
