from string import *
import sys

import ophyd
from ophyd import EpicsMotor
from ophyd import EpicsScaler
import time
import epics
import os
import logging
logger = logging.getLogger(__name__)


global beamline_designation,motor_dict,soft_motor_list,scan_list,counter_dict,motor_channel_dict,counter_channel_dict,number_of_counter_readouts,scanparms_channel_dict,beamline_scan_record,scan_active_pv,scan_reference_counter,scan_detector_count,datafile_name,pvChannelDict

motor_dict = {}
counter_dict = {}
pvLookupDict = {}
motor_channel_dict = {}
counter_channel_dict = {}
scanparms_channel_dict = {}
pvChannelDict = {}

scan_list = []
soft_motor_list = []

number_of_counter_readouts = 6
scan_detector_count = 4
datafile_name = ""



#I think even these next few can go away and I can use epics.PV directly
def pvCreate(pvname,connCB=None,timeout=None):
  pv = None
  pv = epics.PV(pvname,connection_timeout=timeout)
  if not (pv.wait_for_connection()):
    logger.info("\n\nCould not create PV " + pvname + "\n\n")
  return pv


def pvGet(pv):
  return pv.get()


def pvPut(pv,val):
  pv.put(val)


def pvClose(pv):
  del pv



#convenience to set a pv value given the name
def set_any_epics_pv(pv_prefix,field_name,value,wait=True): #this does not use beamline designation
  if (field_name == "VAL"):
    pvname = pv_prefix
  else:
    pvname = "%s.%s" % (pv_prefix,field_name)  
  if (pvname not in pvChannelDict):
    pvChannelDict[pvname] = epics.PV(pvname)
  if (pvChannelDict[pvname] != None):
    pvChannelDict[pvname].put(value,wait=wait)


#convenience to set a pv value given the name
def get_any_epics_pv(pv_prefix,field_name,as_string=False): #this does not use beamline designation
  if (field_name == "VAL"):
    pvname = pv_prefix
  else:
    pvname = "%s.%s" % (pv_prefix,field_name)  
  if (pvname not in pvChannelDict):
    pvChannelDict[pvname] = PVchannel = epics.PV(pvname)
  if (pvChannelDict[pvname] != None):
    pv_val = pvChannelDict[pvname].get(as_string=as_string)
  else:
    pv_val = None
  return pv_val

#initializes epics motors and counter based on the file pointed to by $EPICS_BEAMLINE_INFO
#Below this line is an example beamline info file, (remove one '#' off the front of each line)
##beamline_designation
#x12c
##real motors
#tv1 table_vert1
#tv2 table_vert2
#mon monochromator
##virtual motors
#tbv table_vert
##scanned motors
#mon
#tbv
##counters
#scaler1 main_counter
def init_beamline():
  read_db()
  init_motors()
  

#relative simultaneous move of multiple motors
#usage example: mvr mon 1.0 tv2 0.5
def mvrOld(*args):
  multimot_list = {}
  movedist_list = {}
  try:
    for i in range(0,len(args),2):
      multimot_list[i/2] = beamline_designation+args[i]
      movedist_list[i/2] = float(args[i+1])
    for i in range(0,(len(args)/2)):
      motor_channel_dict[multimot_list[i]].move(movedist_list[i],relative=1)
    for i in range(0,(len(args)/2)):
      motor_channel_dict[multimot_list[i]].wait()
  except epicsMotorException as status:
    logger.error("CAUGHT MOTOR EXCEPTION")
    try:
      ii = 0
      status_string = ""
      while(1):
        status_string = status_string + str(status[ii])
        ii = ii + 1
    except IndexError:
      logger.error(status_string)
      raise epicsMotorException(status_string)


#absolute simultaneous move of multiple motors
#usage example: mva mon 1.0 tv2 0.5
def waitMove(motor):
  time.sleep(0.1)
  while (motor.moving):
    time.sleep(0.1)

