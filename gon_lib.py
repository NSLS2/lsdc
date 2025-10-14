import time
import beamline_lib
import beamline_support
from beamline_support import getPvValFromDescriptor as getPvDesc, setPvValFromDescriptor as setPvDesc
import logging
import daq_utils
if daq_utils.beamline == 'nyx':
  from start_bs import back_light, back_light_range, md2
logger = logging.getLogger(__name__)
BACK_LIGHT_STEP = 0.05 # percent of intensity range

def omegaMoveAbs(angle):
  md2.omega.set(angle)

def omegaMoveRel(angle):
  md2.omega.set(md2.omega.get() + angle)

def backlightBrighter():
  intensity = back_light.get()
  intensity += BACK_LIGHT_STEP * (back_light_range[1]-back_light_range[0])
  back_light.put(intensity)  

def backlightDimmer():
  intensity = back_light.get()
  intensity -= BACK_LIGHT_STEP * (back_light_range[1]-back_light_range[0])
  back_light.put(intensity)
  
def lib_init_diffractometer():
  beamline_support.initControlPVs()


def lib_gon_center_xtal(x,y,angle_omega,angle_phi):
  setPvDesc("C2C_TargetX",float(x))
  setPvDesc("C2C_TargetY",float(y))
  setPvDesc("C2C_Omega",angle_omega)  
  setPvDesc("C2C_Go",1)  
  wait_for_goniohead()
  
def lib_open_shutter():
  beamline_lib.mvaDescriptor("fastShutter",getPvDesc("fastShutterOpenPos"))    


def lib_close_shutter():
  beamline_lib.mvaDescriptor("fastShutter",getPvDesc("fastShutterClosePos"))



def lib_home():
  pass


def lib_home_omega():
  pass



def lib_home_dist():
  pass #for now


def gon_stop():
  logger.info("setting osc abort")
  setPvDesc("vectorAbort",1)


def oscWait():
  time.sleep(0.15)
  while (getPvDesc("oscRunning")):
    time.sleep(0.05)
  

def gon_osc(angle_start,width,exptime):

  angle_end = angle_start+width
  setPvDesc("oscOmegaStart",angle_start)
  setPvDesc("oscOmegaEnd",angle_end)
  setPvDesc("oscDuration",exptime)
  setPvDesc("oscGo",1)
  oscWait()
  end_osc = beamline_lib.motorPosFromDescriptor("omega")
  logger.info("end_osc in gon_osc = " + str(end_osc) + "\n")
  return end_osc


def wait_for_goniohead(): #why can't I just call wait_motors????
  while (1):
    try:
      done_stat = getPvDesc("gonioDone")
      if (done_stat != 0):
        break
      else:
        time.sleep(.2)
        pass      
    except KeyboardInterrupt:
      pass
    except CaChannelException as status:
      logger.error(ca.message(status))
      logger.error("\n\nHandled Epics Error in wait for motors-2\n\n")
      continue
  
  
