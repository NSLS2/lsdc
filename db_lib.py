import logging
import os
import time
import uuid
from collections import defaultdict

import amostra.client.commands as acc
import conftrak.client.commands as ccc
import conftrak.exceptions
import six
from analysisstore.client.commands import AnalysisClient
from pathlib import Path
logger = logging.getLogger(__name__)

#12/19 - Skinner inherited this from Hugo, who inherited it from Matt. Arman wrote the underlying DB and left BNL in 2018. 

# TODO: get the beamline_id from parameter
BEAMLINE_ID = '17ID1'


sample_ref = None
container_ref = None
request_ref = None
configuration_ref = None
mds_ref = None
analysis_ref = None

main_server = os.environ['MONGODB_HOST']

services_config = {
    'amostra': {'host': main_server, 'port': '7770'},
    'conftrak': {'host': main_server, 'port': '7771'},
    'metadataservice': {'host': main_server, 'port': '7772'},
    'analysisstore': {'host': main_server, 'port': '7773'}    
}


def db_connect(params=services_config):
    global sample_ref,container_ref,request_ref,configuration_ref,analysis_ref
    """
    recommended idiom:
    """
    sample_ref = acc.SampleReference(**params['amostra'])
    container_ref = acc.ContainerReference(**params['amostra'])
    request_ref = acc.RequestReference(**params['amostra'])

    configuration_ref = ccc.ConfigurationReference(**services_config['conftrak'])
    analysis_ref = AnalysisClient(services_config['analysisstore'])
    logger.info(analysis_ref)

# should be in config :(
primaryDewarName = 'primaryDewarJohn'


#connect on import
db_connect()


def setCurrentUser(beamline,userName): #for now username, although these should be unique
  setBeamlineConfigParam(beamline,"user",userName)

def getCurrentUser(beamline): #for now username, although these should be unique
  return getBeamlineConfigParam(beamline,"user")
  

def setPrimaryDewarName(dewarName):
  global primaryDewarName

  primaryDewarName = dewarName



def searchBeamline(**kwargs):
    try:
        return list(configuration_ref.find(key="beamline", **kwargs))
    except StopIteration:
        return None


def getBeamlineByNumber(num):
    """eg. 17id1, 17id2, 16id1"""
    try:
        return list(configuration_ref.find(key="beamline", number=num))
    except StopIteration:
        return None


def createContainer(name, capacity, owner, kind, **kwargs): #16_pin_puck, automounterDewar, shippingDewar
    """
    container_name:  string, name for the new container, required
    kwargs:          passed to constructor
    """
    
    if capacity is not None:
        kwargs['content'] = [""]*capacity
    uid = container_ref.create(name=name, 
                            owner=owner, 
                            kind=kind,
                            modified_time=time.time(), 
                            **kwargs)
    return uid


def updateContainer(cont_info): #really updating the contents
    cont = cont_info['uid']
    q = {'uid': cont_info.pop('uid', '')}
    cont_info.pop('time', '')
    container_ref.update(q, {'content':cont_info['content'], 
                             'modified_time': time.time()})  

    return cont


def createSample(sample_name, owner, kind, proposalID=None, **kwargs):
    """
    sample_name:  string, name for the new sample, required
    kwargs:       passed to constructor
    """
    # initialize request count to zero
    if 'request_count' not in kwargs:
        kwargs['request_count'] = 0

    uid = sample_ref.create(name=sample_name, owner=owner,kind=kind,proposalID=proposalID,**kwargs)
    return uid


def incrementSampleRequestCount(sample_id):
    """
    increment the 'request_count' attribute of the specified sample by 1
    """

    # potential for race here?
#skinner - I don't understand this line    sample_ref.update(query={'uid': sample_id}, update={'$inc': {'request_count': 1}})
    reqCount = getSampleRequestCount(sample_id)+1
    sample_ref.update({'uid': sample_id},{'request_count':reqCount})
    
    return getSampleRequestCount(sample_id)


def getSampleRequestCount(sample_id):
    """
    get the 'request_count' attribute of the specified sample
    """
    s = getSampleByID(sample_id)
    return s['request_count']


def getRequestsBySampleID(sample_id, active_only=True):
    """
    return a list of request dictionaries for the given sample_id
    """
    params = {'sample': sample_id}
    if active_only:
        params['state'] = "active"
    reqs = list(request_ref.find(**params))
    return reqs


