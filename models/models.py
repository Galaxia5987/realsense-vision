from typing import List
from pydantic import BaseModel, ConfigDict
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
    hole_filling: HoleFillingFilter = HoleFillingFilter()
    spatial: SpatialFilter = SpatialFilter()
    temporal: TemporalFilter = TemporalFilter()


class CameraSettings(BaseModel):
    filters: Filters = Filters()
    fps: int = 15
    resolution: ResolutionEnum = ResolutionEnum.r640x480


class ColorFrame(BaseModel):
    stream_enabled: bool = True


class DepthFrame(BaseModel):
    stream_enabled: bool = True


class NetworkTables(BaseModel):
    server: str = "10.59.87.2"
    table: str = "RealsenseVision"


class Pipeline(BaseModel):
    args: List[str] = []
    type: str = "regular"


class RootConfig(BaseModel):
    camera: CameraSettings = CameraSettings()
    color_frame: ColorFrame = ColorFrame()
    depth_frame: DepthFrame = DepthFrame()
    min_confidence: float = 0.85
    network_tables: NetworkTables = NetworkTables()
    pipeline: Pipeline = Pipeline()
    rknn_chip_type: str = "rk3588"
