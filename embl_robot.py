import RobotControlLib
import daq_utils
import db_lib
from daq_utils import getBlConfig, setBlConfig
import daq_lib
import beamline_lib
import time
import daq_macros
import beamline_support
from beamline_support import getPvValFromDescriptor as getPvDesc, setPvValFromDescriptor as setPvDesc
import os
import sys
import traceback
import _thread
from threading import Thread
import logging
import epics.ca
import top_view
from config_params import TOP_VIEW_CHECK, DETECTOR_SAFE_DISTANCE, MOUNT_SUCCESSFUL, MOUNT_FAILURE,\
                          MOUNT_UNRECOVERABLE_ERROR, MOUNT_STEP_SUCCESSFUL, UNMOUNT_SUCCESSFUL,\
                          UNMOUNT_FAILURE, UNMOUNT_STEP_SUCCESSFUL, PINS_PER_PUCK, EMBL_SERVER_PV_BASE
import gov_lib
#from start_bs import gov_human, gov_robot
logger = logging.getLogger(__name__)

global retryMountCount
retryMountCount = 0

setBlConfig('sampYAdjust', 0)

def setWorkposThread(init,junk):
  logger.info("setting work pos in thread")
  setPvDesc("robotGovActive",1)
  setPvDesc("robotXWorkPos",getPvDesc("robotXMountPos"))
  setPvDesc("robotYWorkPos",getPvDesc("robotYMountPos"))
  setPvDesc("robotZWorkPos",getPvDesc("robotZMountPos"))
  setPvDesc("robotOmegaWorkPos",90.0)
  if (init):
    time.sleep(20)
    setPvDesc("robotGovActive",0)

