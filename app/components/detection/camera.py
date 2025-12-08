import time
from pathlib import Path

import numpy as np
import pyrealsense2 as rs

import app.core.logging_config as logging_config
from app.config import ConfigManager
from utils import generate_stream_disabled_image
from async_loop_base import AsyncLoopBase

logger = logging_config.get_logger(__name__)
DISABLED_STREAM_IMAGE = (
    generate_stream_disabled_image()
)  # an image with the text "Stream Disabled"

LOOP_INTERVAL = 0.01  # 100 Hz


class RealSenseCamera(AsyncLoopBase):
    def __init__(self, width=640, height=480, fps=30, frame_timeout_ms=5000):
        super().__init__(LOOP_INTERVAL)
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms
        self.config = ConfigManager().get()

        # State variables
        self.pipeline = None
        self.align = None
        self._latest_frame = None
        self._latest_depth_frame = None
        self._latest_depth_data = None
        self.frame_count = 0

        # Filter placeholders
        self.spatial = None
        self.temporal = None
        self.hole_filling = None

        # Attempt initialization
        try:
            if self.is_connected():
                self._initialize_pipeline()
            else:
                logger.warning("No RealSense device detected on startup.")
        except Exception as e:
            logger.error(f"Critical error initializing RealSense: {e}", exc_info=True)

        logger.info(
            f"RealSenseCamera created with resolution {width}x{height} @ {fps}fps",
            operation="init",
        )

    def is_connected(self) -> bool:
        """Check if any device is connected"""
        try:
            ctx = rs.context()
            devices = ctx.query_devices()
            return len(devices) > 0
        except Exception:
            return False

    def _load_config_onto_device(self, device, filename="camera_config.json"):
        """
        Load JSON config onto the device BEFORE pipeline start.
        """
        try:
            file = Path(filename)
            json_content = file.read_text()

            advnc_mode = rs.rs400_advanced_mode(device)
            advnc_mode.load_json(json_content)
            logger.info(f"Loaded configuration from {filename}", operation="init")

        except FileNotFoundError:
            logger.warning(
                f"Config file {filename} not found. Using camera defaults.",
                operation="init",
            )
        except Exception as e:
            logger.error(f"Failed to load JSON config: {e}", operation="init")

    def _setup_filters(self):
        """Initialize filters based on app config."""
        camera_config = self.config.camera
        filters_config = camera_config.filters

        if filters_config.spatial.enabled:
            self.spatial = rs.spatial_filter()
            # TODO: Might be needed
            # self.spatial.set_option(rs.option.filter_magnitude, 2)
            # self.spatial.set_option(rs.option.filter_smooth_alpha, 0.5)
            # self.spatial.set_option(rs.option.filter_smooth_delta, 20)

        if filters_config.temporal.enabled:
            self.temporal = rs.temporal_filter()

        if filters_config.hole_filling.enabled:
            self.hole_filling = rs.hole_filling_filter()

        logger.debug(
            f"Filters initialized: Spatial={bool(self.spatial)}, Temporal={bool(self.temporal)}",
            operation="init_pipeline",
        )

    def _initialize_pipeline(self):
        """Initialize the RealSense pipeline with proper reset sequence."""
        logger.debug(
            "Initializing RealSense pipeline sequence", operation="init_pipeline"
        )

        ctx = rs.context()
        devices = ctx.query_devices()
        if not devices:
            raise RuntimeError("Lost device after reset sequence.")

        # Configure Pipeline
        self.pipeline = rs.pipeline()
        rs_config = rs.config()

        logger.debug(
            f"Configuring streams: {self.width}x{self.height} @ {self.fps}fps",
            operation="init_pipeline",
        )
        rs_config.enable_stream(
            rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps
        )
        rs_config.enable_stream(
            rs.stream.depth, self.width, self.height, rs.format.z16, self.fps
        )

        # Initialize helper objects
        self.align = rs.align(rs.stream.color)
        self._setup_filters()

        # Start Pipeline
        logger.info("Starting RealSense pipeline...", operation="init_pipeline")
        try:
            profile = self.pipeline.start(rs_config)

            time.sleep(1)

            depth_sensor = profile.get_device().first_depth_sensor()
            try:
                depth_sensor.set_option(rs.option.visual_preset, 1)
                depth_sensor.set_option(rs.option.laser_power, 360)
            except Exception as e:
                logger.error(
                    f"Exception while loading preset config onto camera: {e}",
                    exc_info=True,
                )

            logger.info("Loading preset config onto camera...")

            # Warmup: Discard first few frames to allow auto-exposure to settle
            for _ in range(5):
                self.pipeline.wait_for_frames(timeout_ms=1000)

            logger.info(
                "RealSense pipeline started and warmed up.",
                operation="init_pipeline",
                status="success",
            )

        except RuntimeError as e:
            if "device is busy" in str(e).lower():
                logger.error(
                    "Device Busy: Check if another process is using the camera or if USB cable is loose."
                )
            raise e

    def on_iteration(self):
        """
        Main loop iteration.
        Wrapped in try/except to prevent loop crash on single frame failure.
        """
        if self.pipeline is None:
            time.sleep(1)  # Wait before retrying if pipeline died
            return

        try:
            # 1. Wait for frames
            frames = self.pipeline.wait_for_frames(timeout_ms=self.frame_timeout_ms)

            # 2. Align Depth to Color
            aligned_frames = self.align.process(frames)
            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()

            if not depth_frame or not color_frame:
                logger.debug("Frames dropped/incomplete")
                return

            # 3. Apply Filters
            for filter in (self.spatial, self.temporal, self.hole_filling):
                if filter:
                    depth_frame = filter.process(depth_frame)

            # 4. Process Data
            self._latest_frame = np.asanyarray(color_frame.get_data())
            self._latest_depth_data = depth_frame.as_depth_frame()

            self.frame_count += 1

        except RuntimeError as e:
            logger.warning(f"Frame polling timeout or error: {e}", operation="loop")
        except Exception as e:
            logger.error(f"Error in camera loop: {e}", operation="loop")

    @property
    def latest_frame(self):
        """Get the latest color frame."""
        if self._latest_frame is None:
            return DISABLED_STREAM_IMAGE
        return self._latest_frame

    @property
    def latest_depth_frame(self):
        """Get the latest visualized depth frame."""
        if self._latest_depth_frame is None:
            return DISABLED_STREAM_IMAGE
        
        # Create visual depth map
        color_map = rs.colorizer()
        colorized_depth = color_map.process(self._latest_depth_data)
        self._latest_depth_frame = np.asanyarray(colorized_depth.get_data()).astype(
            np.uint8
        )

        return self._latest_depth_frame

    @property
    def latest_depth_data(self):
        """Get the latest raw depth data object."""
        return self._latest_depth_data

    def stop_pipeline(self):
        """Stop the camera gracefully."""
        super().stop_sync()

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
            f"Camera update loop stopped (frames: {self.frame_count})",
            operation="update_loop",
        )