def mva(*args):
  multimot_list = {}
  movedist_list = {}
  for i in range(0,len(args),2):
    multimot_list[i/2] = beamline_designation+args[i]
    movedist_list[i/2] = float(args[i+1])
  for i in range(0,int(len(args)/2)):
    motor_channel_dict[multimot_list[i]].move(movedist_list[i],wait=False)
  for i in range(0,int(len(args)/2)):
    waitMove(motor_channel_dict[multimot_list[i]])

def mvr(*args):
  multimot_list = {}
  movedist_list = {}
  for i in range(0,len(args),2):
    multimot_list[i/2] = beamline_designation+args[i]
    movedist_list[i/2] = float(args[i+1])
  for i in range(0,int(len(args)/2)):
    curval = motor_channel_dict[multimot_list[i]].position
    newval = curval+movedist_list[i]
    motor_channel_dict[multimot_list[i]].move(newval,wait=False)
  for i in range(0,int(len(args)/2)):
    waitMove(motor_channel_dict[multimot_list[i]])



def get_motor_pos(motcode):
  return motor_channel_dict[beamline_designation+motcode].position

def stop_motors():
  for key in list(motor_channel_dict.keys()):
    motor_channel_dict[key].stop()

#count for time_to_count seconds
def do_count(time_to_count=0):
  if (time_to_count == 0):  
    counter_channel_dict[counter_dict["main_counter"]].start()
  else:
    counter_channel_dict[counter_dict["main_counter"]].start(time_to_count)
  counter_channel_dict[counter_dict["main_counter"]].wait()

def ri(): #read intensity legacy call
  do_count()
  print_counts()

def set_count_time(time_to_count):
  counter_channel_dict[counter_dict["main_counter"]].setTime(time_to_count)

def get_count_time():
  return counter_channel_dict[counter_dict["main_counter"]].getTime()

def get_counts(time_to_count=0):
  do_count(time_to_count)
  return counter_channel_dict[counter_dict["main_counter"]].read()

def get_latest_counts():
  return counter_channel_dict[counter_dict["main_counter"]].read()

def print_counts():
  count_result_list = []
  count_result_list = counter_channel_dict[counter_dict["main_counter"]].read()
  for i in range (0,number_of_counter_readouts):
    logger.info("channel %d: %d" % (i,count_result_list[i]))



#dumps motor parameters to a file. Used for creating scan file headers
def dump_mots(dump_filename):
  logger.info(("dumping to " + dump_filename))
  dump_file = open(dump_filename,'a+')
  dump_file.write("#%s\n" % time.ctime(time.time()))
  dump_file.write("#motor_code motor_name    pos speed bspd bcklsh acc bk_acc\n")
  for key in list(motor_channel_dict.keys()):
    dump_file.write("# " + key)
    dump_file.write(" " + motor_channel_dict[key].description)
    dump_file.write(" %.3f" % motor_channel_dict[key].get_position())
    dump_file.write(" %.3f" % motor_channel_dict[key].slew_speed)
    dump_file.write(" %.3f" % motor_channel_dict[key].base_speed)
    dump_file.write(" %.3f" % motor_channel_dict[key].backlash)
    dump_file.write(" %.3f" % motor_channel_dict[key].acceleration)
    dump_file.write("\n")
  dump_file.close()



def sp(motcode,posn): #sets the position w/o moving
  if (not(is_soft_motor(motcode))):
    motor_channel_dict[beamline_designation+motcode].set_position(posn)
  else:
    logger.info("Cannot set Soft Motor " + motcode)



def waveform_to_string(wave):
  s = ""
  for i in range (0,len(wave)):
    if (wave[i] == 0):
      break
    else:
      s = s + "%c" % wave[i]
  return s


#####
# most functions between here and the end of the file are mostly for internal use
####

def is_soft_motor(mcode):
  for i in range(0,len(soft_motor_list)):
    if (soft_motor_list[i] == mcode):
      return 1
    else:
      continue
  return 0
    

