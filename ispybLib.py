import ispyb.factory
from ispyb.exception import ISPyBNoResultException
import os
from datetime import datetime
from ispyb.xmltools import mx_data_reduction_to_ispyb, xml_file_to_dict
import daq_utils
from epics import PV
import db_lib
import det_lib
import time
from PIL import Image
import logging
from config_params import CollectionProtocols
logger = logging.getLogger(__name__)

#12/19 - I'm leaving all commented lines alone on this. Karl Levik, DLS, is an immense help with this.

ispyb_db_name = os.environ("ISPYB_DB", "ispyb")
conf_file = f"/etc/ispyb/{ispyb_db_name}Config.cfg"
visit = 'mx99999-1'
# Get a list of request dicts
#request_dicts = lsdb2.getColRequestsByTimeInterval('2018-02-14T00:00:00','2018-02-15T00:00:00')

# Connect to ISPyB, get the relevant data area objects
#conn = ispyb.open(conf_file)
#core = ispyb.factory.create_data_area(ispyb.factory.DataAreaType.CORE, conn)
#mxacquisition = ispyb.factory.create_data_area(ispyb.factory.DataAreaType.MXACQUISITION, conn)
#mxprocessing = ispyb.factory.create_data_area(ispyb.factory.DataAreaType.MXPROCESSING, conn)
#mxscreening = ispyb.factory.create_data_area(ispyb.factory.DataAreaType.MXSCREENING, conn)
#cnx = mysql.connector.connect(user='ispyb_api', password=os.environ['ISPYB_PASSWORD'],host='ispyb-db-dev.cs.nsls2.local',database='ispyb')
#cursor = cnx.cursor()
beamline = os.environ["BEAMLINE_ID"]

  # Find the id for a particular

def queryOneFromDB(q):
  cursor.execute(q)
  try:
    return list(cursor.fetchone())[0]
  except TypeError:
    return 0


def insertPlotResult(dc_id,imageNumber,spotTotal,goodBraggCandidates,method2Res,totalIntegratedSignal):
  return
  params = mxprocessing.get_quality_indicators_params()
  params['datacollectionid'] = dc_id
  params['imageNumber'] = imageNumber
  params['spotTotal'] = spotTotal
  params['goodBraggCandidates'] = goodBraggCandidates
  params['method2Res'] = method2Res
  params['totalIntegratedSignal'] = totalIntegratedSignal
  id = mxprocessing.upsert_quality_indicators(list(params.values()))
  cnx.commit()         

