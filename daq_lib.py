import os
import grp
import getpass
import time
import subprocess
import daq_macros
from math import *
from gon_lib import *
from det_lib import *
import robot_lib
import daq_utils
import beamline_lib
import beamline_support
from beamline_support import getPvValFromDescriptor as getPvDesc, setPvValFromDescriptor as setPvDesc
import db_lib
from daq_utils import getBlConfig
from config_params import *
from kafka_producer import send_kafka_message
from start_bs import govs, gov_robot, flyer, RE, gonio, robot_arm, dewar
import gov_lib
from bluesky.preprocessors import finalize_wrapper
import bluesky.plan_stubs as bps
import logging
from utils import validation
logger = logging.getLogger(__name__)

try:
  import ispybLib
except Exception as e:
  logger.error("daq_lib: ISPYB import error, %s" % e)

if daq_utils.beamline in ["amx", "fmx"]:
  from start_bs import gov_mon_signal


#all keys below are created as beamlineComm PVs. if adding items here, be sure to add them to the simulator
var_list = {'beam_check_flag':0,'overwrite_check_flag':1,'omega':0.00,'kappa':0.00,'phi':0.00,'theta':0.00,'distance':10.00,'rot_dist0':300.0,'inc0':1.00,'exptime0':5.00,'file_prefix0':'lowercase','numstart0':0,'col_start0':0.00,'col_end0':1.00,'scan_axis':'omega','wavelength0':1.1,'datum_omega':0.00,'datum_kappa':0.00,'datum_phi':0.00,'size_mode':0,'spcgrp':1,'state':"Idle",'state_percent':0,'datafilename':'none','active_sweep':-1,'html_logging':1,'take_xtal_pics':0,'px_id':'none','xtal_id':'none','current_pinpos':0,'sweep_count':0,'group_name':'none','mono_energy_target':1.1,'mono_wave_target':1.1,'energy_inflection':12398.5,'energy_peak':12398.5,'wave_inflection':1.0,'wave_peak':1.0,'energy_fall':12398.5,'wave_fall':1.0,'beamline_merit':0,'fprime_peak':0.0,'f2prime_peak':0.0,'fprime_infl':0.0,'f2prime_infl':0.0,'program_state':"Program Ready",'filter':0,'edna_aimed_completeness':0.99,'edna_aimed_ISig':2.0,'edna_aimed_multiplicity':'auto','edna_aimed_resolution':'auto','mono_energy_current':1.1,'mono_energy_scan_step':1,'mono_wave_current':1.1,'mono_scan_points':21,'mounted_pin':(db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')["sampleID"]),'pause_button_state':'Pause','vector_on':0,'vector_fpp':1,'vector_step':0.0,'vector_translation':0.0,'xia2_on':0,'grid_exptime':0.2,'grid_imwidth':0.2,'choochResultFlag':"0",'xrecRasterFlag':"0"}


global x_vec_start, y_vec_start, z_vec_start, x_vec_end, y_vec_end, z_vec_end, x_vec, y_vec, z_vec
global var_channel_list
global message_string_pv
global gui_popup_message_string_pv
global data_directory_name
global currentIspybDCID

global fastDPNodeCount
fastDPNodeCount = 4
global fastDPNodeCounter
fastDPNodeCounter = 0



global mountCounter
mountCounter = 0

var_channel_list = {}


global abort_flag
abort_flag = 0

def init_var_channels():
  global var_channel_list

  for varname in list(var_list.keys()):
    logger.debug('initing %s' % varname)
    var_channel_list[varname] = beamline_support.pvCreate(daq_utils.beamlineComm + varname)
    if (varname != 'size_mode'):
      beamline_support.pvPut(var_channel_list[varname],var_list[varname])


def gui_message(message_string): 
  beamline_support.pvPut(gui_popup_message_string_pv,message_string)

def destroy_gui_message():
  beamline_support.pvPut(gui_popup_message_string_pv,"killMessage")


def unlatchGov(): # Command needed for FloCos to recover robot
  message1 = f"OLD: unlatchGov called, gov active state = {govs.sel.active.get()}"
  print(message1)
  logger.info(message1)
  govs.sel.active.set(1)
  message2 = f"NEW: unlatchGov called, gov active state = {govs.sel.active.get()}"
  print(message2)
  logger.info(message2)


def set_field(param,val):
  var_list[param] = val
  beamline_support.pvPut(var_channel_list[param],val)


def get_field(param):
  return var_list[param]
    

def set_group_name(group_name):
  set_field("group_name",group_name)

def set_distance_value(distance):
  set_field("distance",atof(distance))
  
def set_xbeam(xbeam): #detector center for image header, in pixels
  setPvDesc("beamCenterX",float(xbeam))

def set_ybeam(ybeam):
  setPvDesc("beamCenterY",float(ybeam))  


def set_beamcenter(xbeam,ybeam): #detector center for image header, in pixels
  set_xbeam(xbeam)
  set_ybeam(ybeam)

def set_space_group(spcgrp):
  set_field("spcgrp",spcgrp)


def beam_monitor_on():
  set_field("beam_check_flag",1)

def beam_monitor_off():
  set_field("beam_check_flag",0)

def overwrite_check_on():
  global allow_overwrite
  
  set_field("overwrite_check_flag",1)
  allow_overwrite = 0

def overwrite_check_off():
  global allow_overwrite  

  set_field("overwrite_check_flag",0)
  allow_overwrite = 1
  
def beam_check_on():
  return get_field("beam_check_flag")


def check_beam():
  return 1

def check_pause():
  global pause_flag

  while (pause_flag==1):
    time.sleep(1.0)

def pause_data_collection():
  global pause_flag

  pause_flag = 1
  set_field("pause_button_state","Continue")
  
def continue_data_collection():
  global pause_flag

  pause_flag = 0
  set_field("pause_button_state","Pause")  


def abort_data_collection(flag):
  global datafile_name,abort_flag,image_started

  if (flag==2): #stop queue after current collection
    abort_flag = 2
    return
  gui_message("Aborting. This may take a minute or more.")  
  while not (getPvDesc("VectorActive")): #only stop if actually collecting
    time.sleep(0.1)
  destroy_gui_message()    
  abort_flag = 1
  time.sleep(1.0)
  gon_stop() #this calls osc abort
  setPvDesc("zebraDisarm",1)
  time.sleep(2)
  detector_stop()


def open_shutter():
  lib_open_shutter()
  set_field("state","Expose")

def close_shutter():
  lib_close_shutter()
  set_field("state","Idle")
  
def init_diffractometer():
  lib_init_diffractometer()

def close_diffractometer():
  lib_close_diffractometer()

def home():
  lib_home()

def home_omega():
  lib_home_omega()


def xtal_id(id):
  set_field("xtal_id",id)


def set_relative_zero(omega,kappa,phi):
  set_field("datum_omega",omega)
  set_field("datum_kappa",kappa)
  set_field("datum_phi",phi)

def relative_zero_to_cp():
  set_field("datum_omega",get_field("omega"))
  set_field("datum_kappa",get_field("kappa"))
  set_field("datum_phi",get_field("phi"))


def unlockGUI():
  logger.info('unlocking GUI')
  beamline_support.set_any_epics_pv(daq_utils.beamlineComm+"zinger_flag","VAL",1)  

def lockGUI():
  logger.info('locking GUI')
  beamline_support.set_any_epics_pv(daq_utils.beamlineComm+"zinger_flag","VAL",-1)  

def govMonOn():
  gov_mon_signal.set(1)

def govMonOff():
  gov_mon_signal.set(0)

def flocoLock():
  lockGUI()
  govMonOff()

def flocoUnlock():
  unlockGUI()
  govMonOn()

def flocoStopOperations():
  try:
    daq_macros.run_recovery_procedure(stop=True)
    lockGUI()
  except Exception as e:
    logger.exception("Error encountered while running flocoStopOperations. Stopping...")

def flocoContinueOperations():
  try:
    daq_macros.run_recovery_procedure(stop=False)
    flocoUnlock()
    beamline_support.set_any_epics_pv(daq_utils.beamlineComm + "command_s", "VAL", 
      json.dumps(
              {
                  "function": "runDCQueue",
                  "args": [],
                  "kwargs": {},
              }
          ))
  except Exception as e:
    logger.exception("Error encountered while running flocoContinueOperations. Stopping...")
  
def refreshGuiTree():
  beamline_support.set_any_epics_pv(daq_utils.beamlineComm+"live_q_change_flag","VAL",1)

def broadcast_output(s):
  time.sleep(0.01)
  if (s.find('|') == -1):
    logger.info(s)
  beamline_support.pvPut(message_string_pv,s)


def getRobotConfig():
  return getPvDesc("robotGovConfig",as_string=True)


def mountSample(sampID):
  global mountCounter

  saveDetDist = beamline_lib.motorPosFromDescriptor("detectorDist")  
  warmUpNeeded = 0
  if (getBlConfig("queueCollect") == 1):
    mountCounter+=1
    if (mountCounter > getBlConfig("robotWarmupInterval")):
      warmUpNeeded = 1
  mountedSampleDict = db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')
  currentMountedSampleID = mountedSampleDict["sampleID"]
  if (getBlConfig(TOP_VIEW_CHECK) == 1):
    logger.info("setting work pos")
    if daq_utils.beamline == "fmx" and getPvDesc('robotSaActive'):
      beamline_lib.mvaDescriptor("sampleX", getPvDesc("robotXMountPos"))
      beamline_lib.mvaDescriptor("sampleY", getPvDesc("robotYMountPos"))
      beamline_lib.mvaDescriptor("sampleZ", getPvDesc("robotZMountPos"))
      beamline_lib.mvaDescriptor("omega", 90.0)
      logger.info(f'Done moving motors for{daq_utils.beamline}')
    setPvDesc("robotXWorkPos",getPvDesc("robotXMountPos"))
    setPvDesc("robotYWorkPos",getPvDesc("robotYMountPos"))
    setPvDesc("robotZWorkPos",getPvDesc("robotZMountPos"))
    setPvDesc("robotOmegaWorkPos",90.0)    
    logger.info("done setting work pos")  
  if (currentMountedSampleID != "" and not robot_lib.multiSampleGripper()): #then unmount what's there
    if (sampID!=currentMountedSampleID):
      puckPos = mountedSampleDict["puckPos"]
      pinPos = mountedSampleDict["pinPos"]
      # Set status as currently unmounting
      set_mounted_pin_data(currentMountedSampleID, mount_state=MountState.CURRENTLY_UNMOUNTING.value)
      if robot_lib.unmountRobotSample(gov_robot, puckPos,pinPos,currentMountedSampleID):
        db_lib.deleteCompletedRequestsforSample(currentMountedSampleID)
        (puckPos,pinPos,puckID) = db_lib.getCoordsfromSampleID(daq_utils.beamline,sampID)
        if (warmUpNeeded):
          gui_message("Warming gripper. Please stand by.")
          mountCounter = 0
        # About to mount next sample
        set_mounted_pin_data(sampID, mount_state=MountState.CURRENTLY_MOUNTING.value, sample_pos={'puckPos':puckPos,'pinPos':pinPos})
        mountStat = robot_lib.mountRobotSample(gov_robot, puckPos,pinPos,sampID,init=0,warmup=warmUpNeeded)
        if (warmUpNeeded):
          destroy_gui_message()
        if (mountStat == MOUNT_SUCCESSFUL):
          set_mounted_pin_data(sampID, sample_pos={'puckPos':puckPos,'pinPos':pinPos})
          detDist = beamline_lib.motorPosFromDescriptor("detectorDist")
          if (detDist != saveDetDist):
            if (getBlConfig("HePath") == 0):
              beamline_lib.mvaDescriptor("detectorDist",saveDetDist)
          if getBlConfig('robot_online') and getBlConfig("queueCollect") == 0:
            # Only run mount options when the robot is online and queue collect is off
            daq_macros.run_on_mount_option(sampID)
            gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
        elif(mountStat == MOUNT_UNRECOVERABLE_ERROR):
          clearMountedSample()
          return MOUNT_UNRECOVERABLE_ERROR
        else:
          clearMountedSample()
          return MOUNT_FAILURE
      else:
        set_mounted_pin_data(currentMountedSampleID, mount_state=MountState.FAILED_UNMOUNTING.value)
        return UNMOUNT_FAILURE
    else: #desired sample is mounted, nothing to do
      return MOUNT_SUCCESSFUL
  else: #nothing mounted
    (puckPos,pinPos,puckID) = db_lib.getCoordsfromSampleID(daq_utils.beamline,sampID)
    set_mounted_pin_data(sampID, mount_state=MountState.CURRENTLY_MOUNTING.value, sample_pos={'puckPos':puckPos,'pinPos':pinPos})
    mountStat = robot_lib.mountRobotSample(gov_robot, puckPos,pinPos,sampID,init=1)
    if (mountStat == MOUNT_SUCCESSFUL):
      set_mounted_pin_data(sampID, sample_pos={'puckPos':puckPos,'pinPos':pinPos})
      if getBlConfig('robot_online') and getBlConfig("queueCollect") == 0:
        # Only run mount options when the robot is online and queue collect is off
        daq_macros.run_on_mount_option(sampID)
        gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
    elif(mountStat == MOUNT_UNRECOVERABLE_ERROR):
      clearMountedSample()
      return MOUNT_UNRECOVERABLE_ERROR
    else:
      clearMountedSample()
      return MOUNT_FAILURE
  return MOUNT_SUCCESSFUL


def clearMountedSample():
  set_field("mounted_pin","")
  db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample', info_dict={'puckPos':0,'pinPos':0,'sampleID':""})
  

def set_mounted_pin_data(sample_id, mount_state=MountState.MOUNTED.value, sample_pos=None):
  current_pin_data = f"{sample_id},{mount_state}"
  logger.info(f"current pin data = {current_pin_data}")
  set_field("mounted_pin", current_pin_data)

  if sample_pos:
    info_dict = { 'puckPos' : sample_pos["puckPos"], 
                  'pinPos' : sample_pos["pinPos"],
                  'sampleID': sample_id }
    db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample', info_dict=info_dict)

def unmountSample():
  global mountCounter

  logger.info("unmountSample")
  mountCounter = 0
  mountedSampleDict = db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')
  currentMountedSampleID = mountedSampleDict["sampleID"]
  if (currentMountedSampleID != ""):
    puckPos = mountedSampleDict["puckPos"]
    pinPos = mountedSampleDict["pinPos"]
    # Set status as currently unmounting
    set_mounted_pin_data(currentMountedSampleID, mount_state=MountState.CURRENTLY_UNMOUNTING.value)
    if robot_lib.unmountRobotSample(gov_robot, puckPos,pinPos,currentMountedSampleID):
      db_lib.deleteCompletedRequestsforSample(currentMountedSampleID)      
      robot_lib.finish()
      clearMountedSample()
      return 1
    else:
      set_mounted_pin_data(currentMountedSampleID, mount_state=MountState.FAILED_UNMOUNTING.value)
      return 0

def unmountCold():
  mountedSampleDict = db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')
  currentMountedSampleID = mountedSampleDict["sampleID"]
  if (currentMountedSampleID != ""):
    puckPos = mountedSampleDict["puckPos"]
    pinPos = mountedSampleDict["pinPos"]
    # Set status as currently unmounting
    set_mounted_pin_data(currentMountedSampleID, mount_state=MountState.CURRENTLY_UNMOUNTING.value)
    if robot_lib.unmountRobotSample(gov_robot, puckPos,pinPos,currentMountedSampleID):
      db_lib.deleteCompletedRequestsforSample(currentMountedSampleID)      
      if getBlConfig("robot_online"):
        robot_lib.parkGripper()
      clearMountedSample()
      setPvDesc("robotGovActive",1)
      return 1
    else:
      set_mounted_pin_data(currentMountedSampleID, mount_state=MountState.FAILED_UNMOUNTING.value)
      return 0

def waitBeam():
  waiting = 0
  while (1):
    if (getPvDesc("beamAvailable") or getBlConfig(BEAM_CHECK) == 0):
      if (waiting):
        waiting = 0
        destroy_gui_message()          
      break
    else:
      if not (waiting):      
        waiting = 1
        gui_message("Waiting for beam. Type beamCheckOff() in lsdcServer window to continue.")
      time.sleep(1.0)

def waitRobotArm():
  waiting = True
  while waiting:
    gui_message("Robot arm speed not at 100%. Set speed to 100")
    time.sleep(1.0)
    if robot_arm.is_full_speed():
      waiting = False

def puck_lifted(puckPos):
  puck_plate_pos = f"{(puckPos//3)+1}{'ABC'[puckPos%3]}"
  if not dewar.get_puck_status(puck_plate_pos):
    logger.error(f"Could not find puck in position {puck_plate_pos}, skipping collection")
    return True
  return False

def runDCQueue(): #maybe don't run rasters from here???
  global abort_flag

  autoMounted = 0 #this means the mount was performed from a runQueue, as opposed to a manual mount button push
  logger.info("running queue in daq server")
  while (1):
    currentRequest = db_lib.popNextRequest(daq_utils.beamline)
    if (getBlConfig("queueCollect") == 1): 
      if (getBlConfig(BEAM_CHECK) == 1):
        waitBeam()
      if not robot_arm.is_full_speed():
        waitRobotArm()
      sampleID = currentRequest["sample"]
      puckPos,pinPos,puckID = db_lib.getCoordsfromSampleID(daq_utils.beamline, sampleID)
      if puck_lifted(puckPos):
        # If the puck is lifted set the collection as complete and move on
        db_lib.updatePriority(currentRequest["uid"],-1)
        refreshGuiTree()
        continue
      
    if (abort_flag):
      abort_flag =  0 #careful about when to reset this
      return
    if (currentRequest == {}):
      break
    elif currentRequest is None:
      gui_message("Queue contains collection requests from different proposals" 
                  "and not using commissioning directory."
                  "Please remove invalid requests or switch to" 
                  "commissioning directory to continue")
      break
    logger.info("processing request " + str(time.time()))
    reqObj = currentRequest["request_obj"]
    gov_lib.set_detz_in(gov_robot, reqObj["detDist"])
    if (reqObj["detDist"] >= DETECTOR_SAFE_DISTANCE[daq_utils.beamline] and getBlConfig("HePath") == 0):
      gov_lib.set_detz_out(gov_robot, reqObj["detDist"])
    sampleID = currentRequest["sample"]
    mountedSampleDict = db_lib.beamlineInfo(daq_utils.beamline, 'mountedSample')
    currentMountedSampleID = mountedSampleDict["sampleID"]
    if (currentMountedSampleID != sampleID):
      if (getBlConfig("queueCollect") == 0):
        current_request = db_lib.popNextRequest(daq_utils.beamline)
        logger.info(f"Current request: {current_request}")
        if currentRequest is None:
          gui_message("Queue contains collection requests from different proposals" 
                      "and not using commissioning directory."
                      "Please remove invalid requests or switch to" 
                      "commissioning directory to continue")
          return
        if current_request["request_obj"]["beamline"] != daq_utils.beamline:
            message = f"Beamline mismatch between collection and beamline. request: '{current_request['request_obj']['beamline']}' beamline: '{daq_utils.beamline}'. request_uid: {current_request['uid']}\nuse db_lib.delete_request(uid) to delete this bad request"
            logger.error(message)
            gui_message(message)
        gui_message("You can only run requests on the currently mounted sample. Remove offending request and continue.")
        return
      mountStat = mountSample(sampleID)
      logger.info("automounting mp= " + currentMountedSampleID + " samp= " + str(sampleID))
      if (mountStat == 1):
        autoMounted = 1
      elif(mountStat == 2):
        db_lib.updatePriority(currentRequest["uid"],-1)
        refreshGuiTree()        
        continue
      else:
        return 0
    db_lib.updatePriority(currentRequest["uid"],99999)
    currentRequest['priority'] = 99999 #TODO have updatePriority return an updated request?
    refreshGuiTree() #just tells the GUI to repopulate the tree from the DB
    logger.info("calling collect data " + str(time.time()))    
    colStatus = collectData(currentRequest)
    logger.info("done collecting data")
    if (autoMounted and db_lib.queueDone(daq_utils.beamline)):
      if (getBlConfig(UNMOUNT_COLD_CHECK)):
        unmountCold()
      else:
        unmountSample()

    

def stopDCQueue(flag):
  logger.info("stopping queue in daq server " + str(flag))
  abort_data_collection(int(flag))



def logMxRequestParams(currentRequest,wait=True):
  global currentIspybDCID
  reqObj = currentRequest["request_obj"]
  transmissionReadback = getPvDesc("transmissionRBV")
  flux = getPvDesc("flux")
  resultObj = {"requestObj":reqObj,"transmissionReadback":transmissionReadback,"flux":flux}  
  resultID = db_lib.addResultforRequest("mxExpParams",currentRequest["uid"],owner=daq_utils.owner,result_obj=resultObj,proposalID=daq_utils.getProposalID(),beamline=daq_utils.beamline)
  newResult = db_lib.getResult(resultID)
  newResult['result_obj']['requestObj']['xbeam'] = reqObj['xbeam']
  newResult['result_obj']['requestObj']['ybeam'] = reqObj['ybeam']
  db_lib.beamlineInfo(daq_utils.beamline, 'currentSampleID', info_dict={'sampleID':currentRequest["sample"]})
  db_lib.beamlineInfo(daq_utils.beamline, 'currentRequestID', info_dict={'requestID':currentRequest["uid"]})
  logfile = open("dataColLog.txt","a+")
  try:
    logfile.write("\n\ntimestamp: " + time.ctime(currentRequest["time"])+"\n")
  except KeyError:    
    logger.error("caught key error in logging")
    logger.error(currentRequest)
  logfile.write("protocol: " + reqObj["protocol"] +"\n")  
  logfile.write("data prefix: " + reqObj["file_prefix"] +"\n")
  logfile.write("flux: " + str(flux) +"\n")
  logfile.write("transimission percent: " + str(transmissionReadback) +"\n")
  logfile.write("total current (BCU): " + str(getPvDesc("totalCurrentBCU")) +"\n")    
  logfile.write("omega start: " + str(reqObj["sweep_start"]) +"\n")
  logfile.write("omega end: " + str(reqObj["sweep_end"]) +"\n")
  logfile.write("image width: " + str(reqObj["img_width"]) +"\n")
  logfile.write("exposure time per image (s): " + str(reqObj["exposure_time"]) +"\n")
  logfile.write("detector distance: " + str(reqObj["detDist"]) +"\n")
  logfile.write("wavelength: " + str(reqObj["wavelength"]) +"\n")
  logfile.close()
  visitName = daq_utils.getVisitName()
  try: #I'm worried about unforseen ispyb db errors
    #rasters results are entered in ispyb by the GUI, no need to wait
    if wait:
      time.sleep(getBlConfig(ISPYB_RESULT_ENTRY_DELAY))
    currentIspybDCID = ispybLib.insertResult(newResult,"mxExpParams",currentRequest,visitName)
  except Exception as e:
    currentIspybDCID = 999999
    logger.error("logMxRequestParams - ispyb error: %s" % e)



def collectData(currentRequest):
  global data_directory_name,currentIspybDCID,fastDPNodeCount,fastDPNodeCounter

  if (daq_utils.beamline == "fmx"):
    if (getPvDesc("detCoverRBV") == 0):
      logger.info("opening det cover")
      setPvDesc("detCoverOpen",1)
  logMe = 1
  reqObj = currentRequest["request_obj"]
  data_directory_name = str(reqObj["directory"])
  exposure_period = reqObj["exposure_time"]
  wavelength = reqObj["wavelength"]
  resolution = reqObj["resolution"]
  slit_height = reqObj["slit_height"]
  slit_width = reqObj["slit_width"]
  attenuation = reqObj["attenuation"]
  img_width = reqObj["img_width"]
  file_prefix = str(reqObj["file_prefix"])
  logger.info(reqObj["protocol"])
  prot = str(reqObj["protocol"])
  sweep_start = reqObj["sweep_start"]
  sweep_end = reqObj["sweep_end"]
  range_degrees = abs(sweep_end-sweep_start)  
  sweep_start = reqObj["sweep_start"]%360.0
  file_number_start = reqObj["file_number_start"]
  basePath = reqObj["basePath"]
  visitName = daq_utils.getVisitName()
  jpegDirectory = visitName + "/jpegs/" + data_directory_name[data_directory_name.find(visitName)+len(visitName):len(data_directory_name)]  
  colDist = reqObj["detDist"]
    
  status = 1
  if not (os.path.isdir(data_directory_name)):
    logger.debug(f'creating {data_directory_name}')
    comm_s = "mkdir -p " + data_directory_name
    os.system(comm_s)
    comm_s = "mkdir -p " + jpegDirectory
    os.system(comm_s)
  logger.debug('starting initial motions - transmission and detector distance')
  daq_macros.setTrans(attenuation)
  if not prot in [CollectionProtocols.E_SCAN]:
    beamline_lib.mvaDescriptor("detectorDist",colDist)  
  logger.debug('transmission and detector distance done')
  # now that the detector is in the correct position, get the beam center
  currentRequest['request_obj']['xbeam'] = getPvDesc('beamCenterX')
  currentRequest['request_obj']['ybeam'] = getPvDesc('beamCenterY')
  db_lib.updateRequest(currentRequest)
  if prot == CollectionProtocols.RASTER:
    logger.info('entering raster')
    RE(daq_macros.snakeRaster(currentRequest["uid"]))
    status = 0
    logger.info('exiting raster')
  elif prot == CollectionProtocols.STEP_RASTER:
    status = daq_macros.snakeStepRaster(currentRequest["uid"])    
  elif prot in (CollectionProtocols.VECTOR, CollectionProtocols.STEP_VECTOR):
    imagesAttempted = collect_detector_seq_hw(sweep_start,range_degrees,img_width,exposure_period,file_prefix,data_directory_name,file_number_start,currentRequest)
  elif prot == CollectionProtocols.MULTI_COL:
    RE(daq_macros.snakeRaster(currentRequest["uid"]))
  elif prot == CollectionProtocols.RASTER_SCREEN:
    daq_macros.rasterScreen(currentRequest)    
  elif prot == CollectionProtocols.MULTI_COL_Q:
    daq_macros.multiCol(currentRequest)
  elif prot == CollectionProtocols.E_SCAN:
    daq_macros.eScan(currentRequest)
  else: #standard, screening, or edna - these may require autoalign, checking first
    if (reqObj["pos_x"] != -999):
      beamline_lib.mvaDescriptor("sampleX",reqObj["pos_x"])
      beamline_lib.mvaDescriptor("sampleY",reqObj["pos_y"])
      beamline_lib.mvaDescriptor("sampleZ",reqObj["pos_z"])
    elif (reqObj["centeringOption"] == "Interactive"): #robotic, pause and let user center
      pause_data_collection()
      check_pause()
    else:
      logger.info("autoRaster")
      daq_macros.run_loop_center_plan()
      if not (daq_macros.autoRasterLoop(currentRequest)):
        logger.info("could not center sample")
        db_lib.updatePriority(currentRequest["uid"],-1)
        refreshGuiTree()
        return 0
      else:
        if (reqObj["centeringOption"] == "AutoLoop"):
          reqObj["sweep_start"] = beamline_lib.motorPosFromDescriptor("omega") #%360.0?
          sweep_start = reqObj["sweep_start"]
        if (reqObj["centeringOption"] == "AutoRaster"):
          reqObj["sweep_start"] = beamline_lib.motorPosFromDescriptor("omega") - 90.0 #%360.0?
          sweep_start = reqObj["sweep_start"]
      daq_macros.setTrans(attenuation)      

    if (reqObj["protocol"] in (CollectionProtocols.CHARACTERIZE, CollectionProtocols.EDNA_COL):
      characterizationParams = reqObj["characterizationParams"]
      index_success = daq_macros.dna_execute_collection3(0.0,img_width,2,exposure_period,data_directory_name+"/",file_prefix,1,-89.0,1,currentRequest)
      if (index_success):        
        resultsList = db_lib.getResultsforRequest(currentRequest["uid"]) # because for testing I keep running the same request. Probably not in usual use.
        results = None
        for i in range(0,len(resultsList)):
          if (resultsList[i]['result_type'] == 'characterizationStrategy'):
            results = resultsList[i]
            break
        if (results != None):
          
          strategyResults = results["result_obj"]["strategy"]
          stratStart = strategyResults["start"]
          stratEnd = strategyResults["end"]
          stratWidth = strategyResults["width"]
          stratExptime = strategyResults["exptime"]
          stratTrans = strategyResults["transmission"]          
          stratDetDist = strategyResults["detDist"]
          sampleID = currentRequest["sample"]
          tempnewStratRequest = daq_utils.createDefaultRequest(sampleID)
          newReqObj = tempnewStratRequest["request_obj"]
          newReqObj["sweep_start"] = stratStart
          newReqObj["sweep_end"] = stratEnd
          newReqObj["img_width"] = stratWidth
          newReqObj["exposure_time"] = stratExptime
          newReqObj["attenuation"] = stratTrans
          newReqObj["detDist"] = stratDetDist
          newReqObj["directory"] = data_directory_name
          newReqObj["pos_x"] = beamline_lib.motorPosFromDescriptor("sampleX")
          newReqObj["pos_y"] = beamline_lib.motorPosFromDescriptor("sampleY")
          newReqObj["pos_z"] = beamline_lib.motorPosFromDescriptor("sampleZ")
          newReqObj["fastDP"] = True # this is where you might want a "new from old" request to carry over stuff like this.
          newReqObj["fastEP"] = reqObj["fastEP"]
          newReqObj["dimple"] = reqObj["dimple"]                
          newReqObj["xia2"] = reqObj["xia2"]
          runNum = db_lib.incrementSampleRequestCount(sampleID)
          newReqObj["runNum"] = runNum
          newStratRequest = db_lib.addRequesttoSample(sampleID,newReqObj["protocol"],daq_utils.owner,newReqObj,priority=0,proposalID=daq_utils.getProposalID())
          if (reqObj["protocol"] == CollectionProtocols.EDNA_COL):
            logger.info("new strat req = ")
            logger.info(newStratRequest)
            db_lib.updatePriority(currentRequest["uid"],-1)
            refreshGuiTree()
            collectData(db_lib.getRequestByID(newStratRequest))
            return 1
    else: #standard
      logger.info("moving omega to start " + str(time.time()))      
      if daq_utils.beamline == "nyx":
          direction = (sweep_end - sweep_start) / abs(sweep_end - sweep_start)
          beamline_lib.mvaDescriptor("omega",sweep_start - direction*0.05)
      else:
          beamline_lib.mvaDescriptor("omega",sweep_start)
      collect_detector_seq_hw(sweep_start,range_degrees,img_width,exposure_period,file_prefix,data_directory_name,file_number_start,currentRequest)
  try:
    if (logMe) and prot == CollectionProtocols.RASTER:
      logMxRequestParams(currentRequest,wait=False)
    elif (logMe):
      logMxRequestParams(currentRequest)
  except TypeError:
    logger.error("caught type error in logging")
  except IndexError:
    logger.error("caught index error in logging")
  except KeyError as e:
    logger.error('caught key error in logging: %s' % e)

  # collection finished, start processing
  if reqObj["protocol"] in (CollectionProtocols.STANDARD, CollectionProtocols.VECTOR, CollectionProtocols.RASTER):
    send_kafka_message(topic=f'{daq_utils.beamline}.lsdc.documents', event='stop', uuid=currentRequest['uid'], protocol=reqObj["protocol"])
  if prot in (CollectionProtocols.VECTOR, CollectionProtocols.STANDARD, CollectionProtocols.STEP_VECTOR):
    if daq_utils.beamline != "nyx":
      seqNum = flyer.detector.cam.sequence_id.get()
      comm_s = os.environ["LSDCHOME"] + "/runSpotFinder4syncW.py " + data_directory_name + " " + file_prefix + " " + str(currentRequest["uid"]) + " " + str(seqNum) + " " + str(currentIspybDCID)+ "&"
      logger.info(f"NOT running spotfinding for per-image analysis in Synchweb: {comm_s}")
      #os.system(comm_s)    
      filename = f"{data_directory_name}/{file_prefix}_{seqNum}_master.h5"
      logger.info(f"Checking integrity of {filename}")
      timeout_index = 0
      while not validation.validate_master_HDF5_file(filename):
        timeout_index += 1
        time.sleep(3)
        if timeout_index > 15:
          logger.error(f"Unable to verify master file after {timeout_index} tries, not proceeding with processing")
          return 
      if img_width > 0: #no dataset processing in stills mode
        if (reqObj["fastDP"]):
          if (reqObj["fastEP"]):
            fastEPFlag = 1
          else:
            fastEPFlag = 0
          if (reqObj["dimple"]):
            dimpleFlag = 1
          else:
            dimpleFlag = 0        
          nodeName = "fastDPNode" + str((fastDPNodeCounter%fastDPNodeCount)+1)
          fastDPNodeCounter+=1
          node = getBlConfig(nodeName)      
          dimpleNode = getBlConfig("dimpleNode")      
          if (daq_utils.detector_id == "EIGER-16"):
            seqNum = flyer.detector.cam.sequence_id.get()
            comm_s = os.environ["LSDCHOME"] + "/runFastDPH5.py " + data_directory_name + " " + str(seqNum) + " " + str(currentRequest["uid"]) + " " + str(fastEPFlag) + " " + node + " " + str(dimpleFlag) + " " + dimpleNode + " " + str(currentIspybDCID)+ "&"
          else:
            comm_s = os.environ["LSDCHOME"] + "/runFastDP.py " + data_directory_name + " " + file_prefix + " " + str(file_number_start) + " " + str(int(round(range_degrees/img_width))) + " " + str(currentRequest["uid"]) + " " + str(fastEPFlag) + " " + node + " " + str(dimpleFlag) + " " + dimpleNode + "&"
          logger.info(f'Running fastdp command: {comm_s}')
          if daq_utils.beamline in ("amx", "fmx"):
            visitName = daq_utils.getVisitName()
            if (not os.path.exists(visitName + "/fast_dp_dir")) or subprocess.run(['pgrep', '-f', 'loop-fdp-dple-populate'], stdout=subprocess.PIPE).returncode == 1:  # for pgrep, return of 1 means string not found
              os.system("killall -KILL loop-fdp-dple-populate")
              logger.info('starting fast dp result gathering script')
              os.system("cd " + visitName + ";${LSDCHOME}/bin/loop-fdp-dple-populate.sh&")
          os.system(comm_s)
        if (reqObj["xia2"]):
          comm_s = f"ssh -q xf17id2-srv1 \"{os.environ['MXPROCESSINGSCRIPTSDIR']}xia2.sh {currentRequest['uid']} \"&"
          os.system(comm_s)
  
  logger.info('processing should be triggered')
  db_lib.updatePriority(currentRequest["uid"],-1)
  refreshGuiTree()
  logger.info('after refresh GUI tree')
  
  return status

    

def collect_detector_seq_hw(sweep_start,range_degrees,image_width,exposure_period,fileprefix,data_directory_name,file_number,currentRequest,z_target=0,changeState=True): #works for pilatus
  global image_started,allow_overwrite,abort_flag

  logger.info("data directory = " + data_directory_name)
  reqObj = currentRequest["request_obj"]
  protocol = str(reqObj["protocol"])
  sweep_start = sweep_start % 360.0 if sweep_start > 0 else sweep_start % -360
  if protocol in (CollectionProtocols.VECTOR, CollectionProtocols.STEP_VECTOR):
    beamline_lib.mvaDescriptor("omega",sweep_start)
  if (image_width == 0):
    number_of_images = range_degrees
  else:
    number_of_images = round(range_degrees/image_width)
  range_seconds = number_of_images*exposure_period
  if (daq_utils.detector_id == "EIGER-16"):  
    exposure_time = exposure_period - .00001
  else:
    exposure_time = exposure_period - .0024  
  angleStart = sweep_start
  file_prefix_minus_directory = str(fileprefix)
  try:
    file_prefix_minus_directory = file_prefix_minus_directory[file_prefix_minus_directory.rindex("/")+1:len(file_prefix_minus_directory)]
  except ValueError: 
    pass

  logger.info("collect %f degrees for %f seconds %d images exposure_period = %f exposure_time = %f" % (range_degrees,range_seconds,number_of_images,exposure_period,exposure_time))
  
  if OPHYD_COLLECTIONS[daq_utils.beamline]:
      logger.info("ophyd collections enabled")
      if (protocol == CollectionProtocols.STANDARD):
        RE(daq_macros.standard_plan_wrapped(currentRequest))
      elif (protocol == CollectionProtocols.VECTOR):
        RE(daq_macros.vector_plan_wrapped(currentRequest))
  else:  
    if (protocol in (CollectionProtocols.STANDARD, CollectionProtocols.CHARACTERIZE,
                     CollectionProtocols.EDNA_COL, CollectionProtocols.BURN):
      logger.info("vectorSync " + str(time.time()))    
      daq_macros.vectorSync()
      logger.info("zebraDaq " + str(time.time()))
    
      vector_params = daq_macros.gatherStandardVectorParams()
      logger.debug(f"vector_params: {vector_params}") 
      RE(daq_macros.standard_zebra_plan(flyer,angleStart,number_of_images,range_degrees,image_width,exposure_period,file_prefix_minus_directory,data_directory_name,file_number, vector_params, file_prefix_minus_directory))
    elif (protocol == CollectionProtocols.VECTOR):
      RE(daq_macros.vectorZebraScan(currentRequest))
    elif (protocol == CollectionProtocols.STEP_VECTOR):
      daq_macros.vectorZebraStepScan(currentRequest)
    else:
      pass
  return 


def detectorArm(angle_start,image_width,number_of_images,exposure_period,fileprefix,data_directory_name,file_number): #will need some environ info to diff eiger/pilatus
  global image_started,allow_overwrite,abort_flag

  detector_save_files()
  detector_set_username(getpass.getuser())
  detector_set_groupname(grp.getgrgid(os.getgid())[0])
  detector_set_fileperms(420)
  logger.info("data directory = " + data_directory_name)

  file_prefix_minus_directory = str(fileprefix)
  try:
    file_prefix_minus_directory = file_prefix_minus_directory[file_prefix_minus_directory.rindex("/")+1:len(file_prefix_minus_directory)]
  except ValueError: 
    pass
  detector_set_exposure_time(exposure_period)  
  detector_set_period(exposure_period) #apparently this takes care of itself for deadtime
  detector_set_numimages(number_of_images)
  detector_set_filepath(data_directory_name)
  detector_set_fileprefix(file_prefix_minus_directory)
  detector_set_filenumber(file_number)
  detector_set_fileheader(angle_start,image_width,beamline_lib.motorPosFromDescriptor("detectorDist"),daq_utils.energy2wave(beamline_lib.motorPosFromDescriptor("energy"), digits=6),0.0,exposure_period,getPvDesc("beamCenterX"),getPvDesc("beamCenterY"),"omega",angle_start,0.0,0.0) #only a few for eiger
  
  detector_start() #but you need wired or manual trigger
  startArm = time.time()
  detector_waitArmed() #don't worry about this while we're not doing hardware triggers., not quite sure what it means
  endArm = time.time()
  armTime = endArm-startArm
  logger.info("\narm time = " + str(armTime) +"\n")
  return

def checkC2C_X(x,fovx): # this is to make sure the user doesn't make too much of an x-move in C2C
  scalePixX = getPvDesc("image_X_scalePix")
  centerPixX = getPvDesc("image_Y_centerPix")
  xpos = beamline_lib.motorPosFromDescriptor("sampleX")
  target = xpos + ((x-centerPixX) * (fovx/scalePixX))
  target = target * daq_utils.unitScaling  # unitScaling multiplier used to adjust units between microns and mm
  logger.info('checkC2C_X target: %s' % target)
  xlimLow = getPvDesc("robotXMountPos") + gov_robot.dev.gx.at_SA.low.get()
  xlimHi = getPvDesc("robotXMountPos") + gov_robot.dev.gx.at_SA.high.get()
  if (target<xlimLow or target>xlimHi):
    gui_message("Click to Center out of bounds on X move. Please mount next sample.")
    return 0
  return 1
  

def center_on_click(x,y,fovx,fovy,source="screen",maglevel=0,jog=0,viewangle=daq_utils.CAMERA_ANGLE_BEAM): #maglevel=0 means lowmag, high fov, #1 = himag with digizoom option, 
  #source=screen = from screen click, otherwise from macro with full pixel dimensions
  #viewangle=daq_utils.CAMERA_ANGLE_BEAM, default camera angle is in-line with the beam

  if daq_utils.beamline == "nyx":
    logger.info("center_on_click: %s" % str((x,y)))
    lsdc_x = daq_utils.screenPixX
    lsdc_y = daq_utils.screenPixY
    md2_x = getPvDesc("md2CenterPixelX") * 2
    md2_y = getPvDesc("md2CenterPixelY") * 2
    scale_x = md2_x / lsdc_x
    scale_y = md2_y / lsdc_y
    x = x * scale_x
    y = y * scale_y
    str_coords = f'{x} {y}'
    logger.info(f'center_on_click: {str_coords}')
    setPvDesc("MD2C2C", str_coords)
    return

  if (getBlConfig('robot_online')): #so that we don't move things when robot moving?
    robotGovState = (getPvDesc("robotSaActive") or getPvDesc("humanSaActive"))
    if (not robotGovState):
      logger.error("Bad governor state, must be in SA to use C2C, aborting C2C movement")
      return
    if not (checkC2C_X(x,fovx)):
      return
  if (source == "screen"):
    gov_lib.waitGovNoSleep()
    setPvDesc("image_X_scalePix",daq_utils.screenPixX) #these are video dimensions in the gui
    setPvDesc("image_Y_scalePix",daq_utils.screenPixY)
    setPvDesc("image_X_centerPix",daq_utils.screenPixX/2)
    setPvDesc("image_Y_centerPix",daq_utils.screenPixY/2)
    setPvDesc("image_X_scaleMM",float(fovx))
    setPvDesc("image_Y_scaleMM",float(fovy))
    
  else:
    if (int(maglevel)==0): #I think hardcoded to not use maglevel anymore, replaced with more flexible fov
      setPvDesc("image_X_scalePix",daq_utils.lowMagPixX)
      setPvDesc("image_Y_scalePix",daq_utils.lowMagPixY)
      setPvDesc("image_X_centerPix",daq_utils.lowMagPixX/2)
      setPvDesc("image_Y_centerPix",daq_utils.lowMagPixY/2)
      setPvDesc("image_X_scaleMM",float(fovx))
      setPvDesc("image_Y_scaleMM",float(fovy))
      
    else:
      setPvDesc("image_X_scalePix",daq_utils.lowMagPixX)
      setPvDesc("image_Y_scalePix",daq_utils.lowMagPixY)
      setPvDesc("image_X_centerPix",daq_utils.highMagPixX/2)
      setPvDesc("image_Y_centerPix",daq_utils.highMagPixY/2)
      setPvDesc("image_X_scaleMM",float(fovx))
      setPvDesc("image_Y_scaleMM",float(fovy))

  # The following is intended to allow basic axis changes for standard off-axis camera views
  # CAMERA_ANGLE_BEAM - camera view is directly in line with beam
  # CAMERA_ANGLE_ABOVE - camera is looking down from directly above
  # CAMERA_ANGLE_BELOW - camera is looking up from directly below
  if (viewangle==daq_utils.CAMERA_ANGLE_BEAM):
    camera_view_omega_offset = 0
  elif (viewangle==daq_utils.CAMERA_ANGLE_ABOVE):
    camera_view_omega_offset = -90
  elif (viewangle==daq_utils.CAMERA_ANGLE_BELOW):
    camera_view_omega_offset = 90
  else:
    logger.error(f"blconfig 'viewangle' set to invalid value:  {viewangle}") 
  
  omega_mod = (camera_view_omega_offset + beamline_lib.motorPosFromDescriptor("omega"))%360.0
  lib_gon_center_xtal(x,y,omega_mod,0)
  if (jog):
    beamline_lib.mvrDescriptor("omega",float(jog))

def setProposalID(proposalID):
  daq_utils.setProposalID(proposalID)

def getProposalID():
  return daq_utils.getProposalID()

