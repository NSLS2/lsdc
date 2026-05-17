#### !/opt/conda_envs/lsdc-server-2023-2-latest/bin/ipython -i
"""
The server run when lsdcRemote is used
"""
import os
from daq_macros import *
import daq_lib
from daq_lib import *
from robot_lib import *
from beamline_lib import *
from gov_lib import setGovRobot
import atexit
from daq_main_common import pybass_init
import logging
from logging import handlers
from start_bs import robot
from embl_robot import EMBLRobot
if isinstance(robot, EMBLRobot):
    print("loading RobotControlLib")
    import RobotControlLib
else:
    print("not importing RobotControlLib")

logger = logging.getLogger()
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('ophyd').setLevel(logging.WARN)
logging.getLogger('caproto').setLevel(logging.WARN)
handler1 = handlers.RotatingFileHandler('lsdcServerLog.txt', maxBytes=5000000, backupCount=100)
handler2 = handlers.RotatingFileHandler('/var/log/dama/%slsdcServerLog.txt' % os.environ['BEAMLINE_ID'], maxBytes=5000000, backupCount=100)
myformat = logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s')
handler1.setFormatter(myformat)
handler2.setFormatter(myformat)
logger.addHandler(handler1)
logger.addHandler(handler2)

# Add stream handlers to output in the terminal
console_handler = logging.StreamHandler()  # or just StreamHandler()
console_handler.setFormatter(myformat)

logger.addHandler(console_handler)

sitefilename = ""
global command_list,immediate_command_list,z
command_list = []
immediate_command_list = []
z = 25

pybass_init()