def insertResult(result,resultType,request,visitName,dc_id=None,xmlFileName=None): #xmlfilename for fastDP
#keep in mind that request type can be standard and result type be fastDP - multiple results per req.
 return

 try:
   sessionid = core.retrieve_visit_id(visitName)
 except ISPyBNoResultException as e:
   message = f"insert result - caught ISPyBNoResultException: '{e}'."
   logger.exception(message)
   raise e
 request_type = request['request_type']
 if request_type in (CollectionProtocols.STANDARD, CollectionProtocols.VECTOR):
   sample = request['sample'] # this needs to be created and linked to a DC group
   if (resultType == 'fastDP'):
     mx_data_reduction_dict = xml_file_to_dict(xmlFileName)
     comm = mx_data_reduction_dict['AutoProcProgramContainer']['AutoProcProgram']['processingCommandLine']
     mx_data_reduction_dict['AutoProcProgramContainer']['AutoProcProgram']['processingCommandLine'] = comm[len(comm)-255:]
     (app_id, ap_id, scaling_id, integration_id) = mx_data_reduction_to_ispyb(mx_data_reduction_dict, dc_id, mxprocessing)
     mxprocessing.upsert_program_ex(program_id=app_id,status=1)
         
   elif resultType == 'mxExpParams':
     result_obj = result['result_obj']
     request_obj = result_obj['requestObj']
     directory = request_obj["directory"]
     filePrefix = request_obj['file_prefix']
     basePath = request_obj["basePath"]
     visitName = daq_utils.getVisitName()
     jpegDirectory = visitName + "/jpegs/" + directory[directory.find(visitName)+len(visitName):len(directory)]  
     fullJpegDirectory = basePath + "/" + jpegDirectory
     jpegImagePrefix = fullJpegDirectory+"/"+filePrefix     
     daq_utils.take_crystal_picture(filename=jpegImagePrefix)
     jpegImageFilename = jpegImagePrefix+".jpg"
     jpegImageThumbFilename = jpegImagePrefix+"t.jpg"
     resizeRatio = 0.4
     logger.info(f'resizing image: ratio: {resizeRatio} filename: {jpegImageThumbFilename}')
     fullSnapshot = Image.open(jpegImageFilename)
     resizeWidth = fullSnapshot.width * resizeRatio
     resizeHeight = fullSnapshot.height * resizeRatio
     thumbSnapshot = fullSnapshot.resize((int(resizeWidth), int(resizeHeight)))
     thumbSnapshot.save(jpegImageThumbFilename)
     
     seqNum = int(det_lib.detector_get_seqnum())          
     node = db_lib.getBeamlineConfigParam(beamline,"adxvNode")
     request_id = result['request']
     comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}eiger2cbf.sh {request_id} 1 1 0 {seqNum}\""
     logger.info(f'diffraction thumbnail conversion to cbf: {comm_s}')
     os.system(comm_s)
     comm_s = f"ssh -q {node} \"{os.environ['MXPROCESSINGSCRIPTSDIR']}cbf2jpeg.sh {request_id}\""
     logger.info(f'diffraction thumbnail conversion to jpeg: {comm_s}')
     os.system(comm_s)
     # Create a new data collection group entry:
     params = mxacquisition.get_data_collection_group_params()
     params['parentid'] = sessionid
     if request_type == CollectionProtocols.STANDARD:
       params['experimenttype'] = 'OSC'
     elif request_type == CollectionProtocols.VECTOR:
       params['experimenttype'] = 'Helical'
     return createDataCollection(directory, filePrefix, jpegImageFilename, params, request_obj, sessionid)

                 ## For strategies (EDNA or otherwise)
                 # params = mxscreening.get_screening_params()
                 # params['dcgid'] = dcg_id
                 # ...
                 # s_id = mxscreening.insert_screening(list(params.values()))
                 # params = mxscreening.get_screening_input_params()
                 # params['screening_id'] = s_id
                 # ...
                 # s_in_id = mxscreening.insert_screening_input(list(params.values()))
                 # params = mxscreening.get_screening_output_params()
                 # params['screening_id'] = s_id
                 # ...
                 # s_out_id = mxscreening.insert_screening_output(list(params.values()))
                 # params = mxscreening.get_screening_output_lattice_params()
                 # params['screening_output_id'] = s_out_id
                 # ...
                 # mxscreening.insert_screening_output_lattice(list(params.values()))

                 # params = mxscreening.get_screening_strategy_params()
                 # params['screening_output_id'] = s_out_id
                 # ...
                 # s_s_id = mxscreening.insert_screening_strategy(list(params.values()))
                 # params = mxscreening.get_screening_strategy_wedge_params()
                 # params['screening_strategy_id'] = s_s_id
                 # ...
                 # s_s_wedge_id = mxscreening.insert_screening_strategy_wedge(list(params.values()))
                 # params = mxscreening.get_screening_strategy_sub_wedge_params()
                 # params['screening_strategy_wedge_id'] = s_s_wedge_id
                 # ...
                 # mxscreening.insert_screening_strategy_sub_wedge(list(params.values()))

                 ## For raster scans a.k.a. grid scans:
                 # params = mxacquisition.get_dc_position_params()
                 # params['id'] = dc_id
                 # params['posx'] =
                 # params['posy'] =
                 # params['posz'] =
                 # mxacquisition.update_dc_position(list(params.values()))

                 ## For per-image analysis results (raster scans or otherwise)
                 # for image in images:
                 #     params = mxprocessing.get_quality_indicators_params()
                 #     imq.imagenumber as nim, imq.method2res as res, imq.spottotal as s, imq.totalintegratedsignal, imq.goodbraggcandidates as b
                 #     params['imagenumber'] =
                 #     params['datacollectionid'] =
                 #     params['method2res'] =
                 #     params['spottotal'] =
                 #     params['totalintegratedsignal'] =
                 #     params['goodbraggcandidates'] =
                 #     mxprocessing.upsert_quality_indicators(list(params.values()))

                 ## For fast_dp and similar MX data reduction pipeline results:
                 # ...
                 # (app_id, ap_id, scaling_id, integration_id) = mx_data_reduction_to_ispyb(mx_data_reduction_dict, dc_id, mxprocessing)


                 ## For raster scans a.k.a. grid scans:
                 # params = mxacquisition.get_dcg_grid_params()
                 # params['parentid'] = dcg_id
                 # params['dx_mm'] =
                 # params['dy_mm'] =
                 # params['steps_x'] =
                 # params['steps_y'] =
                 # params['pixelspermicronx'] =
                 # params['pixelspermicrony'] =
                 # params['snapshot_offsetxpixel'] =
                 # params['snapshot_offsetypixel'] =
                 # params['orientation'] =
                 # params['snaked'] =
                 # mxacquisition.upsert_dcg_grid(list(params.values()))


                 # Beamsize:
                 # params['beamsize_at_samplex'] = ?
                 # params['beamsize_at_sampley'] = ?

                 # Other things:
                 # params['xbeam'] = ?
                 # params['ybeam'] = ?
                 # params['phistart'] = ?
                 # params['kapppastart'] = ?
                 # params['omegastart'] = ?

       # hard-coding hack to make SynchWeb understand whether it's a full data collection or a screening


