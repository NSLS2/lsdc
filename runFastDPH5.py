#!/opt/conda_envs/lsdc-server-2023-2-latest/bin/python
import os
import sys
import db_lib
from daq_utils import getBlConfig, setBlConfig
import xmltodict
import json
import logging
import subprocess
logger = logging.getLogger()
logging.getLogger().setLevel(logging.INFO)
handler1 = logging.FileHandler('fast_dp.txt')
myformat = logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s')
handler1.setFormatter(myformat)
logger.addHandler(handler1)

try:
  import ispybLib
except Exception as e:
  logger.error("runFastDPH5: ISPYB import error, %s" % e)

baseDirectory = os.environ["PWD"]
directory = sys.argv[1]
runningDir = directory+"/fastDPOutput"
comm_s = "mkdir -p " + runningDir
os.system(comm_s)
os.chdir(runningDir) #maybe not needed
numstart = int(float(sys.argv[2]))
request_id = sys.argv[3]
request=db_lib.getRequestByID(request_id) #add another argument false to allow finished requests to be retrieved for testing
owner=request["owner"]
runFastEP = int(sys.argv[4])
node = sys.argv[5]
runDimple = int(sys.argv[6])
dimpleNode = sys.argv[7]
ispybDCID = 1 #int(sys.argv[8])
runAutoProc = int(sys.argv[9])
# runAutoProc = 0

try:
  comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}fast_dp.sh {request_id} {numstart}\""
  logger.info(comm_s)
  os.system(comm_s)
  fastDPResultFile = runningDir+"/fast_dp.xml"
  fd = open(fastDPResultFile)
  resultObj = xmltodict.parse(fd.read())
  logger.info(f"finished fast_dp {request_id}")
  resultID = db_lib.addResultforRequest("fastDP",request_id,owner,resultObj,beamline=os.environ["BEAMLINE_ID"])
  newResult = db_lib.getResult(resultID)
  visitName = getBlConfig("visitName")
except Exception as e:
  logger.error("runfastdph5 error running fastdp: %s" % e)

try:
  ispybLib.insertResult(newResult,"fastDP",request,visitName,ispybDCID,fastDPResultFile)
except Exception as e:
  logger.error("runfastdph5 insert result ispyb error: %s" % e)

if (runFastEP):
  os.system("fast_ep") #looks very bad! running on ca1!

if (runDimple):
  try:
    dimpleComm = getBlConfig("dimpleComm")
    comm_s = f"ssh -q {dimpleNode} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}dimple.sh {request_id} {numstart}\""  
    logger.info(f"running dimple: {comm_s}")
    # os.system(comm_s)
    subprocess.Popen(comm_s, shell=True)
  except Exception as e:
    logger.error("runfastdph5 error running dimple: %s" % e)
    
if runAutoProc:
  logger.info("Running AUTO-AUTOPROC...")
  setBlConfig("auto_proc_lock", True)
  try:
    queue = getBlConfig("auto_proc_queue")
    queue.append((directory, request_id))
    setBlConfig("auto_proc_queue", queue)
  except Exception as e:
    logger.exception("Could not add request to autoproc queue")
  finally:
    setBlConfig("auto_proc_lock", False)
  start_in_proc = None
  autoproc_processor_list = json.loads(getBlConfig("autoprocNodes"))
  for proc_num in autoproc_processor_list:
    if not getBlConfig(proc_num):
      start_in_proc = proc_num
      break
  if start_in_proc:
    comm_s = f"ssh {start_in_proc} \"nohup {os.environ['MXPROCESSINGSCRIPTSDIR']}autoproc.sh {start_in_proc} {os.environ['BEAMLINE_ID']} & \" "
    logger.info(f"Initializing AUTO-AUTOPROC {comm_s} \n In ({directory}, {request_id})")
    subprocess.Popen(comm_s, shell=True)
