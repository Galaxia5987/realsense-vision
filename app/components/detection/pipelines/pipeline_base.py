from abc import abstractmethod

from app.components.detection.camera import RealSenseCamera
from models.models import Pipeline

# Registry dictionary
PIPELINE_REGISTRY: dict[str, type] = {}

class PipelineBase:
    def __init_subclass__(cls, **kwargs):
            """Automatically register subclasses by their 'name' property."""
            super().__init_subclass__(**kwargs)
            if hasattr(cls, "name") and isinstance(cls.name, str):
                PIPELINE_REGISTRY[cls.name] = cls

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the pipeline"""
        pass

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

def create_pipeline_by_name(pipeline: Pipeline, camera: RealSenseCamera) -> PipelineBase | None:
    cls = PIPELINE_REGISTRY.get(pipeline.type)
    if cls:
        return cls(pipeline.type, camera, *pipeline.args)
    return None