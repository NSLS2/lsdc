from pydantic import BaseModel, field_validator, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal, Union, Dict, Any, List, Tuple, NewType
from enum import Enum
from pathlib import Path

PuckName = NewType("PuckName", str)
SampleName = NewType("SampleName", str)


class RequestType(str, Enum):
    standard = "standard"
    raster = "raster"
    vector = "vector"
    multicol = "multiCol"

class BaseRequestDefinition(BaseModel):
    sample: UUID
    sweep_start: float
    sweep_end: float
    osc_range: Optional[float] = None
    img_width: float
    exposure_time: float
    protocol: RequestType
    detector_distance: float = Field(..., alias="detDist", validate_default=True)
    parent_request_id: UUID | Literal[-1] = Field(..., alias="parentReqID")
    base_path: Path = Field(..., alias="basePath", validate_default=True)
    file_prefix: str
    directory: Path
    file_number_start: int
    energy: float
    wavelength: float
    resolution: float
    slit_height: float
    slit_width: float
    attenuation: float
    visit_name: str
    detector: str
    beamline: str
    pos_x: float
    pos_y: float
    pos_z: float
    pos_type: str
    grid_step: float = Field(..., alias="gridStep")
    run_num: int = Field(..., alias="runNum")
    xbeam: Optional[float] = None
    ybeam: Optional[float] = None
    model_config = {"frozen": False, "extra": "allow"}

    @model_validator(mode="before")
    def ignore_specific_fields(cls, values):
        # Removing dataPath because it is always stuck in /legacy/2022-3 which is of no use
        fields_to_ignore = {"dataPath"}
        if isinstance(values, dict):
            return {k: v for k, v in values.items() if k not in fields_to_ignore}
        return values

    # Validator for fields of type `Path`
    @field_validator("base_path", "directory")
    def convert_to_path(cls, value):
        return Path(value) if value else value


class StandardRequestDefinition(BaseRequestDefinition):
    protocol: Literal[RequestType.standard] = RequestType.standard
    centering_option: Literal["AutoRaster", "Interactive"] = Field(
        ..., alias="centeringOption"
    )
    fast_dp: bool = Field(..., alias="fastDP")
    fast_ep: bool = Field(..., alias="fastEP")
    dimple: bool
    xia2: bool
    model_config = {"frozen": False}


class VectorRequestDefinition(BaseRequestDefinition):
    protocol: Literal[RequestType.vector] = RequestType.vector
    centering_option: Literal["AutoRaster", "Interactive"] = Field(
        ..., alias="centeringOption"
    )
    fast_dp: bool = Field(..., alias="fastDP")
    fast_ep: bool = Field(..., alias="fastEP")
    dimple: bool
    xia2: bool
    model_config = {"frozen": False}


class Point2D(BaseModel):
    x: float
    y: float
    model_config = {"frozen": False}


class Point3D(BaseModel):
    x: float
    y: float
    z: float
    model_config = {"frozen": False}


class VectorDefinition(BaseModel):
    start: Point3D = Field(..., alias="vecStart")
    end: Point3D = Field(..., alias="vecEnd")
    length: float = Field(..., alias="trans_total")
    frames_per_point: int = Field(..., alias="fpp")
    model_config = {"frozen": False}


class RasterRowDefinition(BaseModel):
    start: Point2D
    end: Point2D
    num_steps: int = Field(..., alias="numsteps")
    model_config = {"frozen": False}


class RasterDefinition(BaseModel):
    beam_width: float = Field(..., alias="beamWidth")
    beam_height: float = Field(..., alias="beamHeight")
    status: int
    x: float
    y: float
    z: float
    omega: float
    step_size: float = Field(..., alias="stepsize")
    row_defs: list[RasterRowDefinition] = Field(..., alias="rowDefs")
    num_cells: int = Field(..., alias="numCells")
    raster_type: str = Field(..., alias="rasterType")
    model_config = {"frozen": False}


class MaxRasterPosition(BaseModel):
    file: Optional[str]
    coords: list[float | None]
    index: Optional[int]
    omega: Optional[float]
    model_config = {"frozen": False}


class RasterRequestDefinition(BaseRequestDefinition):
    protocol: Literal[RequestType.raster] = RequestType.raster
    raster_def: RasterDefinition = Field(..., alias="rasterDef")
    max_raster: Optional[MaxRasterPosition] = None
    model_config = {"frozen": False}

class MultiColRequestDefinition(BaseRequestDefinition):
    protocol: Literal[RequestType.multicol] = RequestType.multicol
    raster_def: RasterDefinition = Field(..., alias="rasterDef")
    max_raster: Optional[MaxRasterPosition] = None
    model_config = {"frozen": False}

