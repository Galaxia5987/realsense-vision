from app.components.detection.pipelines.pipeline_base import PipelineBase
from app.core import logging_config
from utils.utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)


class RegularPipeline(PipelineBase):
    name = "RegularPipeline"

    def __init__(self, camera):
        super().__init__()
        logger.info("Initializing RegularPipeline", operation="init")
        self.camera = camera
        self.frame = None
        self.depth_frame = None
        logger.info("RegularPipeline initialized", operation="init", status="success")

    def iterate(self):
        """Main processing loop."""
        self.frame = self.camera.latest_frame
        self.depth_frame = self.camera.latest_depth_frame

    def _convert_to_jpeg(self, frame):
        if frame is None:
            return None
        return frames_to_jpeg_bytes(
            frame, resolution=(self.camera.width, self.camera.height)
        )

    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        return self._convert_to_jpeg(self.depth_frame)

    def get_color_jpeg(self):
        """Get JPEG-encoded color frame."""
        return self._convert_to_jpeg(self.frame)
