import pandas
from pandas.errors import EmptyDataError
import db_lib
from daq_lib import refreshGuiTree
import sanitize_sheet
import logging
logger = logging.getLogger(__name__)

def parseSpreadsheet(infilename):

  excel_data = pandas.read_excel(infilename,header=1)

  DataFrame = pandas.read_excel(infilename, sheet_name=0)
  d = DataFrame.to_dict()
  logger.info(d)
  return d

def insertSpreadsheetDict(d,owner):
  currentPucks = []
  first_container_name = str(d["puckName"][0]).replace(" ","")
  try:
    sanitize_sheet.check_sampleNames(d["sampleName"].values())
    sanitize_sheet.check_for_duplicate_samples(d["sampleName"].values())
    #sanitize_sheet.check_for_sequence(d["sequence"].values()) #remove for now
    sanitize_sheet.check_proposalNum(d["proposalNum"].values())
  except Exception as e:
    message = 'Insert spreadsheet aborting due to %s' % repr(e)
    logger.error(message)
    print(message)
    return
  print("Spreadsheet starting with puck %s being created..." % first_container_name)
  for i in range (0,len(d["puckName"])): #number of rows in sheet
    container_name = str(d["puckName"][i]).replace(" ","")
    position_s = str(d["position"][i]).replace(" ","")
    position = int(position_s)
    propNum = None
    try:
      propNum_s = str(d["proposalNum"][i]).replace(" ","")
      propNum = int(propNum_s)
    except KeyError:
      pass
    except ValueError:
      propNum = None      
    if (propNum == ''):
      propNum = None
    logger.info(propNum)
    item_name1 = str(d["sampleName"][i]).replace(".","_")
    item_name = item_name1.replace(" ","_")    
    modelFilename = str(d["model"][i]).replace(" ","")
    sequenceFilename = str(d["sequence"][i]).replace(" ","")
    containerUID = db_lib.getContainerIDbyName(container_name,owner)
    if (containerUID == ''):
      logger.info("create container " + str(container_name))
      print("Creating container %s" % container_name)
      containerUID = db_lib.createContainer(container_name,16,owner,"16_pin_puck")
    sampleUID = db_lib.getSampleIDbyName(item_name,owner) #this line looks like not needed anymore
    logger.info("create sample " + str(item_name))
    sampleUID = db_lib.createSample(item_name,owner,"pin",model=modelFilename,sequence=sequenceFilename,proposalID=propNum)
    if (containerUID not in currentPucks):
      db_lib.emptyContainer(containerUID)
      currentPucks.append(containerUID)
    logger.info("insertIntoContainer " + str(container_name) + "," + owner + "," + str(position) + "," + sampleUID)
    db_lib.insertIntoContainer(container_name, owner, position, sampleUID)
  print("Spreadsheet starting with puck %s created with %s samples" % (first_container_name, len(d["puckName"])))


def importSpreadsheet(infilename,owner):
  try:
    d = parseSpreadsheet(infilename)
    insertSpreadsheetDict(d,owner)
    refreshGuiTree() 
  except OSError as e:
    logger.error(f"Aborting import, bad spreadsheet file:  {infilename}")
  except EmptyDataError as e:
    logger.error(f"No data in excel file:  {infilename}")
  except ValueError as e:
    logger.error(f"Bad excel format in file {infilename}, panda raised the following error: {e}")
  except ImportError as e:
    logger.error(f"Panda raised the following:  {e}")
