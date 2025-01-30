#!/opt/conda_envs/lsdc-server-2023-2-latest/bin/python
import os
import sys
import db_lib
import time
from daq_utils import getBlConfig
import xmltodict
import logging
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

comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}fast_dp.sh {request_id} {numstart}\""
logger.info(comm_s)
os.system(comm_s)
fastDPResultFile = runningDir + "/fast_dp.xml"
for attempt in range(3):
  try:
    with open(fastDPResultFile) as fd:
      resultObj = xmltodict.parse(fd.read())
    break
  except FileNotFoundError as e:
    if attempt < 2:
      logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in 5 seconds...")
      time.sleep(5)
    else:
      logger.error(f"Failed to open {fastDPResultFile} after 3 attempts: {e}")
      raise

logger.info(f"finished fast_dp {request_id}")
resultID = db_lib.addResultforRequest("fastDP", request_id, owner, resultObj, beamline=os.environ["BEAMLINE_ID"])
newResult = db_lib.getResult(resultID)
visitName = getBlConfig("visitName")
try:
  ispybLib.insertResult(newResult,"fastDP",request,visitName,ispybDCID,fastDPResultFile)
except Exception as e:
  logger.error("runfastdph5 insert result ispyb error: %s" % e)
if (runFastEP):
  os.system("fast_ep") #looks very bad! running on ca1!
if (runDimple):
  dimpleComm = getBlConfig("dimpleComm")
  comm_s = f"ssh -q {dimpleNode} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}dimple.sh {request_id} {numstart}\""  
  logger.info(f"running dimple: {comm_s}")
  os.system(comm_s)
