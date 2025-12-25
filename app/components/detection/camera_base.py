from __future__ import annotations

from abc import ABC, abstractmethod

from utils.async_loop_base import AsyncLoopBase
from utils.utils import generate_stream_disabled_image

LOOP_INTERVAL = 0.01  # 100 Hz
DISABLED_STREAM_IMAGE = generate_stream_disabled_image()


class CameraBase(AsyncLoopBase, ABC):
    supports_depth = False

    def __init__(self, width=640, height=480, fps=30, frame_timeout_ms=5000):
        super().__init__(LOOP_INTERVAL)
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms

        self._latest_frame = None
        self._latest_depth_frame = None
        self._latest_depth_data = None
        self.frame_count = 0

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if any device is connected."""
        raise NotImplementedError()

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
        return self._latest_depth_frame

    @property
    def latest_depth_data(self):
        """Get the latest raw depth data object."""
        return self._latest_depth_data

    def stop_pipeline(self):
        """Stop the camera gracefully."""
        self.stop_sync()
