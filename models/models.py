from enum import Enum
from typing import List

from pydantic import BaseModel


class ResolutionEnum(str, Enum):
    r640x480 = "640x480"
    r1280x720 = "1280x720"
    r848x640 = "848x640"


class HoleFillingFilter(BaseModel):
    enabled: bool


class SpatialFilter(BaseModel):
    enabled: bool


class TemporalFilter(BaseModel):
    enabled: bool


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
    args: list[str]
    type: str


class RootConfig(BaseModel):
    camera: CameraSettings
    color_frame: ColorFrame
    depth_frame: DepthFrame
    image_size: int
    min_confidence: float
    network_tables: NetworkTables
    pipeline: Pipeline
    rknn_chip_type: str


# Default configuration instance
default_config = RootConfig(
    camera=CameraSettings(
        filters=Filters(
            hole_filling=HoleFillingFilter(enabled=False),
            spatial=SpatialFilter(enabled=True),
            temporal=TemporalFilter(enabled=True),
        ),
        fps=15,
        resolution=ResolutionEnum.r640x480,
    ),
    color_frame=ColorFrame(stream_enabled=True),
    depth_frame=DepthFrame(stream_enabled=True),
    image_size=640,
    min_confidence=0.85,
    network_tables=NetworkTables(server="10.59.87.2", table="AdvantageKit/RealsenseVision"),
    pipeline=Pipeline(args=[], type="regular"),
    rknn_chip_type="rk3588",
)