def read_db():
  global beamline_designation,motor_dict,soft_motor_list,scan_list,counter_dict
  
  envname = "EPICS_BEAMLINE_INFO"
  try:
    dbfilename = os.environ[envname]
  except KeyError:
    logger.error(envname + " not defined. Defaulting to epx.db.")
    dbfilename = "epx.db"
  if (os.path.exists(dbfilename) == 0):
    error_msg = "EPICS BEAMLINE INFO %s does not exist.\n Program exiting." % dbfilename
    logger.error(error_msg)
    sys.exit()
  else:
    dbfile = open(dbfilename,'r')
    line = dbfile.readline()
    line = dbfile.readline()
    beamline_designation = line[:-1]
    line = dbfile.readline()
    i = 0
    while(1):
      line = dbfile.readline()
      if (line == ""):
        break
      else:
        line = line[:-1]
        if (line == "#virtual motors"):
          break
        else:
          motor_inf = line.split()
          motor_dict[motor_inf[1]] = beamline_designation +  motor_inf[0]
    while(1):
      line = dbfile.readline()
      if (line == ""):
        break
      else:
        line = line[:-1]
        if (line == "#control PVs"):
          break
        else:
          motor_inf = line.split()
          soft_motor_list.append(beamline_designation + motor_inf[0])
          motor_dict[motor_inf[1]] = beamline_designation + motor_inf[0]          
    while(1):
      line = dbfile.readline()
      if (line == ""):
        break
      else:
        line = line[:-1]
        if (line == "#scanned motors"):
          break
        else:
          inf = line.split()
          pvLookupDict[inf[1]] = beamline_designation + inf[0]          
    while(1):
      line = dbfile.readline()
      if (line == ""):
        break
      else:
        line = line[:-1]
        if (line == "#counters"):
          break
        else:
          scan_list.append(beamline_designation + line + "scanParms")
    line = dbfile.readline()
    counter_inf = line.split()
    counter_dict[counter_inf[1]] = beamline_designation + counter_inf[0]    



def init_motors():
  global motor_channel_dict
  md2_motors = ["omega","sampleX","sampleY","sampleZ", "finex", "finey", "finez"]

  for key in list(motor_dict.keys()):
    if beamline_designation == "XF:19ID" and key in md2_motors:
      from mxbluesky.devices.md2 import MD2Positioner
      motor_channel_dict[motor_dict[key]] = MD2Positioner(motor_dict[key],name = key)
    else:
      motor_channel_dict[motor_dict[key]] = EpicsMotor(motor_dict[key],name = key)


def initControlPVs():
  global pvChannelDict

  for key in list(pvLookupDict.keys()):
    pvChannelDict[pvLookupDict[key]] = epics.PV(pvLookupDict[key])

      

def init_counters():
  global counter_channel_dict

  for key in list(counter_dict.keys()):
    counter_channel_dict[counter_dict[key]] = EpicsScaler(counter_dict[key])



def get_short_motor_code(beamline_desginated_code): # return motor code minus beamline designation
  i = beamline_desginated_code.find(beamline_designation)
  if (i>-1):
    return beamline_desginated_code[len(beamline_designation):len(beamline_desginated_code)]
  else:
    return beamline_desginated_code


def pvNameSuffix_from_descriptor(descriptor): # for example - {Gon:1-Ax:O}Mtr = pvNameSuffix_from_descriptor("omega")
  return get_short_motor_code(motor_code_from_descriptor(descriptor))

def motor_code_from_descriptor(descriptor):
  return motor_dict[descriptor]

def pvNameFromDescriptor(descriptor): 
  return pvLookupDict[descriptor]

def getPvValFromDescriptor(descriptor,as_string=False):
  return get_any_epics_pv(pvNameFromDescriptor(descriptor),"VAL",as_string=as_string)

def setPvValFromDescriptor(descriptor,setval,wait=True):
  set_any_epics_pv(pvNameFromDescriptor(descriptor),"VAL",setval,wait)
  

  
