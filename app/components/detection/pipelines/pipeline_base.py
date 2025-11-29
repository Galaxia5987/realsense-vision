from abc import abstractmethod
from typing import List

from app.components.detection.camera import RealSenseCamera
from models.models import Pipeline

# Registry dictionary
PIPELINE_REGISTRY: dict[str, type] = {}


class PipelineBase:
    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses by their 'name' property."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(getattr(cls, "name"), str):
            PIPELINE_REGISTRY[getattr(cls, "name")] = cls

    @abstractmethod
    def get_jpeg(self) -> bytes | None:
        pass

    @abstractmethod
    def get_depth_jpeg(self) -> bytes | None:
        pass

    def get_output(self):
        return None

    @abstractmethod
    def iterate(self):
        pass


def create_pipeline_by_name(
    pipeline: Pipeline, camera: RealSenseCamera
) -> PipelineBase | None:
    cls = PIPELINE_REGISTRY.get(pipeline.type)
    if cls:
        return cls(camera, *pipeline.args)
    return None


def get_all_pipeline_names() -> List[str]:
    return list(PIPELINE_REGISTRY.keys())
