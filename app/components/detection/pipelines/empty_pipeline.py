import time
from app.components.detection.pipelines.pipeline_base import PipelineBase
from app.components.detection.realsense_camera import DISABLED_STREAM_IMAGE
from app.core import logging_config
from utils.utils import EmptyModel, frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)

class EmptyPipeline(PipelineBase):
    name = "EmptyPipeline"
    props = EmptyModel

    def __init__(self, camera):
        super().__init__()
        logger.info("Initializing RegularPipeline", operation="init")
        self.camera = camera
        logger.info("RegularPipeline initialized", operation="init", status="success")

    def iterate(self):
        """Main processing loop."""
        time.sleep(0.09)

    def _convert_to_jpeg(self, frame):
        if frame is None:
            return None
        return frames_to_jpeg_bytes(
            frame, resolution=(self.camera.width, self.camera.height)
        )

    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        return self._convert_to_jpeg(DISABLED_STREAM_IMAGE)

    def get_color_jpeg(self):
        """Get JPEG-encoded color frame."""
        return self._convert_to_jpeg(DISABLED_STREAM_IMAGE)
