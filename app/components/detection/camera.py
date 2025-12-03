import asyncio
import time
import json
import pyrealsense2 as rs
import numpy as np
from app.config import ConfigManager
from utils import AsyncLoopBase, generate_stream_disabled_image
import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)
disabled_mat = generate_stream_disabled_image()

LOOP_INTERVAL = 0.01  # 100 Hz


class RealSenseCamera(AsyncLoopBase):
    def __init__(self, width=640, height=480, fps=30, frame_timeout_ms=5000):
        # Increased timeout to 5000ms to allow for startup hiccups
        super().__init__(LOOP_INTERVAL)
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms
        self.config = ConfigManager().get()
        
        # State variables
        self.pipeline = None
        self.align = None
        self.latest_frame = None
        self.latest_depth_frame = None
        self.latest_depth_data = None
        self.frame_count = 0

        # Filter placeholders
        self.spatial = None
        self.temporal = None
        self.hole_filling = None

        # Attempt initialization
        try:
            if self.realsense_connected():
                self._initialize_pipeline()
            else:
                logger.warning("No RealSense device detected on startup.")
        except Exception as e:
            logger.error(f"Critical error initializing RealSense: {e}", exc_info=True)

        logger.info(
            f"RealSenseCamera created with resolution {width}x{height} @ {fps}fps",
            operation="init",
        )

    def realsense_connected(self) -> bool:
        """Check if any device is connected without resetting."""
        try:
            ctx = rs.context()
            devices = ctx.query_devices()
            return len(devices) > 0
        except Exception:
            return False

    def _reset_and_wait_for_device(self):
        """
        Resets the device and blocks until it re-enumerates on the USB bus.
        """
        ctx = rs.context()
        devices = ctx.query_devices()
        
        if len(devices) == 0:
            logger.warning("No device found to reset.")
            return

        device = devices[0]
        serial = device.get_info(rs.camera_info.serial_number)
        
        logger.info(f"Issuing Hardware Reset to device {serial}...", operation="init")
        
        try:
            device.hardware_reset()
        except RuntimeError:
            # It is normal for this to throw an error as the device disconnects
            pass

        # Wait for re-enumeration
        logger.info("Waiting for device to re-enumerate...", operation="init")
        found = False
        
        # Try for up to 10 seconds
        for i in range(20):
            time.sleep(0.5)
            ctx = rs.context() # Refresh context
            if len(ctx.query_devices()) > 0:
                found = True
                logger.info("Device re-connected successfully.", operation="init")
                break
        
        if not found:
            raise RuntimeError("Device failed to come back online after reset.")

    def _load_config_onto_device(self, device, filename="camera_config.json"):
        """
        Loads JSON config onto the device BEFORE pipeline start.
        """
        try:
            with open(filename, "r") as f:
                json_content = f.read()
            
            # Validate JSON validity
            json.loads(json_content)

            # adv = rs.rs400_advanced_mode(device)
            # if not adv.is_enabled():
            #     adv.toggle_advanced_mode(True)
            #     time.sleep(1) # Wait for mode toggle
            
            # adv.load_json(json_content)
            advnc_mode = rs.rs400_advanced_mode(device)
            advnc_mode.load_json(json_content)
            logger.info(f"Loaded configuration from {filename}", operation="init")
            
        except FileNotFoundError:
            logger.warning(f"Config file {filename} not found. Using camera defaults.", operation="init")
        except Exception as e:
            logger.error(f"Failed to load JSON config: {e}", operation="init")

    def _setup_filters(self):
        """Initialize filters based on app config."""
        camera_config = self.config.camera
        filters_config = camera_config.filters

        if filters_config.spatial.enabled:
            self.spatial = rs.spatial_filter()
            # Optional: Configure spatial parameters here if needed
            # self.spatial.set_option(rs.option.filter_magnitude, 2)
            # self.spatial.set_option(rs.option.filter_smooth_alpha, 0.5)
            # self.spatial.set_option(rs.option.filter_smooth_delta, 20)

        if filters_config.temporal.enabled:
            self.temporal = rs.temporal_filter()

        if filters_config.hole_filling.enabled:
            self.hole_filling = rs.hole_filling_filter()

        logger.debug(f"Filters initialized: Spatial={bool(self.spatial)}, Temporal={bool(self.temporal)}", operation="init_pipeline")

    def _initialize_pipeline(self):
        """Initialize the RealSense pipeline with proper reset sequence."""
        logger.debug("Initializing RealSense pipeline sequence", operation="init_pipeline")

        # 1. Reset hardware first (clears bad states from previous runs)
        # self._reset_and_wait_for_device()

        # 2. Re-acquire context and device after reset
        ctx = rs.context()
        devices = ctx.query_devices()
        if not devices:
            raise RuntimeError("Lost device after reset sequence.")
        
        active_device = devices[0]
        
        # 3. Load Advanced Mode JSON (must be done before pipeline.start)

        # 4. Configure Pipeline
        self.pipeline = rs.pipeline()
        rs_config = rs.config()

        # Explicitly bind to the device we found
        serial = active_device.get_info(rs.camera_info.serial_number)
        rs_config.enable_device(serial)


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

        # 5. Initialize helper objects
        self.align = rs.align(rs.stream.color)
        self._setup_filters()

        # 6. Start Pipeline
        logger.debug("Starting RealSense pipeline...", operation="init_pipeline")
        try:
            self.pipeline.start(rs_config)

            self._load_config_onto_device(self.pipeline.get_active_profile().get_device(), "camera_config.json")
            
            # Warmup: Discard first few frames to allow auto-exposure to settle
            for _ in range(5):
                self.pipeline.wait_for_frames(timeout_ms=1000)
                
            logger.info("RealSense pipeline started and warmed up.", operation="init_pipeline", status="success")
            
        except RuntimeError as e:
            if "device is busy" in str(e).lower():
                logger.error("Device Busy: Check if another process is using the camera or if USB cable is loose.")
            raise e

    def on_iteration(self):
        """
        Main loop iteration. 
        Wrapped in try/except to prevent loop crash on single frame failure.
        """
        if self.pipeline is None:
            time.sleep(1) # Wait before retrying if pipeline died
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
            if self.spatial:
                depth_frame = self.spatial.process(depth_frame)
            if self.temporal:
                depth_frame = self.temporal.process(depth_frame)
            if self.hole_filling:
                depth_frame = self.hole_filling.process(depth_frame)

            # 4. Process Data
            self.latest_frame = np.asanyarray(color_frame.get_data())
            self.latest_depth_data = depth_frame.as_depth_frame()
            
            # Create visual depth map
            color_map = rs.colorizer()
            colorized_depth = color_map.process(self.latest_depth_data)
            self.latest_depth_frame = np.asanyarray(colorized_depth.get_data()).astype(np.uint8)

            self.frame_count += 1

        except RuntimeError as e:
            logger.warning(f"Frame polling timeout or error: {e}", operation="loop")
        except Exception as e:
            logger.error(f"Unexpected error in camera loop: {e}", operation="loop")

    def get_latest_frame(self):
        """Get the latest color frame."""
        if self.latest_frame is None:
            return disabled_mat
        return self.latest_frame

    def get_latest_depth_frame(self):
        """Get the latest visualized depth frame."""
        if self.latest_depth_frame is None:
            return disabled_mat
        return self.latest_depth_frame

    def get_latest_depth_data(self):
        """Get the latest raw depth data object."""
        return self.latest_depth_data

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