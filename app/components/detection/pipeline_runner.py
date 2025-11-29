from typing import Callable
from app.components.detection.pipelines.pipeline_base import PipelineBase
from utils import AsyncLoopBase, generate_stream_disabled_image, frames_to_jpeg_bytes
from app.config import ConfigManager
import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)

""" Retarded JPEG """
disabled_jpeg = frames_to_jpeg_bytes(generate_stream_disabled_image())

LOOP_INTERVAL = 0.1

class PipelineRunner(AsyncLoopBase):
    def __init__(self, pipeline: PipelineBase, set_output_callback: Callable):
        super().__init__(LOOP_INTERVAL)
        logger.info(
            f"Initializing pipeline runner with {pipeline.name}",
            operation="init"
        )

        self.config = ConfigManager().get()
        self.pipeline = pipeline
        self.set_output_callback = set_output_callback
        assert set_output_callback, "set_output callback was empty! "
        
        logger.info(
            "Pipeline runner initialized successfully",
            operation="init", status="success"
        )
    

    def on_iteration(self):
        """
        Main pipeline processing loop with error handling.
        
        Note: This runs as a daemon thread, which is appropriate because:
        - The pipeline should run continuously while the app is running
        - The stop() method provides graceful shutdown via stop_event
        - Resources are cleaned up in the finally block
        """
        logger.info("Pipeline loop started", operation="loop")
        
    
        logger.debug(
            f"Creating pipeline instance: {self.pipeline.name}",
            operation="loop"
        )
        logger.info("Pipeline instance created", operation="loop", status="success")
        
        self.pipeline.iterate()
            
        output = self.pipeline.get_output()
        if output:
            self.set_output_callback(output)

    def get_jpeg(self):
        """Get JPEG-encoded color frame."""
        if ConfigManager().get().color_frame.stream_enabled:
            return self.pipeline.get_jpeg()
        return None
    
    def get_output(self):
        """Get pipeline output. Returns None if using a none depth pipeline!"""
        return self.pipeline.get_output()

    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        if self.config.depth_frame.stream_enabled:
            return self.pipeline.get_depth_jpeg() 
        return None