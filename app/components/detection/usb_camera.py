import time

import cv2

import app.core.logging_config as logging_config
from app.components.detection.camera_base import CameraBase
from app.config import ConfigManager

logger = logging_config.get_logger(__name__)


class UsbCamera(CameraBase):
    supports_depth = False

    def __init__(
        self, width=640, height=480, fps=30, device_index=0, frame_timeout_ms=5000
    ):
        super().__init__(width, height, fps, frame_timeout_ms)
        self.device_index = device_index
        self.capture = None
        self._last_connect_attempt = 0.0
        self._last_exposure_settings = None
        self._last_exposure_apply = 0.0

        self._initialize_capture()
        logger.info(
            f"UsbCamera created with resolution {width}x{height} @ {fps}fps",
            operation="init",
        )

    def _initialize_capture(self):
        self._last_connect_attempt = time.time()
        self.capture = cv2.VideoCapture(self.device_index)
        if not self.capture.isOpened():
            logger.warning(
                f"USB camera index {self.device_index} failed to open.",
                operation="init",
            )
            return

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.fps)

        logger.info(
            f"USB camera index {self.device_index} opened.",
            operation="init",
        )

    def is_connected(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

    def on_iteration(self):
        if not self.is_connected():
            if time.time() - self._last_connect_attempt > 2:
                self._initialize_capture()
            time.sleep(1)
            return

        self._apply_exposure_settings()

        ok, frame = self.capture.read()
        if not ok or frame is None:
            logger.warning("Failed to read frame from USB camera", operation="loop")
            return

        self._latest_frame = frame
        self.frame_count += 1

    def _apply_exposure_settings(self):
        if not self.capture:
            return

        now = time.time()
        if now - self._last_exposure_apply < 0.5:
            return

        camera_config = ConfigManager().get().camera
        settings = (camera_config.auto_exposure, camera_config.exposure)
        if settings == self._last_exposure_settings:
            return

        try:
            if camera_config.auto_exposure:
                self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
            else:
                self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self.capture.set(cv2.CAP_PROP_EXPOSURE, float(camera_config.exposure))
            self._last_exposure_settings = settings
            self._last_exposure_apply = now
        except Exception as e:
            logger.warning(f"Failed to apply exposure settings: {e}", operation="loop")

    def stop_pipeline(self):
        super().stop_pipeline()

        if self.capture:
            try:
                self.capture.release()
            except Exception as e:
                logger.warning(f"Error releasing USB camera: {e}", operation="stop")
            finally:
                self.capture = None

        logger.info("USB camera stopped", operation="stop", status="success")
