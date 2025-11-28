from components.detection.pipelines.pipeline_base import PipelineBase
from core import logging_config
from utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)

class RegularPipeline(PipelineBase):
    @property
    def name(self) -> str:
        return "RegularPipeline"

    def __init__(self, camera):
        logger.info("Initializing RegularPipeline", operation="init")
        self.camera = camera
        self.frame = None
        logger.info("RegularPipeline initialized", operation="init", status="success")

    def loop(self):
        """Main processing loop."""
        self.frame = self.camera.get_latest_frame()
        self.depth_frame = self.camera.get_latest_depth_frame()
        
    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        if self.depth_frame is None:
            return None
        return frames_to_jpeg_bytes(self.depth_frame, resolution=(self.camera.width, self.camera.height))

    def get_jpeg(self):
        """Get JPEG-encoded color frame."""
        if self.frame is None:
            return None
        return frames_to_jpeg_bytes(self.frame, resolution=(self.camera.width, self.camera.height))