def getSampleByID(sample_id):
    """
    sample_id:  required, integer
    """
    s = list(sample_ref.find(uid=sample_id))
    if (s):
      return s[0]
    else:
      return {}
  


def getSampleNamebyID(sample_id):
    """
    sample_id:  required, integer
    """
    s = getSampleByID(sample_id)
    if (s==None):
      return ''
    else:
      return s['name']


def getSamplesbyOwner(owner): #skinner
    s = sample_ref.find(owner=owner)
    return [samp['uid'] for samp in s]

def getSampleIDbyName(sampleName,owner):
    """
    sample_id:  required, integer
    """
    samples = list(sample_ref.find(owner=owner,name=sampleName))
    if (samples != []):
      return samples[0]["uid"]
    else:
      return ""
  

def getContainerIDbyName(container_name,owner):
    containers = list(container_ref.find(owner=owner,name=container_name))
    if (containers != []):
      return containers[0]["uid"]
    else:
      return ""




def getContainerNameByID(container_id):
    """
    container_id:  required, integer
    """
    c = list(container_ref.find(uid=container_id))
    return c[0]['name']


def createResult(result_type, owner,request_id=None, sample_id=None, result_obj=None, proposalID=None,
                 **kwargs):
    """
    result_type:  string
    request_id:   int
    sample_id:    int
    result_obj:   dict to attach
    """

    header = analysis_ref.insert_analysis_header(result_type=result_type,owner=owner, uid=str(uuid.uuid4()),
                                                sample=sample_id, request=request_id,
                                                 provenance={'lsdc':1}, result_obj=result_obj,proposalID=proposalID,time=time.time(),**kwargs)
    logger.info("uuid of result inserted into analysisstore: %s" % header)

    return header


def getResult(result_id):
    """
    result_id:  required, int
    """
    header = list(analysis_ref.find_analysis_header(uid=result_id))
    return header[0]


def getResultsforRequest(request_id):
    """
    Takes an integer request_id  and returns a list of matching results or [].
    """
    resultGen = analysis_ref.find_analysis_header(request=request_id)
    if (resultGen != None):
      headers = list(resultGen)
      return headers
    else:
      return []
  


def getResultsforSample(sample_id):
    """
    Takes a sample_id and returns it's resultsList or [].
    """
    headers = list(analysis_ref.find_analysis_header(sample=sample_id))
    return headers


def getRequestByID(request_id, active_only=True):
    """
    return a list of request dictionaries for the given request_id
    """
    params = {'uid': request_id}
    if active_only:
        params['state'] = "active"
    req = list(request_ref.find(**params))[0]
    return req


def addResultforRequest(result_type, request_id, owner,result_obj=None, **kwargs): 
    """
    like createResult, but also adds it to the resultList of result['sample_id']
    """
    sample = getRequestByID(request_id)['sample'] 
    r = createResult(owner=owner,result_type=result_type, request_id=request_id, sample_id=sample, result_obj=result_obj, **kwargs)
    return r


def addResulttoSample(result_type, sample_id, owner,result_obj=None, as_mongo_obj=False, proposalID=None,**kwargs): 
    """
    like addResulttoRequest, but without a request
    """
    r = createResult(owner=owner,result_type=result_type, request_id=None, sample_id=sample_id, result_obj=result_obj, proposalID=proposalID,**kwargs)
    return r


def addResulttoBL(result_type, beamline_id, owner,result_obj=None, proposalID=None,**kwargs):
    """
    add result to beamline
    beamline_id: the integer, 'beamline_id' field of the beamline entry

    other fields are as for createRequest
    """
    r = createResult(owner=owner,result_type=result_type, request_id=None, sample_id=None, result_obj=result_obj, beamline_id=beamline_id, proposalID=proposalID,**kwargs)
    return r


def getResultsforBL(id=None, name=None, number=None):
    """
    Retrieve results using either BL id, name, or number (tried in that order)
    Returns a generator of results
    """
    if id is None:
        if name is None:
            key = 'number'
            val = number
        else:
            key = 'name'
            val = name

        query = {key: val}
        b = searchBeamline(**query)
        if b is None:
            yield None
            raise StopIteration

        id = b['uid']

        if id is None:
            yield None
            raise StopIteration

    results = list(analysis_ref.find_analysis_header(beamline_id=id))

    for r in results:
        yield r


