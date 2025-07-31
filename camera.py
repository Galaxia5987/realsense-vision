import pyrealsense2 as rs
import numpy as np
import threading
import cv2
from config import config
from utils import generate_stream_disabled_image
import logging

disabled_mat = generate_stream_disabled_image()

class RealSenseCamera:
    def __init__(self, width=1280, height=720, fps=30):
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

    def stop(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.pipeline.stop()
        self.pipeline = None

    def _update_loop(self):
        MIN_DEPTH = 0
        MAX_DEPTH = 3000

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
                depth_image = np.asanyarray(self.latest_depth_data.get_data())
                if not config.get_config().get("depth_frame", {}).get("stream", {}).get("enabled", True):
                    self.latest_depth_frame = depth_image
                    continue
                depth_clipped = np.clip(depth_image, MIN_DEPTH, MAX_DEPTH)
                normalized = ((depth_clipped - MIN_DEPTH) / (MAX_DEPTH - MIN_DEPTH) * 255).astype(np.uint8)
                hist_eq = cv2.equalizeHist(normalized)
                heatmap = cv2.applyColorMap(hist_eq, cv2.COLORMAP_JET)

                # --- Add depth scale legend bar on top ---
                legend = np.linspace(0, 255, 256, dtype=np.uint8)
                legend = np.tile(legend, (30, 1))
                legend_color = cv2.applyColorMap(legend, cv2.COLORMAP_JET)
                legend_color_resized = cv2.resize(legend_color, (self.width, 30), interpolation=cv2.INTER_NEAREST)

                label_img = np.zeros((30, self.width, 3), dtype=np.uint8)
                tick_positions = [0, 128, 255]
                tick_values = [f"{MIN_DEPTH}mm",f"{(MIN_DEPTH + MAX_DEPTH)//4}mm" ,f"{(MIN_DEPTH + MAX_DEPTH)//2}mm",f"{(MIN_DEPTH + MAX_DEPTH)*3//4}mm", f"{MAX_DEPTH}mm"]
                for pos, val in zip(tick_positions, tick_values):
                    x = int(pos / 255 * self.width)
                    cv2.putText(label_img, val, (x, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

                top_bar = cv2.addWeighted(legend_color_resized, 0.7, label_img, 0.3, 0)
                self.latest_depth_frame = np.vstack((top_bar, heatmap))

    def get_latest_frame(self):
        return self.latest_frame if not self.bad_init else disabled_mat

    def get_latest_depth_frame(self):
        return self.latest_depth_frame if not self.bad_init else disabled_mat

    def get_latest_depth_data(self):
        return self.latest_depth_data
