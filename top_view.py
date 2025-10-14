from daq_utils import setBlConfig, getBlConfig
import daq_lib
import beamline_lib
import time
from beamline_support import getPvValFromDescriptor as getPvDesc, setPvValFromDescriptor as setPvDesc
import os
import filecmp
import logging
import subprocess
from config_params import TOP_VIEW_CHECK

logger = logging.getLogger(__name__)

def wait90TopviewThread(gov_robot, prefix1,prefix90):
  startTime = time.time()
  if (getPvDesc("gripTemp")>-170):
    threadTimeout = 130.0
  else:
    threadTimeout = 30.0    
  while (1):
    omegaCP = beamline_lib.motorPosFromDescriptor("omega")
    if (omegaCP > 89.5 and omegaCP < 90.5):
      logger.info("leaving topview thread for 90")      
      break
    if (time.time()-startTime > threadTimeout):
      logger.info("leaving topview thread for " + str(threadTimeout))
      setPvDesc("topViewTrigMode",0)    
      setPvDesc("topViewImMode",2)
      setPvDesc("topViewDataType",1)
      setPvDesc("topViewAcquire",1,wait=False)    
      return
    time.sleep(0.10)
  try:
    topViewWrite()
    topViewSnap(prefix90,getBlConfig("visitDirectory")+"/pinAlign",1)
    snapshot1Name = prefix1+"_001.jpg"
    snapshot2Name = prefix90+"_001.jpg"
    if (not filecmp.cmp(getBlConfig("visitDirectory")+"/pinAlign/"+snapshot1Name,getBlConfig("visitDirectory")+"/pinAlign/"+snapshot2Name)): #this would mean something is wrong if true because the pictures are identical
      comm_s = [os.environ["LSDCHOME"] + "/runPinAlign.py", snapshot1Name, snapshot2Name]
      logger.info(comm_s)
      process = subprocess.run(comm_s, cwd=getBlConfig("visitDirectory"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      lines = process.stdout.decode().strip().split('\n')
      logger.info("printing lines right after popen ")
      logger.info(lines)
      logger.info(" done")
      if (lines[0].find("CANNOT CENTER") == -1):
        offsetTokens = lines[0].split()
        logger.info(offsetTokens[0] + " " + offsetTokens[1] + " " + offsetTokens[2])
        xlimLow = getPvDesc("robotXMountPos") + gov_robot.dev.gx.at_SA.low.get()
        xlimHi = getPvDesc("robotXMountPos") + gov_robot.dev.gx.at_SA.high.get()
        xpos = beamline_lib.motorPosFromDescriptor("sampleX")          
        target = xpos + float(offsetTokens[0])*1000.0
        if (target<xlimLow or target>xlimHi):
          logger.info("Pin X move beyond limit - Mount next sample.")
##else it thinks it worked              return 0
        else:
          sampXadjust = 1000.0*float(offsetTokens[0])
          sampYadjust = 1000.0*float(offsetTokens[1])
          setBlConfig('sampYAdjust', sampYadjust)
          sampZadjust = 1000.0*float(offsetTokens[2])
          sampXCP = beamline_lib.motorPosFromDescriptor("sampleX")
          sampYCP = beamline_lib.motorPosFromDescriptor("sampleY")
          sampZCP = beamline_lib.motorPosFromDescriptor("sampleZ")
          sampXAbsolute = sampXCP+sampXadjust          
          sampYAbsolute = sampYCP+sampYadjust          
          sampZAbsolute = sampZCP+sampZadjust
          setPvDesc("robotXWorkPos",sampXAbsolute)
          setPvDesc("robotYWorkPos",sampYAbsolute)
          setPvDesc("robotZWorkPos",sampZAbsolute)          
      else:
        logger.info("Cannot align pin - Mount next sample.")
#else it thinks it worked            return 0
      for outputline in lines:
        logger.info(outputline)
  except Exception as e:
    e_s = str(e)
    message = "TopView check ERROR, will continue: " + e_s
    daq_lib.gui_message(message)
    logger.error(message)

def topViewSnap(filePrefix,data_directory_name,file_number_start,acquire=1): #if we don't need to stream, then this requires few steps
  os.system("mkdir -p " + data_directory_name)
  os.system("chmod 777 " + data_directory_name)
  setPvDesc("topViewAcquire",0,wait=False)
  time.sleep(1.0) #this sleep definitely needed
  setPvDesc("topViewTrigMode",5)
  setPvDesc("topViewImMode",0)
  setPvDesc("topViewDataType",0)
  setPvDesc("topViewJpegFilePath",data_directory_name)
  setPvDesc("topViewJpegFileName",filePrefix)
  setPvDesc("topViewJpegFileNumber",file_number_start)
  if (acquire):
    setPvDesc("topViewAcquire",1)
    setPvDesc("topViewWriteFile",1)
    setPvDesc("topViewTrigMode",0)
    setPvDesc("topViewImMode",2)
    setPvDesc("topViewDataType",1)
    setPvDesc("topViewAcquire",1,wait=False)

def topViewWrite():
  setPvDesc("topViewWriteFile",1)
  setPvDesc("topViewTrigMode",0)
  setPvDesc("topViewImMode",2)
  setPvDesc("topViewDataType",1)

def topViewCheckOn():
  setBlConfig(TOP_VIEW_CHECK,1)

def topViewCheckOff():
  setBlConfig(TOP_VIEW_CHECK,0)