def addFile(data=None, filename=None):
    """
    Put the file data into the GenericFile collection,
    return the _id for use as an id or ReferenceField.

    If a filename kwarg is given, read data from the file.
    If a data kwarg is given or data is the 1st arg, store the data.
    If both or neither is given, raise an error.
    """
    #TODO: Decide what to do with this method
    raise NotImplemented
    '''
    if filename is not None:
        if data is not None:
            raise ValueError('both filename and data kwargs given.  can only use one.')
        else:
            with open(filename, 'r') as file:  # do we need 'b' for binary?
                data = file.read()  # is this blocking?  might not always get everything at once?!

    elif data is None:
        raise ValueError('neither filename or data kwargs given.  need one.')

    f = GenericFile(data=data)
    f.save()
    f.reload()  # to fetch generated id
    return f.to_dbref()
    '''

def getFile(_id):
    """
    Retrieve the data from the GenericFile collection
    for the given _id or db_ref

    Returns the data in Binary.  If you know it's a txt file and want a string,
    convert with str()

    Maybe this will be automatically deref'd most of the time?
    Only if they're mongoengine ReferenceFields...
    """
    #TODO: Decide what to do with this method
    raise NotImplemented
    '''
    try:
        _id = _id.id

    except AttributeError:
        pass

    f = GenericFile.objects(__raw__={'_id': _id})  # yes it's '_id' here but just 'id' below, gofigure
    return _try0_dict_key(f, 'file', 'id', _id, None,
                           dict_key='data')
    '''

def createRequest(request_type, owner, request_obj=None, as_mongo_obj=False, proposalID=None, **kwargs):
    """
    request_type:  required, name (string) of request type, dbref to it's db entry, or a Type object
    request_obj:  optional, stored as is, could be a dict of collection parameters, or whatever
    priority:  optional, integer priority level

    anything else (priority, sample_id) can either be embedded in the
    request_object or passed in as keyword args to get saved at the
    top level.
    """
    kwargs['request_type'] = request_type
    kwargs['request_obj'] = request_obj
    kwargs['owner'] = owner
    kwargs['proposalID']=proposalID

    uid = request_ref.create(**kwargs)

    return uid 


def addRequesttoSample(sample_id, request_type, owner,request_obj=None, as_mongo_obj=False, proposalID=None,**kwargs):
    """
    sample_id:  required, integer sample id
    request_type:  required, name (string) of request type, dbref to it's db entry, or a Type object
    request_obj:  optional, stored as is, could be a dict of collection parameters, or whatever

    anything else (priority, sample_id) can either be embedded in the
    request_object or passed in as keyword args to get saved at the
    top level.
    """

    kwargs['sample'] = sample_id
    s = time.time()
    r = createRequest(request_type, owner, request_obj=request_obj, as_mongo_obj=True, proposalID=proposalID,**kwargs)
    t = time.time()-s
    logger.info("add req = " + str(t))

    return r


def insertIntoContainer(container_name, owner, position, itemID):
    c = getContainerByName(container_name,owner)
    if c is not None:
        cnt = c['content']
        cnt[position - 1] = itemID  # most people don't zero index things
        c['content'] = cnt
        updateContainer(c)
        return True
    else:
        logger.error("bad container name %s" % container_name)
        return False


def emptyContainer(uid):
    c = getContainerByID(uid)
    if c is not None:
        cnt = c['content']
        for i in range (len(cnt)):        
          cnt[i] = ''
        c['content'] = cnt
        updateContainer(c)
        return True
    else:
        logger.error("container not found")
        return False


def getContainers(filters=None): 
    """get *all* containers"""
    if filters is not None:
        c = list(container_ref.find(**filters)) #skinner - seems to break on compound filter
    else:
        c = list(container_ref.find())
    return c


def getContainersByType(type_name, owner): 
    #TODO: group_name was not being used kept for compatibility
    return getContainers(filters={"kind": type_name,"owner":owner})


def getAllPucks(owner): #shouldn't this be for owner?
    # find all the types desended from 'puck'?
    # and then we could do this?
    return getContainersByType("16_pin_puck", owner)