RequestDefinition = Union[
    StandardRequestDefinition, RasterRequestDefinition, VectorRequestDefinition, MultiColRequestDefinition
]

   
class StandardResult(BaseModel):
    time: Optional[float] = None
    result_time: Optional[datetime] = None
    diffraction_images: Optional[str] = None
    fast_dp_row: Optional[List] = None
    auto_proc_row: Optional[List] = None
    model_config = {"frozen": False}

    @model_validator(mode="before")
    def convert_epoch_to_datetime(cls, values: Any) -> Any:
        # Access other fields using info.data
        if values.get("result_time") is None and values.get("time") is not None:
            values["result_time"] = datetime.fromtimestamp(values["time"])
        return values

class VectorResult(StandardResult):
    pass

class RasterCellData(BaseModel):
    image: Tuple[Path, int]
    spot_count: float
    spot_count_no_ice: float
    d_min: float
    d_min_method_1: Optional[float] = None
    d_min_method_2: Optional[float] = None
    total_intensity: float
    cell_map_key: str = Field(..., alias="cellMapKey")
    model_config = {"frozen": False}

    @field_validator("image")
    def validate_and_convert_path(cls, value):
        # Convert the first element (path string) to a Path object
        path_str, some_int = value
        value = (Path(path_str), some_int)
        return value


class RasterCellCollection(BaseModel):
    type: str
    cells: List[RasterCellData] = Field(..., alias="resultObj")
    model_config = {"frozen": False}


class RasterResultData(BaseModel):
    sample_id: UUID
    parent_request_id: UUID | Literal[-1] = Field(..., alias="parentReqID")
    cell_map: Dict[str, Point3D] = Field(..., alias="rasterCellMap")
    cell_data_collection: RasterCellCollection = Field(..., alias="rasterCellResults")
    model_config = {"frozen": False}


class RasterResult(BaseModel):
    uid: UUID
    time: float
    result_time: Optional[datetime] = None
    provenance: Dict[str, Any]
    result_type: str
    owner: str
    sample: UUID
    request: UUID
    data: RasterResultData = Field(..., alias="result_obj")
    plot_image: Optional[str] = None
    jpeg_image: Optional[str] = None
    top_frames: Optional[str] = None
    hist_mean_neighbor_dist: Optional[str] = None
    hist_resolutions: Optional[str] = None
    hist_spot_count: Optional[str] = None

    model_config = {"frozen": False}

    @model_validator(mode="before")
    def convert_epoch_to_datetime(cls, values: Any) -> Any:
        # Access other fields using info.data
        if values.get("result_time") is None and values.get("time") is not None:
            values["result_time"] = datetime.fromtimestamp(values["time"])
        return values


Result = Union[StandardResult, RasterResult, VectorResult]
# Result = RasterResult


class Request(BaseModel):
    uid: UUID
    sample: UUID
    time: float
    request_time: Optional[datetime] = None
    state: Optional[Literal["active", "inactive"]] = None
    seq_num: int
    priority: int
    request_type: RequestType
    request_def: RequestDefinition = Field(..., alias="request_obj")
    owner: str
    proposal_id: str = Field(..., alias="proposalID")
    result: Optional[Result] = None

    model_config = {"frozen": False}

    @field_validator("proposal_id", mode="before")
    def proposal_id_to_str(cls, v):
        if isinstance(v, (str, int)):
            return str(v)
        raise TypeError("proposal_id must be a string or integer")

    @model_validator(mode="before")
    def convert_epoch_to_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            return values
        # Access the fields from the values dictionary
        try:
            if values.get("request_time") is None and values.get("time") is not None:
                values["request_time"] = datetime.fromtimestamp(values["time"])
        except Exception as e:
            print(f"Error converting epoch to datetime: {e} {type(cls)}")
        return values


class Sample(BaseModel):
    uid: UUID
    name: SampleName
    time: float
    create_time: Optional[datetime] = None
    container: UUID | Literal["NULL"]
    position: int | None = None
    owner: str
    kind: str
    proposal_id: Optional[str | int] = Field(..., alias="proposalID")
    model: str
    sequence: Optional[str | int] = None
    request_count: int
    model_config = {"frozen": False}

    @model_validator(mode="before")
    def convert_epoch_to_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            return values
        # Access the fields from the values dictionary
        try:
            if values.get("create_time") is None and values.get("time") is not None:
                values["create_time"] = datetime.fromtimestamp(values["time"])
        except Exception as e:
            print(f"Error converting epoch to datetime: {e} {type(cls)}")
        return values


class AutomatedCollection(BaseModel):
    sample: Sample
    rasters: Dict[UUID, Dict[UUID, Request]]
    standard: Dict[UUID, Request]
    model_config = {"frozen": False}


class ManualCollection(BaseModel):
    sample: Sample
    rasters: Dict[UUID, Request]
    standards: Dict[UUID, Request]
    vectors: Dict[UUID, Request]
    model_config = {"frozen": False}


CollectionType = AutomatedCollection | ManualCollection


class CollectionData(BaseModel):
    sample_collections: dict[SampleName, CollectionType]
    sample_data: dict[SampleName, Sample]
    puck_data: Dict[PuckName, List[SampleName]]
    model_config = {"frozen": False}
    beamline: Optional[str] = None
    proposal: Optional[str] = None
