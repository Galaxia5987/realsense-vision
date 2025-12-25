from enum import Enum

from typing import Any

from pydantic import BaseModel

class ResolutionEnum(str, Enum):
    r640x480 = "640x480"
    r1280x720 = "1280x720"
    r848x640 = "848x640"


class CameraType(str, Enum):
    realsense = "realsense"
    usb = "usb"


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
    type: CameraType = CameraType.realsense
    usb_device_index: int = 0


class ColorFrame(BaseModel):
    stream_enabled: bool


class DepthFrame(BaseModel):
    stream_enabled: bool


class NetworkTables(BaseModel):
    server: str
    table: str


class Pipeline(BaseModel):
    # Properties vary per pipeline; store as plain dict so validation doesn't try to
    # instantiate BaseModel directly (which pydantic forbids).
    properties: dict[str, Any] | None = None
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
        fps=25,
        resolution=ResolutionEnum.r640x480,
        type=CameraType.realsense,
        usb_device_index=0,
    ),
    color_frame=ColorFrame(stream_enabled=True),
    depth_frame=DepthFrame(stream_enabled=True),
    image_size=640,
    min_confidence=0.85,
    network_tables=NetworkTables(
        server="10.59.87.2", table="AdvantageKit/RealsenseVision"
    ),
    pipeline=Pipeline(type="RegularPipeline"),
    rknn_chip_type="rk3588",
)
