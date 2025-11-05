import threading
from utils import generate_stream_disabled_image, frames_to_jpeg_bytes, fail_restart
from config import config
import logging_config
from retry_utils import safe_call

logger = logging_config.get_logger(__name__)
disabled_jpeg = frames_to_jpeg_bytes(generate_stream_disabled_image())

class PipelineRunner:
    def __init__(self, pipeline_type, camera, args=[], set_output_callback=None):
        logger.info(
            f"Initializing pipeline runner with {pipeline_type.__name__}",
            operation="init"
        )
        
        try:
            self.pipeline_type = pipeline_type
            self.args = args
            self.camera = camera
            self.set_output_callback = set_output_callback
            self.stop_event = threading.Event()
            self.running = False
            self.error_count = 0
            self.loop_count = 0
            
            self.thread = threading.Thread(target=self.loop, daemon=True)
            self.thread.start()
            self.running = True
            
            logger.info(
                "Pipeline runner initialized successfully",
                operation="init", status="success"
            )
        except Exception as e:
            logger.exception(
                f"Exception while initializing pipeline: {e}",
                operation="init"
            )
            # fail_restart()
            raise Exception("Exception while initializing pipeline: " + str(e))
    

    def loop(self):
        """
        Main pipeline processing loop with error handling.
        
        Note: This runs as a daemon thread, which is appropriate because:
        - The pipeline should run continuously while the app is running
        - The stop() method provides graceful shutdown via stop_event
        - Resources are cleaned up in the finally block
        """
        logger.info("Pipeline loop started", operation="loop")
        
        try:
            logger.debug(
                f"Creating pipeline instance: {self.pipeline_type.__name__}",
                operation="loop"
            )
            self.pipeline = self.pipeline_type(self.camera, *self.args)
            logger.info("Pipeline instance created", operation="loop", status="success")
            
            consecutive_errors = 0
            max_consecutive_errors = 10
            
            while not self.stop_event.is_set():
                try:
                    self.pipeline.loop()
                    
                    if self.set_output_callback and hasattr(self.pipeline, 'get_output'):
                        output = self.pipeline.get_output()
                        if output is not None:
                            safe_call(
                                self.set_output_callback,
                                operation_name="output_callback",
                                args=(output,)
                            )
                    
                    # Reset consecutive errors on success
                    if consecutive_errors > 0:
                        logger.info(
                            f"Pipeline recovered from {consecutive_errors} consecutive errors",
                            operation="loop", status="recovered"
                        )
                        consecutive_errors = 0
                    
                    self.loop_count += 1
                    
                    # Log periodically
                    if self.loop_count % 300 == 0:
                        logger.debug(
                            f"Pipeline processed {self.loop_count} iterations",
                            operation="loop"
                        )
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.error_count += 1
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(
                            f"Pipeline failed after {max_consecutive_errors} consecutive errors",
                            operation="loop", status="failed"
                        )
                        logger.exception(str(e), operation="loop")
                        break
                    else:
                        logger.warning(
                            f"Error in pipeline loop (consecutive: {consecutive_errors}): {e}",
                            operation="loop"
                        )
                        
        except Exception as e:
            logger.exception(
                f"Fatal exception in pipeline loop: {e}",
                operation="loop"
            )
            # fail_restart()
            raise Exception("Exception while on pipeline loop: " + str(e))
        finally:
            self.running = False
            logger.info(
                f"Pipeline loop stopped (iterations: {self.loop_count}, errors: {self.error_count})",
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
        if config.get_config().get("color_frame", {}).get("stream", {}).get("enabled", False):
            return safe_call(
                lambda: self.pipeline.get_jpeg() if hasattr(self, 'pipeline') else disabled_jpeg,
                default=disabled_jpeg,
                operation_name="get_jpeg"
            )
        else:
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