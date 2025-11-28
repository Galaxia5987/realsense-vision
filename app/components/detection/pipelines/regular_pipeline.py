from components.detection.pipelines.pipeline_base import PipelineBase
from core import logging_config
from utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)

class RegularPipeline(PipelineBase):
    def __init__(self, camera):
        logger.info("Initializing RegularPipeline", operation="init")
        self.camera = camera
        self.frame = None
        logger.info("RegularPipeline initialized", operation="init", status="success")

    def loop(self):
        """Main processing loop."""
        try:
            self.frame = self.camera.get_latest_frame()
            self.depth_frame = self.camera.get_latest_depth_frame()
        except Exception as e:
            logger.error(f"Error in regular pipeline loop: {e}", operation="loop")
        
    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        try:
            if self.depth_frame is None:
                return None
            return frames_to_jpeg_bytes(self.depth_frame, resolution=(self.camera.width, self.camera.height))
        except Exception as e:
            logger.error(f"Error generating depth JPEG: {e}", operation="get_depth_jpeg")
            return None

    def get_jpeg(self):
        """Get JPEG-encoded color frame."""
        try:
            if self.frame is None:
                return None
            return frames_to_jpeg_bytes(self.frame, resolution=(self.camera.width, self.camera.height))
        except Exception as e:
            logger.error(f"Error generating JPEG: {e}", operation="get_jpeg")
            return None
