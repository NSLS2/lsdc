import os
from pydantic import ValidationError
import requests
import logging
from db_lib import getRequestByID, getSampleByID
from config_params import CURRENT_CYCLE
from utils.models import Request, Sample

logger = logging.getLogger(__name__)

def get_sample_metadata(sample_id):
    sample_md = Sample.model_validate(getSampleByID(sample_id))
    return sample_md.model_dump(mode="json")

def get_bluesky_metadata(request_dict: "dict|None" = None, request_id: "str|None" = None) -> "dict[str, str]":
    if request_id and not request_dict:
        request_dict = getRequestByID(request_id)
    if request_dict is None and request_id is None:
        return {}
    bs_md = {}
    try:
        request: Request = Request.model_validate(request_dict)
        proposal_id = request.proposal_id # request["proposalID"]
        bs_md["collection_metadata"] = request.request_def.model_dump(mode="json")  # request["request_obj"]
    except ValidationError as e:
        logger.exception("Could not validate request")
        proposal_id = request_dict.get("proposal_id")
        bs_md["collection_metadata"] = request_dict.get("request_obj")

    beamline = os.environ["BEAMLINE_ID"]
    bs_md["cycle"] = CURRENT_CYCLE
        

    # Get sample metadata:
    try:
        sample_id = bs_md["collection_metadata"].get("sample")
        if sample_id:
            bs_md["sample_metadata"] = get_sample_metadata(sample_id)
    except Exception as e:
        logger.warning("Error getting sample info from API: %s", "Not populating sample info", exc_info=True)
    

    try:
        r = requests.get(f"{os.environ['NSLS2_API_URL']}/v1/proposal/{proposal_id}")
        r.raise_for_status()
        proposal_data = r.json()['proposal']
        pi_name = ""
        for user in proposal_data["users"]:
            if user.get("is_pi"):
                pi_name = (
                    f"{user.get('first_name', '')} {user.get('last_name', '')}".strip())
        proposal_id = proposal_data.get("proposal_id")
        bs_md["proposal"] = {
            "proposal_id": proposal_id,
            "title": proposal_data.get("title"),
            "type": proposal_data.get("type"),
            "pi_name": pi_name,
        }
        bs_md["data_session"] = f'pass-{proposal_id}' if proposal_id is not None else f"{beamline}_beamline"
    except Exception as e:
        bs_md["data_session"] = f"{beamline}_beamline"
        logger.warning("Error getting proposal info from API: %s", "Not populating proposal info", exc_info=True)

    bs_md["tiled_access_tags"] = [bs_md["data_session"]]
    return bs_md