def getPrimaryDewar(beamline):
    """
    returns the mongo object for a container with a name matching
    the global variable 'primaryDewarName'
    """
    return getContainerByName(primaryDewarName,beamline)


def getContainerByName(container_name,owner):
    c = getContainers(filters={'name': container_name,'owner':owner})[0] #skinner, this should return only one, not a list
    return c


def getContainerByID(container_id):
    c = getContainers(filters={'uid': container_id})[0]
    return c

def get_dewar_tree_data(dewar_name, beamline, get_latest_pucks=False):
    """
    returns all data required to show dewar tree data with minimum number of database accesses
    """
    dewar_data = getContainers(filters={"name": dewar_name, "owner": beamline})[0]

    puck_ids = [
        pid for pid in dewar_data.get("content", []) if pid
    ]  # removes blank ids
    pucks = getContainers(filters={"uid": {"$in": puck_ids}})

    if get_latest_pucks:
        # If get_latest_pucks is true, get the puck most recently updated in the database
        # This is for cases when the excel sheet has been uploaded after puck_to_dewar
        # Or when staff manually refreshes the dewar tree
        new_pucks = []
        for puck in pucks:
            all_pucks = getContainers(filters={"name":puck["name"]})
            latest_puck = max(all_pucks, key=lambda x: x.get("modified_time", 0.0))
            new_pucks.append(latest_puck)
        pucks = new_pucks  
    # Create a mega list of sample ids from puck information
    sample_ids = [
        sample_id
        for puck in pucks
        for sample_id in puck.get("content", [])
        if sample_id
    ]

    # Get all sample info in one call
    params = {"uid": {"$in": sample_ids}}
    samples = sample_ref.find(as_document=False, **params)

    # Get all request info in one call
    params = {"sample": {"$in": sample_ids}, "state": "active"}
    reqs = list(request_ref.find(**params))

    # Assemble data into dictionaries
    puck_data = {puck["uid"]: puck for puck in pucks}
    sample_data = {sample["uid"]: sample for sample in samples}
    request_data = defaultdict(list)
    for req in reqs:
        request_data[req["sample"]].append(req)
    
    return dewar_data, puck_data, sample_data, request_data



def getQueue(beamlineName):
    """
    returns a list of request dicts for all the samples in the container
    named by the global variable 'primaryDewarName'
    """

    # seems like this would be alot simpler if it weren't for the Nones?

    ret_list = []

    # try to only retrieve what we need...
    # Use .first() instead of [0] here because when the query returns nothing,
    # .first() returns None while [0] generates an IndexError
    # Nah... [0] is faster and catch Exception...
    DewarItems = []
    try:
        DewarItems = getPrimaryDewar(beamlineName)['content']
    except IndexError as AttributeError:
        raise ValueError('could not find container: "{0}"!'.format(primaryDewarName))
    items = []
    for item in DewarItems:
      if (item != ""):
        items.append(item)
    logger.debug(f"dewar items: {items}")

    sample_list = []
    contents = [getContainerByID(uid)['content'] for uid in items]
    logger.debug(f"total contents: {contents}")
    for samples in contents:
        logger.debug(f"samples: {samples}")
        for samp in samples:
            logger.debug(f'{samp} {samp!=""}')
            if (samp != ""):
              sample_list.append(samp)
    logger.debug(f"sample list: {sample_list}")

    for s in sample_list:
        reqs = getRequestsBySampleID(s, active_only=True)
        logger.debug(f"requests for sample {s}: {reqs}")
        for request in reqs:
            yield request



def getQueueUnorderedObsolete(beamlineName):
    """
    returns a list of request dicts for all the samples in the container
    named by the global variable 'primaryDewarName'
    """

    # seems like this would be alot simpler if it weren't for the Nones?

    ret_list = []

    # try to only retrieve what we need...
    # Use .first() instead of [0] here because when the query returns nothing,
    # .first() returns None while [0] generates an IndexError
    # Nah... [0] is faster and catch Exception...
    try:
        items = getPrimaryDewar(beamlineName)['content']
    except IndexError as AttributeError:
        raise ValueError('could not find container: "{0}"!'.format(primaryDewarName))

    items = set(items)
    items.discard("")  # skip empty positions

    sample_list = []
    contents = [getContainerByID(uid)['content'] for uid in items]
    for samp in contents:
        sil = set(samp)
        sil.discard("")
        sample_list += sil

    for s in sample_list:
        reqs = getRequestsBySampleID(s, active_only=True)
        for request in reqs:
            yield request


            