class EMBLRobot:


    def __init__(self):
        self.workposThread = None


    def control_type(self):
        return "DIRECT"

    def finish(self):
      if (getBlConfig('robot_online')):
        try:
          RobotControlLib.runCmd("finish")
          return MOUNT_SUCCESSFUL
        except Exception as e:
          e_s = str(e)
          message = "ROBOT Finish ERROR: " + e_s
          daq_lib.gui_message(message)
          logger.error(message)
          return MOUNT_FAILURE

    def warmupGripperRecoverThread(self, savedThreshold,junk):
      time.sleep(120.0)
      setPvDesc("warmupThreshold",savedThreshold)


    def recoverRobot(self):
      try:
        self.rebootEMBL()
        time.sleep(8.0)
        _,bLoaded,_ = RobotControlLib.recover()
        if bLoaded:
          daq_macros.robotOff()
          daq_macros.disableMount()
          daq_lib.gui_message("Found a sample in the gripper - CALL STAFF! disableMount() executed.")
        else:
          RobotControlLib.runCmd("goHome")
      except Exception as e:
        e_s = str(e)
        daq_lib.gui_message("ROBOT Recover failed! " + e_s)


    def dryGripper(self):
      try:
        saveThreshold = getPvDesc("warmupThresholdRBV")
        setPvDesc("warmupThreshold",50)
        _thread.start_new_thread(self.warmupGripperRecoverThread,(saveThreshold,0))
        self.warmupGripperForDry()
      except Exception as e:
        e_s = str(e)
        daq_lib.gui_message("Dry gripper failed! " + e_s)
        setPvDesc("warmupThreshold",saveThreshold)

    def DewarAutoFillOn(self):
      RobotControlLib.runCmd("turnOnAutoFill")

    def DewarAutoFillOff(self):
      RobotControlLib.runCmd("turnOffAutoFill")

    def DewarHeaterOn(self):
      RobotControlLib.runCmd("dewarHeaterOn")

    def DewarHeaterOff(self):
      RobotControlLib.runCmd("dewarHeaterOff")

  
    def warmupGripper(self):
      try:
        RobotControlLib.runCmd("warmupGripper")
        daq_lib.mountCounter = 0
      except:
        daq_lib.gui_message("ROBOT warmup failed!")

    def warmupGripperForDry(self):

        RobotControlLib.runCmd("warmupGripper")
        daq_lib.mountCounter = 0



    def enableDewarTscreen(self):
      RobotControlLib.runCmd("enableTScreen")

    def openPort(self, portNo):
      RobotControlLib.openPort(int(portNo))

    def closePorts(self):
      RobotControlLib.runCmd("closePorts")

    def rebootEMBL(self):
      try:
        RobotControlLib.rebootEMBL()
      except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type == epics.ca.ChannelAccessGetFailure and str(exc_value) == "Get failed; status code: 192":
          logger.info('channel access failure detected but error 192 is expected, so continuing')
        else:
          # channel access exception with error 192 seems "normal". only raise for other exceptions
          logger.error('rebootEMBL exception: %s' % traceback.format_exception(exc_type, exc_value, exc_tb))
          raise(e)


    def cooldownGripper(self):
      try:
        RobotControlLib.runCmd("cooldownGripper")
      except:
        daq_lib.gui_message("ROBOT cooldown failed!")


    def parkGripper(self):
      try:
        RobotControlLib.runCmd("park")
      except Exception as e:
        e_s = str(e)
        message = "Park gripper Failed!: " + e_s
        daq_lib.gui_message(message)
        logger.error(message)


    def testRobot(self):
      try:
        RobotControlLib.testRobot()
        logger.info("Test Robot passed!")
        daq_lib.gui_message("Test Robot passed!")
      except Exception as e:
        e_s = str(e)
        message = "Test Robot failed!: " + e_s
        daq_lib.gui_message(message)
        logger.error(message)


    def multiSampleGripper(self):
      return False

    def openGripper(self):
      RobotControlLib.openGripper()


    def closeGripper(self):
      RobotControlLib.closeGripper()


    # pin alignment, then dewar alignment done here
    def preMount(self, gov_robot, puckPos, pinPos, sampID, **kwargs):
      init = kwargs.get("init", 0)
      if (getBlConfig('robot_online')):
        desired_gov_state = 'SE'
        if kwargs.get('govStatus', None):
          gov_lib.waitGov(kwargs['govStatus'])
        if not kwargs.get('govStatus', None) or not kwargs['govStatus'].success:  # TODO check that we are at desired_gov_state
          gov_return = gov_lib.setGovRobot(gov_robot, desired_gov_state)
          if not gov_return.success:
            logger.error(f'Did not reach {desired_gov_state}')
            return MOUNT_FAILURE, kwargs
        if (getBlConfig(TOP_VIEW_CHECK) == 1):
          try:
            if (daq_utils.beamline == "fmx"):
              self.workposThread = Thread(target=setWorkposThread,args=(init,0))
              self.workposThread.start()

            sample = db_lib.getSampleByID(sampID)
            sampName = sample['name']
            reqCount = sample['request_count']
            prefix1 = sampName + "_" + str(puckPos) + "_" + str(pinPos) + "_" + str(reqCount) + "_PA_0"
            prefix90 = sampName + "_" + str(puckPos) + "_" + str(pinPos) + "_" + str(reqCount) + "_PA_90"
            kwargs['prefix1'] = prefix1
            kwargs['prefix90'] = prefix90
            if daq_utils.beamline == "fmx":
              top_view.topViewSnap(prefix1,getBlConfig("visitDirectory")+"/pinAlign",1,acquire=0)
          except Exception as e:
            e_s = str(e)
            message = "TopView check ERROR, will continue: " + e_s
            daq_lib.gui_message(message)
            logger.error(message)
        logger.info("mounting " + str(puckPos) + " " + str(pinPos) + " " + str(sampID))
        platePos = int(puckPos/3)
        rotMotTarget = daq_utils.dewarPlateMap[platePos][0]
        rotCP = daq_macros.dewar.rotation.get()
        logger.info("dewar target,CP")
        logger.info("%s %s" % (rotMotTarget,rotCP))
        if (abs(rotMotTarget-rotCP)>0.01):
          logger.info("rot dewar")
          try:
            if (init == 0):
              RobotControlLib.runCmd("park")
          except Exception as e:
            e_s = str(e)
            message = "ROBOT Park ERROR: " + e_s
            daq_lib.gui_message(message)
            logger.error(message)
            return MOUNT_FAILURE, kwargs
          daq_macros.dewar.rotate(rotMotTarget)
      return MOUNT_STEP_SUCCESSFUL, kwargs


    def callAlignPinThread(self, gov_robot, **kwargs):
      if (getBlConfig(TOP_VIEW_CHECK) == 1):
        prefix1 = kwargs['prefix1']
        prefix90 = kwargs['prefix90']
        omegaCP = beamline_lib.motorPosFromDescriptor("omega")
        if (omegaCP > 89.5 and omegaCP < 90.5):
          beamline_lib.mvrDescriptor("omega", 85.0)
        logger.info("calling thread")
        if daq_utils.beamline == "fmx":
          _thread.start_new_thread(top_view.wait90TopviewThread,(gov_robot, prefix1,prefix90))
        logger.info("called thread")


    def mount(self, gov_robot, puckPos,pinPos,sampID,**kwargs):
      global retryMountCount
      init = kwargs.get("init", 0)
      warmup = kwargs.get("warmup", 0)

      absPos = (PINS_PER_PUCK*(puckPos%3))+pinPos+1
      logger.info("absPos = " + str(absPos))
      if getBlConfig('robot_online'):
        try:
          if (init):
            setPvDesc("boostSelect",0)
            if (getPvDesc("sampleDetected") == 0): #reverse logic, 0 = true
              setPvDesc("boostSelect",1)
            else:
              robotStatus = beamline_support.get_any_epics_pv(f"{EMBL_SERVER_PV_BASE.get(daq_utils.beamline, 'SW')}:RobotState","VAL")
              if (robotStatus != "Ready"):
                gov_status = gov_lib.setGovRobot(gov_robot, 'SE')
                if not gov_status.success:
                  return MOUNT_FAILURE
            self.callAlignPinThread(gov_robot, **kwargs)
            setPvDesc("boostSelect",0)
            if (getPvDesc("gripTemp")>-170):
              try:
                RobotControlLib.mount(absPos)
              except Exception as e:
                e_s = str(e)
                message = "ROBOT mount ERROR: " + e_s
                if "Load ABORT with exception Timeout" in e_s:
                  daq_macros.run_robot_recovery_procedure()
                  try:
                    RobotControlLib.mount(absPos)
                  except Exception as e:
                    e_s = str(e)
                    message = "ROBOT mount ERROR: " + e_s                    
                    daq_lib.gui_message(message)
                    logger.error(message)
                    return MOUNT_FAILURE
                else:
                  daq_lib.gui_message(message)
                  logger.error(message)
                  return MOUNT_FAILURE
            else:
              time.sleep(0.5)
              if (getPvDesc("sampleDetected") == 0):
                logger.info("full mount")
                RobotControlLib.mount(absPos)
              else:
                RobotControlLib.initialize()
                RobotControlLib._mount(absPos)
            setPvDesc("boostSelect",1)
          else:
            self.callAlignPinThread(gov_robot, **kwargs)
            if (warmup):
              RobotControlLib._mount(absPos,warmup=True)
            else:
              RobotControlLib._mount(absPos)
        except Exception as e:
          # the following errors in the exception are from RobotControlMerge
          logger.error(e)
          e_s = str(e)
          if (e_s.find("Fatal") != -1):
            if self.isSampleDetected(e_s):
              return MOUNT_STEP_SUCCESSFUL
            daq_macros.robotOff()
            daq_macros.disableMount()
            daq_lib.gui_message(e_s + ". FATAL ROBOT ERROR - CALL STAFF! robotOff() executed.")
            return MOUNT_FAILURE
          if (e_s.find("tilted") != -1 or e_s.find("Load Sample Failed") != -1 or e_s.find("Fail to calculate Pin Position") != -1):
            if (getBlConfig("queueCollect") == 0):
              daq_lib.gui_message(e_s + ". Try mounting again")
              return MOUNT_FAILURE
            else:
              if (retryMountCount == 0):
                retryMountCount+=1
                if e_s.find("Fail to calculate Pin Position") != -1:
                  # This error happens when the dewar has not rotated to the correct position
                  # If it happens, try running the premount again
                  logger.info('Trying premount')
                  self.preMount(gov_robot, puckPos, pinPos, sampID, init=1)
                mountStat = self.mount(gov_robot, puckPos,pinPos,sampID, **kwargs)
                if (mountStat == MOUNT_STEP_SUCCESSFUL):
                  retryMountCount = 0
                return mountStat
              else:
                retryMountCount = 0
                daq_lib.gui_message("ROBOT: Could not recover from " + e_s)
                return MOUNT_UNRECOVERABLE_ERROR
          daq_lib.gui_message("ROBOT mount ERROR: " + e_s)
          return MOUNT_FAILURE
      return MOUNT_STEP_SUCCESSFUL

    def isSampleDetected(self, error_string, max_wait_time=60):
      """Sometimes after mount, the pin is not detected on the gonio because
      there is a buildup of ice between the pin and gonio
      This function checks for that error, and if it is detected will check for
      the pin every second for max_wait_time seconds.
      If after that time it still does not detect the sample it will throw an error
      """
      
      if (error_string.find("Pin lost during mount transaction") != -1):
        logger.info(f"Pin probably has ice, waiting for {max_wait_time + 1} seconds")
        wait_time = 0
        while wait_time < max_wait_time:
          wait_time += 1
          time.sleep(1)
          if getPvDesc("sampleDetected") == 0:
            # Sample is detected
            return True
      return False
  
    def postMount(self, gov_robot, puck, pinPos, sampID):
      sampYadjust = float(getBlConfig('sampYAdjust'))
      if getBlConfig('robot_online'):
        if (getBlConfig(TOP_VIEW_CHECK) == 1):
          if daq_utils.beamline == "fmx":
            try: #make sure workposThread is finished before proceeding to robotGovActive check
              timeout = 20
              start_time = time.time()
              while self.workposThread.isAlive():
                time.sleep(0.5)
                if time.time() - start_time > timeout:
                  raise Exception(f'setWorkposThread failed to finish before {timeout}s timeout')
              logger.info(f'Time waiting for workposThread: {time.time() - start_time}s')
            except Exception as e:
              daq_lib.gui_message(e)
              logger.error(e)
              return MOUNT_FAILURE
            if getPvDesc('robotGovActive') == 0: #HACK, if FMX and top view, if stuck in robot inactive
                                             #(due to setWorkposThread),
              logger.info('FMX, top view active, and robot stuck in inactive - restoring to active')
              setPvDesc('robotGovActive', 1) #set it active
            else:
              logger.info('not changing anything as governor is active')
          if (sampYadjust == 0):
            logger.info("Cannot align pin - Mount next sample.")
        if daq_utils.beamline == "amx":
          try:
            daq_macros.run_top_view_optimized()
          except:
            logger.exception("Error running top_view_optimized")
        if gov_robot.state.get() != "SA":
          gov_status = gov_lib.setGovRobot(gov_robot, 'SA')
          if not gov_status.success:
            logger.error('Failure during governor change to SA')
      return MOUNT_SUCCESSFUL

 
    def preUnmount(self, gov_robot, puckPos,pinPos,sampID): #will somehow know where it came from
      absPos = (PINS_PER_PUCK*(puckPos%3))+pinPos+1
      robotOnline = getBlConfig('robot_online')
      logger.info("robot online = " + str(robotOnline))
      if (robotOnline):
        logger.info("Checking detector dist")
        detDist = beamline_lib.motorPosFromDescriptor("detectorDist")
        if (detDist<DETECTOR_SAFE_DISTANCE[daq_utils.beamline]):
          gov_lib.set_detz_out(gov_robot, DETECTOR_SAFE_DISTANCE[daq_utils.beamline])
        if daq_utils.beamline == "fmx":
            beamline_lib.mvaDescriptor("omega", 0)
        logger.info("Setting SE state")
        if daq_utils.beamline == "amx":
          wait = False
        else:
          wait = True
        gov_lib.setGovRobot(gov_robot, "SE")
        logger.info("Done setting SE")
        logger.info("unmounting " + str(puckPos) + " " + str(pinPos) + " " + str(sampID))
        logger.info("absPos = " + str(absPos))
        platePos = int(puckPos/3)
        rotMotTarget = daq_utils.dewarPlateMap[platePos][0]
        rotCP = daq_macros.dewar.rotation.get()
        logger.info("dewar target,CP")
        logger.info("%s %s" % (rotMotTarget,rotCP))
        if (abs(rotMotTarget-rotCP)>1):
          logger.info("rot dewar")
          try:
            RobotControlLib.runCmd("park")
          except Exception as e:
            e_s = str(e)
            message = "ROBOT park ERROR: " + e_s
            daq_lib.gui_message(message)
            logger.error(message)
            return UNMOUNT_FAILURE
          daq_macros.dewar.rotate(rotMotTarget)
        try:
          par_init=(beamline_support.get_any_epics_pv("SW:RobotState","VAL")!="Ready")
          par_cool=(getPvDesc("gripTemp")>-170)
          RobotControlLib.unmount1(init=par_init,cooldown=par_cool)
        except Exception as e:
          e_s = str(e)
          message = "ROBOT unmount ERROR: " + e_s
          daq_lib.gui_message(message)
          logger.error(message)
          return UNMOUNT_FAILURE
        detDist = beamline_lib.motorPosFromDescriptor("detectorDist")
        if (detDist<DETECTOR_SAFE_DISTANCE[daq_utils.beamline]):
          beamline_lib.mvaDescriptor("detectorDist",DETECTOR_SAFE_DISTANCE[daq_utils.beamline])
        if (beamline_lib.motorPosFromDescriptor("detectorDist") < (DETECTOR_SAFE_DISTANCE[daq_utils.beamline] - 1.0)):
          logger.error(f"ERROR - Detector < {DETECTOR_SAFE_DISTANCE[daq_utils.beamline]}")
          return UNMOUNT_FAILURE
      return UNMOUNT_STEP_SUCCESSFUL

    def unmount(self, gov_robot, puckPos, pinPos, sampID):
        absPos = (PINS_PER_PUCK*(puckPos%3))+pinPos+1
        if getBlConfig('robot_online'):
          try:
            logger.info("Unmounting sample")
            RobotControlLib.unmount2(absPos)
          except Exception as e:
            e_s = str(e)
            if (e_s.find("Fatal") != -1):
              daq_macros.robotOff()
              daq_macros.disableMount()
              daq_lib.gui_message(e_s + ". FATAL ROBOT ERROR - CALL STAFF! robotOff() executed.")
              return UNMOUNT_FAILURE
            elif "SE" in e_s:
              # In case there is an SE Timeout error, run the recovery procedure
              daq_macros.run_robot_recovery_procedure()
              try:
                # Try to unmount again
                RobotControlLib.unmount2(absPos)
              except Exception as e:
                # If there is an exception again, return UNMOUNT_FAILURE
                daq_macros.run_robot_recovery_procedure()
                message = f"ROBOT unmount2 ERROR: {e}"
                daq_lib.gui_message(message)
                logger.error(message)
                return UNMOUNT_FAILURE
            else:
              message = "ROBOT unmount2 ERROR: " + e_s
              daq_lib.gui_message(message)
              logger.error(message)
              return UNMOUNT_FAILURE
          gov_status = gov_lib.setGovRobot(gov_robot, 'SE')
          if not gov_status.success:
            daq_lib.clearMountedSample()
            logger.info("could not go to SE")
            return UNMOUNT_FAILURE
        return UNMOUNT_SUCCESSFUL
