import asyncio
import pyrealsense2 as rs
from app.config import ConfigManager
import numpy as np
from utils import AsyncLoopBase, generate_stream_disabled_image
import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)
disabled_mat = generate_stream_disabled_image()

LOOP_INTERVAL = 0.1

class RealSenseCamera(AsyncLoopBase):
    def __init__(self, width=640, height=480, fps=30, frame_timeout_ms=1000):
        super().__init__(LOOP_INTERVAL)
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms
        self.config = ConfigManager().get()
        self.pipeline = None
        self.latest_frame = None
        self.latest_depth_frame = None
        self.latest_depth_data = None
        self.frame_count = 0
        if self.realsense_connected():
            self._initialize_pipeline()
        
        logger.info(
            f"RealSenseCamera created with resolution {width}x{height} @ {fps}fps (timeout={frame_timeout_ms}ms)",
            operation="init"
        )

    def realsense_connected(self) -> bool:
        ctx = rs.context()
        devices = ctx.query_devices()
        return len(devices) > 0

    def load_config_onto_device(self, device, filename):
        with open("camera_config.json", "r") as f: 
            json_camera_config = f.read()
            device.hardware_reset()
            device.load_json(json_camera_config)
                
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
        camera_config = self.config.camera
        filters_config = camera_config.filters
        
        self.spatial = None
        self.temporal = None
        self.hole_filling = None
        
        if filters_config.spatial.enabled:
            self.spatial = rs.spatial_filter()
            logger.debug("Spatial filter enabled", operation="init_pipeline")
        
        if filters_config.temporal.enabled:
            self.temporal = rs.temporal_filter()
            logger.debug("Temporal filter enabled", operation="init_pipeline")
        
        if filters_config.hole_filling.enabled:
            self.hole_filling = rs.hole_filling_filter()
            logger.debug("Hole filling filter enabled", operation="init_pipeline")
        
        # Start pipeline
        logger.debug("Starting RealSense pipeline", operation="init_pipeline")
        self.pipeline.start(rs_config)
        # Configure depth sensor

        device = self.pipeline.get_active_profile().get_device()
        self.load_config_onto_device(device, "camera_config.json")

        logger.debug("Depth sensor configured", operation="init_pipeline")
        
        logger.info("RealSense pipeline initialized", operation="init_pipeline", status="success")            

    def on_iteration(self):
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


    def get_latest_frame(self):
        """Get the latest color frame."""
        return self.latest_frame

    def get_latest_depth_frame(self):
        """Get the latest depth frame."""
        return self.latest_depth_frame

    def get_latest_depth_data(self):
        """Get the latest depth data."""
        return self.latest_depth_data

    def stop_pipeline(self):
        """Stop the camera gracefully."""
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(super().stop(), loop)
        
        if self.pipeline:
            try:
                self.pipeline.stop()
                logger.debug("Pipeline stopped", operation="stop")
            except Exception as e:
                logger.warning(f"Error stopping pipeline: {e}", operation="stop")
            finally:
                self.pipeline = None
        
        logger.info("RealSense camera stopped", operation="stop", status="success")
        logger.info(
            f"Camera update loop stopped (frames: {self.frame_count}, errors: {self.error_count})",
            operation="update_loop"
        )