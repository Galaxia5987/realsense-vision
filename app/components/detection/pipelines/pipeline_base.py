from __future__ import annotations

from abc import abstractmethod

from pydantic import BaseModel

from app.components.detection.realsense_camera import RealSenseCamera
from app.core import logging_config
from models.models import Pipeline
from utils.utils import EmptyModel

# Registry dictionary
PIPELINE_REGISTRY: dict[str, type[PipelineBase]] = {}
logger = logging_config.get_logger(__name__)


class PipelineBase:
    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses by their 'name' property."""
        super().__init_subclass__(**kwargs)
        try:
            PIPELINE_REGISTRY[getattr(cls, "name")] = cls
        except AttributeError:
            logger.warning(
                f"Pipeline {cls.__name__} doesn't have a name attribute, registering by module __name__"
            )
            PIPELINE_REGISTRY[cls.__name__] = cls

    @abstractmethod
    def get_color_jpeg(self) -> bytes | None:
        raise NotImplementedError()

    @abstractmethod
    def get_depth_jpeg(self) -> bytes | None:
        raise NotImplementedError()

    @abstractmethod
    def get_output(self) -> object:
        return None

    @abstractmethod
    def iterate(self):
        raise NotImplementedError()

def get_pipeline_type_by_name(pipeline: Pipeline | str) -> type[PipelineBase]:
    name = pipeline if isinstance(pipeline, str) else pipeline.type
    return PIPELINE_REGISTRY[name]

def get_pipeline_properties_by_name(pipeline: Pipeline | str) -> type[BaseModel]:
    try:
        pipe = get_pipeline_type_by_name(pipeline)
        props = getattr(pipe, "props")
        return props
    except KeyError:
        logger.warning(f"No pipeline named {pipeline} found")
        return EmptyModel
    except AttributeError:
        logger.warning(f"{pipeline} has no 'props' attribute")
        return EmptyModel

def create_pipeline_by_name(
    pipeline: Pipeline, camera: RealSenseCamera
) -> PipelineBase | None:
    try:
        cls = get_pipeline_type_by_name(pipeline)
        model = get_pipeline_properties_by_name(pipeline)
        return cls(camera, model.model_validate(pipeline.properties))
    except KeyError:
        return None

def get_all_pipeline_names() -> list[str]:
    return list(PIPELINE_REGISTRY.keys())
