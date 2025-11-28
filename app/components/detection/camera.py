import pyrealsense2 as rs
import numpy as np
import threading
import time
from utils import AsyncLoopBase, generate_stream_disabled_image
import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)
disabled_mat = generate_stream_disabled_image()

class RealSenseCamera(AsyncLoopBase):
    def __init__(self, width=640, height=480, fps=30, frame_timeout_ms=1000):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms
        self.pipeline = None
        self.latest_frame = None
        self.latest_depth_frame = None
        self.latest_depth_data = None
        self.frame_count = 0
        
        logger.info(
            f"RealSenseCamera created with resolution {width}x{height} @ {fps}fps (timeout={frame_timeout_ms}ms)",
            operation="init"
        )

    def on_iteration(self):
        pass

    def start(self):
        """Start the camera with retry logic and detailed logging."""
        if self.running:
            logger.warning("Camera already running", operation="start")
            return
        
        logger.info("Starting RealSense camera", operation="start", status="starting")
        
        try:
            self._initialize_pipeline()
            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
            
            logger.info(
                "RealSense camera started successfully",
                operation="start", status="success"
            )
        except Exception as e:
            self.bad_init = True
            self.running = False
            logger.exception(
                f"Failed to start RealSense camera: {e}",
                operation="start"
            )
            raise Exception("Failed to start realsense camera")
    
    def _initialize_pipeline(self):
        """Initialize the RealSense pipeline with filters."""
        logger.debug("Initializing RealSense pipeline", operation="init_pipeline")
        
        # Create pipeline
        self.pipeline = rs.pipeline()
        rs_config = rs.config()
        
        # Configure streams
        logger.debug(
            f"Configuring color stream: {self.width}x{self.height} @ {self.fps}fps",
            operation="init_pipeline"
        )
        rs_config.enable_stream(
            rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps
        )

        logger.debug(
            f"Configuring depth stream: {self.width}x{self.height} @ {self.fps}fps",
            operation="init_pipeline"
        )
        rs_config.enable_stream(
            rs.stream.depth, self.width, self.height, rs.format.z16, self.fps
        )
        
        # Create alignment
        self.align = rs.align(rs.stream.color)
        
        # Configure filters based on config
        camera_config = config.get_config().get("camera", {})
        filters_config = camera_config.get("filters", {})
        
        if filters_config.get("spatial", {}).get("enabled", True):
            self.spatial = rs.spatial_filter()
            logger.debug("Spatial filter enabled", operation="init_pipeline")
        else:
            self.spatial = None
            logger.debug("Spatial filter disabled", operation="init_pipeline")
        
        if filters_config.get("temporal", {}).get("enabled", True):
            self.temporal = rs.temporal_filter()
            logger.debug("Temporal filter enabled", operation="init_pipeline")
        else:
            self.temporal = None
            logger.debug("Temporal filter disabled", operation="init_pipeline")
        
        if filters_config.get("hole_filling", {}).get("enabled", True):
            self.hole_filling = rs.hole_filling_filter()
            logger.debug("Hole filling filter enabled", operation="init_pipeline")
        else:
            self.hole_filling = None
            logger.debug("Hole filling filter disabled", operation="init_pipeline")
        
        # Start pipeline
        logger.debug("Starting RealSense pipeline", operation="init_pipeline")
        self.pipeline.start(rs_config)
        # Configure depth sensor
        try:
            device = self.pipeline.get_active_profile().get_device()
            depth_sensor = device.first_depth_sensor()
            depth_sensor.set_option(rs.option.visual_preset, 3)
            depth_sensor.set_option(rs.option.laser_power, 360)
            logger.debug("Depth sensor configured", operation="init_pipeline")

            with open("camera_config.json", "r") as f: 
                json_camera_config = f.read()
                device.hardware_reset()
                device.load_json(json_camera_config)  # Load settings directly to the live device
        except Exception as e:
            logger.warning(
                f"Failed to configure depth sensor preset: {e}",
                operation="init_pipeline"
            )
        
        logger.info("RealSense pipeline initialized", operation="init_pipeline", status="success")            

    def stop(self):
        """Stop the camera gracefully."""
        if self.stop_event.is_set():
            logger.debug("Camera already stopped", operation="stop")
            return
        
        logger.info("Stopping RealSense camera", operation="stop")
        
        self.running = False
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
            if self.thread.is_alive():
                logger.warning("Camera thread did not stop gracefully", operation="stop")
        
        # Stop pipeline
        if self.pipeline:
            try:
                self.pipeline.stop()
                logger.debug("Pipeline stopped", operation="stop")
            except Exception as e:
                logger.warning(f"Error stopping pipeline: {e}", operation="stop")
            finally:
                self.pipeline = None
        
        logger.info("RealSense camera stopped", operation="stop", status="success")

    def _update_loop(self):
        """
        Main camera frame acquisition loop with error handling.
        
        Note: This runs as a daemon thread, which is appropriate because:
        - The camera should acquire frames continuously while running
        - The stop() method provides graceful shutdown via stop_event
        - Pipeline cleanup is handled in stop()
        """
        logger.info("Camera update loop started", operation="update_loop")
        
        consecutive_errors = 0
        max_consecutive_errors = 10

        while not self.stop_event.is_set() and not self.bad_init:
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=self.frame_timeout_ms)
                frames = self.align.process(frames)
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                
                # Apply filters
                if depth_frame:
                    if self.spatial:
                        depth_frame = self.spatial.process(depth_frame)
                    if self.temporal:
                        depth_frame = self.temporal.process(depth_frame)
                    if self.hole_filling:
                        depth_frame = self.hole_filling.process(depth_frame)

                # Store frames
                if color_frame:
                    self.latest_frame = np.asanyarray(color_frame.get_data())
                if depth_frame:
                    self.latest_depth_data = depth_frame.as_depth_frame()
                    color_map = rs.colorizer()
                    colorized_frame = color_map.process(self.latest_depth_data)
                    depth_image = np.asanyarray(colorized_frame.get_data()).astype(np.uint8)
                    self.latest_depth_frame = depth_image
                
                # Reset error count on success
                if consecutive_errors > 0:
                    logger.info(
                        f"Recovered from {consecutive_errors} consecutive errors",
                        operation="update_loop", status="recovered"
                    )
                    consecutive_errors = 0
                
                self.frame_count += 1
                
                # Log frame count periodically
                if self.frame_count % 300 == 0:  # Every ~10 seconds at 30fps
                    logger.debug(
                        f"Processed {self.frame_count} frames",
                        operation="update_loop"
                    )
                
            except Exception as e:
                consecutive_errors += 1
                self.error_count += 1
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        f"Camera failed after {max_consecutive_errors} consecutive errors",
                        operation="update_loop", status="failed"
                    )
                    logger.exception(str(e), operation="update_loop")
                    self.bad_init = True
                    break
                else:
                    logger.warning(
                        f"Error in camera update loop (consecutive: {consecutive_errors}): {e}",
                        operation="update_loop"
                    )
                    # Brief pause before retry
                    time.sleep(0.1)
        
        logger.info(
            f"Camera update loop stopped (frames: {self.frame_count}, errors: {self.error_count})",
            operation="update_loop"
        )


    def get_latest_frame(self):
        """Get the latest color frame."""
        return safe_call(
            lambda: self.latest_frame if not self.bad_init else disabled_mat,
            default=disabled_mat,
            operation_name="get_latest_frame"
        )

    def get_latest_depth_frame(self):
        """Get the latest depth frame."""
        return safe_call(
            lambda: self.latest_depth_frame if not self.bad_init else disabled_mat,
            default=disabled_mat,
            operation_name="get_latest_depth_frame"
        )

    def get_latest_depth_data(self):
        """Get the latest depth data."""
        return safe_call(
            lambda: self.latest_depth_data,
            default=None,
            operation_name="get_latest_depth_data"
        )
    
    def is_healthy(self) -> bool:
        """Check if camera is healthy and operating correctly."""
        return (
            not self.bad_init 
            and self.running 
            and self.thread is not None 
            and self.thread.is_alive()
            and self.latest_frame is not None
        )
