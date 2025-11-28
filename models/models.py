from typing import List
from pydantic import BaseModel, Field
from enum import Enum


class ResolutionEnum(str, Enum):
    r640x480 = "640x480"
    r1280x720 = "1280x720"
    r848x640 = "848x640"


class HoleFillingFilter(BaseModel):
    enabled: bool = False


class SpatialFilter(BaseModel):
    enabled: bool = True


class TemporalFilter(BaseModel):
    enabled: bool = True


class Filters(BaseModel):
    hole_filling: HoleFillingFilter
    spatial: SpatialFilter
    temporal: TemporalFilter


class CameraSettings(BaseModel):
    filters: Filters
    fps: int
    resolution: ResolutionEnum


class ColorFrame(BaseModel):
    stream_enabled: bool


class DepthFrame(BaseModel):
    stream_enabled: bool


class NetworkTables(BaseModel):
    server: str
    table: str


class Pipeline(BaseModel):
    args: List[str]
    type: str


class RootConfig(BaseModel):
    camera: CameraSettings
    color_frame: ColorFrame
    depth_frame: DepthFrame
    min_confidence: float
    network_tables: NetworkTables
    pipeline: Pipeline
    rknn_chip_type: str
