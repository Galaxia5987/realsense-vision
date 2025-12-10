from enum import Enum, auto
import time
from pathlib import Path

import numpy as np
import pyrealsense2 as rs

import app.core.logging_config as logging_config
from app.config import ConfigManager
from utils.async_loop_base import AsyncLoopBase
from utils.utils import generate_stream_disabled_image

logger = logging_config.get_logger(__name__)
DISABLED_STREAM_IMAGE = (
    generate_stream_disabled_image()
)  # an image with the text "Stream Disabled"

LOOP_INTERVAL = 0.01  # 100 Hz

class StreamType(Enum):
    RGB = auto()
    INFRARED = auto()

class RealSenseCamera(AsyncLoopBase):
    def __init__(self, width=640, height=480, fps=30, frame_timeout_ms=5000, stream_type: StreamType = StreamType.RGB):
        super().__init__(LOOP_INTERVAL)
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms
        self.stream_type = stream_type
        self._depth_scale = 1.0
        self._camera_intrinsics = [1.0,1.0,1.0,1.0]
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

    @property
    def depth_scale(self):
        return self._depth_scale
    
    @property 
    def camera_intrinsics(self):
        return self._camera_intrinsics

    def is_connected(self) -> bool:
        """Check if any device is connected"""
        try:
            ctx = rs.context()
            devices = ctx.query_devices()
            return len(devices) > 0
        except Exception:
            return False

    def _load_config_onto_device(self, device, file: Path = Path("camera_config.json")):
        """
        Load JSON config onto the device BEFORE pipeline start.
        """
        try:
            json_content = file.read_text()

            advnc_mode = rs.rs400_advanced_mode(device)
            advnc_mode.load_json(json_content)
            logger.info(f"Loaded configuration from {file}", operation="init")

        except FileNotFoundError:
            logger.warning(
                f"Config file {file} not found. Using camera defaults.",
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
        logger.debug("Initializing RealSense pipeline sequence", operation="init_pipeline")

        ctx = rs.context()
        devices = ctx.query_devices()
        if not devices:
            raise RuntimeError("Lost device after reset sequence.")

        self.pipeline = rs.pipeline()
        rs_config = rs.config()

        logger.debug(
            f"Configuring streams: {self.width}x{self.height} @ {self.fps}fps",
            operation="init_pipeline",
        )

        # Color vs Infrared selection
        if self.stream_type == StreamType.RGB:
            rs_config.enable_stream(
                rs.stream.color,
                self.width,
                self.height,
                rs.format.bgr8,
                self.fps,
            )
            # Depth gets aligned to color
            self.align = rs.align(rs.stream.color)

        elif self.stream_type == StreamType.INFRARED:
            # Infrared stream index 1 is the standard "left" IR image
            rs_config.enable_stream(
                rs.stream.infrared,
                1,
                self.width,
                self.height,
                rs.format.y8,
                self.fps,
            )
            # No align needed, IR is already in depth frame coordinates
            self.align = None

        # Depth always enabled
        rs_config.enable_stream(
            rs.stream.depth,
            self.width,
            self.height,
            rs.format.z16,
            self.fps,
        )

        # Init filters
        self._setup_filters()

        logger.info("Starting RealSense pipeline...", operation="init_pipeline")

        try:
            profile = self.pipeline.start(rs_config)
            time.sleep(1)

            # Sensor config
            depth_sensor = profile.get_device().first_depth_sensor()

            try:
                depth_sensor.set_option(rs.option.visual_preset, 1)
                depth_sensor.set_option(rs.option.laser_power, 360)

                # When using IR, disable emitter for a cleaner IR frame
                if self.stream_type == StreamType.INFRARED:
                    depth_sensor.set_option(rs.option.emitter_enabled, 0.0)

            except Exception as e:
                logger.error(f"Error applying preset configs: {e}", exc_info=True)

            # Depth scale
            self._depth_scale = depth_sensor.get_depth_scale()

            # Extract intrinsics for the chosen stream
            if self.stream_type == StreamType.RGB:
                stream = profile.get_stream(rs.stream.color)
            else:
                stream = profile.get_stream(rs.stream.infrared, 1)

            intr = stream.as_video_stream_profile().get_intrinsics()
            self._camera_intrinsics = [intr.fx, intr.fy, intr.ppx, intr.ppy]

            # Warmup
            for _ in range(5):
                self.pipeline.wait_for_frames(timeout_ms=1000)

            logger.info("RealSense pipeline started and warmed up.", operation="init_pipeline")

        except RuntimeError as e:
            if "device is busy" in str(e).lower():
                logger.error("Device Busy: another process uses the camera or USB problem.")
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
            frames = self.pipeline.wait_for_frames(timeout_ms=self.frame_timeout_ms)

            # Select frame source
            if self.stream_type == StreamType.RGB:
                # Align depth to color frames
                aligned = self.align.process(frames)
                color_frame = aligned.get_color_frame()
                depth_frame = aligned.get_depth_frame()

                if not color_frame or not depth_frame:
                    logger.debug("RGB mode incomplete frame")
                    return

                frame_image = np.asanyarray(color_frame.get_data())

            else:
                # IR mode: no align, raw IR + raw depth
                ir_frame = frames.get_infrared_frame(1)
                depth_frame = frames.get_depth_frame()

                if not ir_frame or not depth_frame:
                    logger.debug("IR mode incomplete frame")
                    return

                # IR is grayscale, 8 bit
                frame_image = np.asanyarray(ir_frame.get_data())

            # Apply filters to depth
            for f in (self.spatial, self.temporal, self.hole_filling):
                if f:
                    depth_frame = f.process(depth_frame)

            # Store data
            self._latest_frame = frame_image
            self._latest_depth_data = depth_frame.as_depth_frame()

            self.frame_count += 1

        except RuntimeError as e:
            logger.warning(f"Frame timeout or RS error: {e}", operation="loop")
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
        if self._latest_depth_data is None:
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
