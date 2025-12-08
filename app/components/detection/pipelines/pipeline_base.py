from __future__ import annotations

from abc import abstractmethod

from app.components.detection.camera import RealSenseCamera
from app.core import logging_config
from models.models import Pipeline

# Registry dictionary
PIPELINE_REGISTRY: dict[str, type[PipelineBase]] = {}
logger = logging_config.get_logger(__name__)


class PipelineBase:
    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses by their 'name' property."""
        super().__init_subclass__(**kwargs)
        try:
            PIPELINE_REGISTRY[getattr(cls,"name")] = cls
        except AttributeError:
            logger.warning(
                f"Pipeline {cls.__name__} doesn't have a name attribute, registering by module __name__"
            )
            PIPELINE_REGISTRY[cls.__name__] = cls

    @abstractmethod
    def get_jpeg(self) -> bytes | None:
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


def create_pipeline_by_name(
    pipeline: Pipeline, camera: RealSenseCamera
) -> PipelineBase | None:
    try:
        cls = PIPELINE_REGISTRY.get(pipeline.type)
        assert cls
        return cls(camera, *pipeline.args)
    except KeyError | AssertionError:
        return None


def get_all_pipeline_names() -> list[str]:
    return list(PIPELINE_REGISTRY.keys())
