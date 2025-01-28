#!/opt/conda_envs/lsdc-server-2023-2-latest/bin/ipython -i
"""
The main server for the LSDC system
"""
import sys
import os
from daq_main_common import pybass_init, run_server
from utils.healthcheck import perform_server_checks
#TODO understand why imports are required here - GUI requires imports in daq_main_common
from daq_macros import *
from daq_lib import *
from robot_lib import *
from beamline_lib import *
from gov_lib import setGovRobot
import getpass
from start_bs import robot
from embl_robot import EMBLRobot
if isinstance(robot, EMBLRobot):
    print("loading RobotControlLib")
    import RobotControlLib
else:
    print("not importing RobotControlLib")

import logging
from logging import handlers
logger = logging.getLogger()
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('ophyd').setLevel(logging.WARN)
logging.getLogger('caproto').setLevel(logging.WARN)
handler1 = handlers.RotatingFileHandler('lsdcServerLog.txt', maxBytes=5000000, backupCount=100)
myformat = logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s')
handler1.setFormatter(myformat)
logger.addHandler(handler1)

perform_server_checks()
setBlConfig("visitDirectory", os.environ.get("CURRENT_VISIT_DIR", os.getcwd()))
sitefilename = ""
global command_list,immediate_command_list,z
command_list = []
immediate_command_list = []
z = 25

def main(mode):
  pybass_init()
  if (mode=="gui"):
    run_server()
  else:
    lsdcHome = os.environ["LSDCHOME"]
    os.system(lsdcHome+"/daq_main2.py gui&")    

if (len(sys.argv)>1):
  if (sys.argv[1] == "gui"):
    main(mode="gui")
else:
  main(mode="shell")  