def queueDone(beamlineName):
    ql = list(getQueue(beamlineName))
    
    for i in range (0,len(ql)):
      if (ql[i]['priority'] > 0):
        return 0
    return 1
      


def getCoordsfromSampleID(beamline,sample_id):
    """
    returns the container position within the dewar and position in
    that container for a sample with the given id in one of the
    containers in the container named by the global variable
    'primaryDewarName'
    """
    try:
        primary_dewar_item_list = getPrimaryDewar(beamline)['content']
    except IndexError as AttributeError:
        raise ValueError('could not find container: "{0}"!'.format(primaryDewarName))
#john    try:

    # eliminate empty item_list slots
    pdil_set = set(primary_dewar_item_list)
    pdil_ssample_id = pdil_set.discard("")

    # find container in the primary_dewar_item_list (pdil) which has the sample

    filters = {'$and': [{'uid': {'$in':list(pdil_set)}}, {'content': {'$in':[sample_id]}}]}
    c = getContainers(filters=filters)

    # get the index of the found container in the primary dewar
    i = primary_dewar_item_list.index(c[0]['uid'])

    # get the index of the sample in the found container item_list
    j = c[0]['content'].index(sample_id)

    # get the container_id of the found container
    puck_id = c[0]['uid']

    return (i, j, puck_id)


def popNextRequest(beamlineName):
    """
    this just gives you the next one, it doesn't
    actually pop it off the stack
    """
    orderedRequests = getOrderedRequestList(beamlineName)
    logger.info(f"Requests in queue: {len(orderedRequests)}")
    request_proposal_ids = set()
    request_paths = set()
    for req in orderedRequests:
        if req["priority"] > 0 and req["priority"] != 99999:
            request_proposal_ids.add(req["proposalID"])
            request_paths.add(req["request_obj"]["basePath"])
    visit_dir_path = Path(getBeamlineConfigParam(beamlineName, "visitDirectory")).resolve()
    if request_proposal_ids:
        if len(request_proposal_ids) > 1 and "commissioning" not in visit_dir_path.parts:
            # Multiple proposal requests being run and not in commissioning
            logger.error(f"Queue contains requests with multiple proposals, and server not running in commissioning dir")
            return None
        elif Path(list(request_paths)[0]).resolve() != visit_dir_path and "commissioning" not in visit_dir_path.parts:
            # Single proposal being run, does not match visit dir and not commissioning
            logger.error(f"Proposal directory mismatch, and server not running in commissioning dir")
            return None


    try:
        for req in orderedRequests:
            if req["priority"] != 99999 and req["priority"] > 0:
                return req
    except IndexError:
        pass

    return {}


def getRequestObsolete(reqID):  # need to get this from searching the dewar I guess 
#skinner - no idea    reqID = int(reqID)
    """
    request_id:  required, integer id
    """
    r = getRequestByID(reqID)
    return r

def updateRequest(request_dict):
    """
    This is not recommended once results are recorded for a request!
    Using a new request instead would keep the apparent history
    complete and intuitive.  Although it won't hurt anything if you've
    also recorded the request params used inside the results and query
    against that, making requests basically ephemerally useful objects.
    """

    if 'uid' in request_dict:
        r_uid = request_dict.pop('uid', '')        
        s_time = request_dict.pop('time', '')
        r = request_ref.update({'uid':r_uid},request_dict)
        request_dict["uid"] = r_uid
        request_dict["time"] = s_time


def deleteRequest(r_id):
    """
    reqObj should be a dictionary with a 'uid' field
    and optionally a 'sample_uid' field.

    """


    r = getRequestByID(r_id)
    r['state'] = "inactive"
    updateRequest(r)


def updateSample(sampleObj):
    if 'uid' in sampleObj:
        s_uid = sampleObj.pop('uid','')
        s_time = sampleObj.pop('time','')        
        s = sample_ref.update({'uid': s_uid}, sampleObj)


def deleteSample(sample_uid):
    s = getSampleByID(sample_uid)
    s['state'] = "active"
    updateSample(s)


def removePuckFromDewar(beamline,dewarPos):
    dewar = getPrimaryDewar(beamline)
    dewar['content'][dewarPos] = ''
    updateContainer(dewar)