def createDataCollection(directory, filePrefix, jpegImageFilename, params, request_obj, sessionid):
    return
    params['starttime'] = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    params['endtime'] = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    dcg_id = mxacquisition.insert_data_collection_group(list(params.values()))
    logger.info("dcg_id: %i" % dcg_id)
    params = mxacquisition.get_data_collection_params()
    params['parentid'] = dcg_id
    params['visitid'] = sessionid
    params['imgdir'] = directory
    params['imgprefix'] = filePrefix
    params['imgsuffix'] = 'cbf'  # assume CBF ...?
    params['wavelength'] = request_obj['wavelength']
    params['starttime'] = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    params['run_status'] = 'DataCollection Successful'  # assume success / not aborted
    params['datacollection_number'] = request_obj['runNum']
    if request_obj['img_width'] > 0:
      params['n_images'] = int(round((request_obj['sweep_end'] - request_obj['sweep_start']) / request_obj['img_width']))
    else:
      params['n_images'] = 1 # stills mode
    params['exp_time'] = request_obj['exposure_time']
    params['start_image_number'] = request_obj['file_number_start']
    params['axis_start'] = request_obj['sweep_start']
    params['axis_end'] = request_obj['sweep_end']
    params['axis_range'] = request_obj['img_width']
    params['resolution'] = request_obj['resolution']
    params['detector_distance'] = request_obj['detDist']
    params['slitgap_horizontal'] = request_obj['slit_width']
    params['slitgap_vertical'] = request_obj['slit_height']
    params['transmission'] = request_obj['attenuation'] * 100.0
    params['file_template'] = '%s_####.cbf' % (request_obj['file_prefix'])  # assume cbf ...
    params['overlap'] = 0.0
    params['rotation_axis'] = 'Omega'  # assume Omega unless we know otherwise
    logger.info("jpegimfilename = " + jpegImageFilename)
    try:
      params['xbeam'] = request_obj['xbeam']
      params['ybeam'] = request_obj['ybeam']
    except KeyError:
      logger.error('Value of xbeam or ybeam not present')
    params['xtal_snapshot1'] = jpegImageFilename
    params['xtal_snapshot2'] = '/dls/i03/data/2016/cm14451-2/jpegs/20160413/test_xtal/xtal1_1_1_90.0.png'
    params['xtal_snapshot3'] = '/dls/i03/data/2016/cm14451-2/jpegs/20160413/test_xtal/xtal1_3_1_183.0.png'
    params['xtal_snapshot4'] = '/dls/i03/data/2016/cm14451-2/jpegs/20160413/test_xtal/xtal1_3_1_93.0.png'
    dc_id = mxacquisition.insert_data_collection(list(params.values()))
    logger.info("dc_id: %i" % dc_id)
    return dc_id


#         if request_type == 'screening':
#           params['overlap'] = 89.0
                 
def insertRasterResult(request,visitName): 
 return
 try:
   sessionid = core.retrieve_visit_id(visitName)
 except ISPyBNoResultException as e:
   message = f"insertRasterResult - caught ISPyBNoResultException: '{e}'."
   logger.error(message)
   raise e
 request = db_lib.getRequestByID(request_id)
 sample = request['sample'] # this needs to be created and linked to a DC group
 #result_obj = result['result_obj'] this doesn't appear to be used -DK
 request_obj = request['request_obj']
 directory = request_obj["directory"]
 filePrefix = request_obj['file_prefix']
 basePath = request_obj["basePath"]
 visitName = daq_utils.getVisitName()
 jpegDirectory = visitName + "/jpegs/" + directory[directory.find(visitName)+len(visitName):len(directory)]  
 fullJpegDirectory = basePath + "/" + jpegDirectory
 jpegImagePrefix = fullJpegDirectory+"/"+filePrefix     
 jpegImageFilename = jpegImagePrefix+".jpg"
 jpegImageThumbFilename = jpegImagePrefix+"t.jpg"
 comm_s = "convert " + jpegImageFilename + " -resize 40% " + jpegImageThumbFilename + "&"     
 logger.info('raster thumbnail creation: %s' %comm_s)
 os.system(comm_s)
 # Create a new data collection group entry:
 params = mxacquisition.get_data_collection_group_params()
 params['parentid'] = sessionid
 params['experimenttype'] = 'OSC'
 return createDataCollection(directory, filePrefix, jpegImageFilename, params, request_obj, sessionid)
