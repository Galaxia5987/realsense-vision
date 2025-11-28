import threading
from utils import AsyncLoopBase, generate_stream_disabled_image, frames_to_jpeg_bytes, fail_restart
from app.config import ConfigManager
import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)
disabled_jpeg = frames_to_jpeg_bytes(generate_stream_disabled_image())

class PipelineRunner(AsyncLoopBase):
    def __init__(self, pipeline_type, camera, set_output_callback, args=[], ):
        
        logger.info(
            f"Initializing pipeline runner with {pipeline_type.__name__}",
            operation="init"
        )

        self.pipeline_type = pipeline_type
        self.args = args
        self.camera = camera
        self.set_output_callback = set_output_callback
        assert set_output_callback, "set_output callback was empty! "

        self.running = False
        self.error_count = 0
        self.loop_count = 0
        
        self.running = True
        
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
            f"Creating pipeline instance: {self.pipeline_type.__name__}",
            operation="loop"
        )
        self.pipeline = self.pipeline_type(self.camera, *self.args)
        logger.info("Pipeline instance created", operation="loop", status="success")
        
        self.pipeline.loop()
            
        if self.set_output_callback and hasattr(self.pipeline, 'get_output'):
            output = self.pipeline.get_output()
            if output is not None:
                self.set_output_callback(output)
                
            self.loop_count += 1
            
            # Log periodically
            if self.loop_count % 300 == 0:
                logger.debug(
                    f"Pipeline processed {self.loop_count} iterations",
                    operation="loop"
                )

    def stop(self):
        """Stop the pipeline gracefully."""
        logger.info("Stopping pipeline runner", operation="stop")
        self.stop_event.set()
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
            if self.thread.is_alive():
                logger.warning("Pipeline thread did not stop gracefully", operation="stop")
        
        logger.info("Pipeline runner stopped", operation="stop", status="success")

    def get_jpeg(self):
        """Get JPEG-encoded color frame."""
        if ConfigManager().get().color_frame.stream_enabled:
            return self.pipeline.get_jpeg()
        return disabled_jpeg
    
    def get_output(self):
        """Get pipeline output."""
        return safe_call(
            lambda: self.pipeline.get_output() if hasattr(self, 'pipeline') else None,
            default=None,
            operation_name="get_output"
        )

    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        if not hasattr(self, 'pipeline'):
            return disabled_jpeg
            
        if hasattr(self.pipeline, 'get_depth_jpeg'):
            if config.get_config().get("depth_frame", {}).get("stream", {}).get("enabled", False):
                return safe_call(
                    self.pipeline.get_depth_jpeg,
                    default=disabled_jpeg,
                    operation_name="get_depth_jpeg"
                )
            else:
                return disabled_jpeg
        return None
    
    def is_healthy(self) -> bool:
        """Check if pipeline runner is healthy."""
        return (
            self.running
            and self.thread is not None
            and self.thread.is_alive()
            and hasattr(self, 'pipeline')
        )