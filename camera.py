import pyrealsense2 as rs
import numpy as np
import threading
import cv2
from config import config
from utils import generate_stream_disabled_image, fail_restart
import logging

disabled_mat = generate_stream_disabled_image()

class RealSenseCamera:
    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.pipeline = None
        self.thread = None
        self.running = False
        self.latest_frame = None
        self.latest_depth_frame = None
        self.latest_depth_data = None

    def start(self):
        try:
            if self.running:
                return
            self.pipeline = rs.pipeline()
            rs_config = rs.config()
            rs_config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
            rs_config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
            self.align = rs.align(rs.stream.color)
            self.spatial = rs.spatial_filter() if config.get_config().get("camera", {}).get("filters", {}).get("spatial", {}).get("enabled", True) else None
            self.temporal = rs.temporal_filter() if config.get_config().get("camera", {}).get("filters", {}).get("temporal", {}).get("enabled", True) else None
            self.hole_filling = rs.hole_filling_filter() if config.get_config().get("camera", {}).get("filters", {}).get("hole_filling", {}).get("enabled", True) else None
            self.pipeline.start(rs_config)
            depth_sensor = self.pipeline.get_active_profile().get_device().first_depth_sensor()
            depth_sensor.set_option(rs.option.visual_preset, 3)
            self.bad_init = False
            self.stop_event = threading.Event()
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
        except Exception as e:
            self.bad_init = True
            logging.exception("Failed to start RealSense camera: %s", e)
            raise Exception("Failed to start realsense camera")
            # fail_restart()            

    def stop(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.pipeline.stop()
        self.pipeline = None

    def _update_loop(self):

        while not self.stop_event.is_set() and not self.bad_init:
            frames = self.pipeline.wait_for_frames()
            frames = self.align.process(frames)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if self.spatial:
                depth_frame = self.spatial.process(depth_frame)
            if self.temporal:
                depth_frame = self.temporal.process(depth_frame)
            if self.hole_filling:
                depth_frame = self.hole_filling.process(depth_frame)

            if color_frame:
                self.latest_frame = np.asanyarray(color_frame.get_data())
            if depth_frame:
                self.latest_depth_data = depth_frame.as_depth_frame()
                color_map = rs.colorizer()
                colorized_frame = color_map.process(self.latest_depth_data)
                depth_image = np.asanyarray(colorized_frame.get_data()).astype(np.uint8)
                self.latest_depth_frame = depth_image


    def get_latest_frame(self):
        return self.latest_frame if not self.bad_init else disabled_mat

    def get_latest_depth_frame(self):
        return self.latest_depth_frame if not self.bad_init else disabled_mat

    def get_latest_depth_data(self):
        return self.latest_depth_data