def updatePriority(request_id, priority):
    r = getRequestByID(request_id)
    r['priority'] = priority
    updateRequest(r)


def getPriorityMap(beamlineName):
    """
    returns a dictionary with priorities as keys and lists of requests
    having those priorities as values
    """

    priority_map = {}

    for request in getQueue(beamlineName):
        try:
            priority_map[request['priority']].append(request)

        except KeyError:
            priority_map[request['priority']] = [request]

    return priority_map


def getOrderedRequestList(beamlineName):
    """
    returns a list of requests sorted by priority
    """

    orderedRequestsList = []

    priority_map = getPriorityMap(beamlineName)

    for priority in sorted(six.iterkeys(priority_map), reverse=True):
        orderedRequestsList += priority_map[priority]
        #for request in priority_map[priority]:
        #    yield request
        # or if we want this to be a generator could it be more efficient
        # with itertools.chain?
        # foo=['abc','def','ghi']
        # [a for a in itertools.chain(*foo)]
        # ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
        # or [a for a in itertools.chain.from_iterable(foo)]

    return orderedRequestsList






def createBeamline(bl_name, bl_num): #createBeamline("fmx", "17id1")
    data = {"key": "beamline", "name": bl_name, "number": bl_num}
    uid = configuration_ref.create(beamline_id=bl_num, **data)
    return uid








def beamlineInfo(beamline_id, info_name, info_dict=None):
    """
    to write info:  beamlineInfo('x25', 'det', info_dict={'vendor':'adsc','model':'q315r'})
    to fetch info:  info = beamlineInfo('x25', 'det')
    """

    # if it exists it's a query or update
    try:
        bli = list(configuration_ref.find(key='beamline_info', beamline_id=beamline_id, info_name=info_name))[0] #hugo put the [0]

        if info_dict is None:  # this is a query
            return bli['info']

        # else it's an update
        bli_uid = bli.pop('uid', '')
        configuration_ref.update({'uid': bli_uid},{'info':info_dict})

    # else it's a create
    except conftrak.exceptions.ConfTrakNotFoundException:
        # edge case for 1st create in fresh database
        # in which case this as actually a query
        if info_dict is None:
            return {}

        # normal create
        data = {'key': 'beamline_info', 'info_name':info_name, 'info': info_dict}
        uid = configuration_ref.create(beamline_id,**data)


def setBeamlineConfigParams(paramDict, searchParams):
    # get current config
    beamlineConfig = beamlineInfo(**searchParams)

    # update with given param dict and last_modified
    paramDict['last_modified'] = time.time()
    beamlineConfig.update(paramDict)

    # save  
    beamlineInfo(info_dict=beamlineConfig, **searchParams)

def setBeamlineConfigParam(beamline_id, paramName, paramVal):
    beamlineInfo(beamline_id,paramName,{"val":paramVal})

def getBeamlineConfigParam(beamline_id, paramName):
    try:
        return beamlineInfo(beamline_id,paramName)["val"]
    except KeyError as e:
        logger.error(f'key {paramName} does not exist as part of beamlineInfo')
        raise e

def getAllBeamlineConfigParams(beamline_id):
  g = configuration_ref.find(key='beamline_info', beamline_id=beamline_id)
  configList = list(g)
  return configList

def logAllBeamlineConfigParams(beamline_id):
  printAllBeamlineConfigParams(beamline_id, log=True)

def printAllBeamlineConfigParams(beamline_id, log=False):
  configList = getAllBeamlineConfigParams(beamline_id)
  for i in range (0,len(configList)):
    try:
      if log:
        logger.info(configList[i]['info_name'] + " " + str(configList[i]['info']['val']))
      else:
        print(configList[i]['info_name'] + " " + str(configList[i]['info']['val']))
    except KeyError:
      pass

def deleteCompletedRequestsforSample(sid):
  return #short circuit, not what they wanted
  logger.info("delete request " + sid)
  requestList=getRequestsBySampleID(sid)
  for i in range (0,len(requestList)):
    if (requestList[i]["priority"] == -1): #good to clean up completed requests after unmount
      if (requestList[i]["protocol"] == "raster" or requestList[i]["protocol"] == "vector"):
        deleteRequest(requestList[i]['uid'])

