from ultralytics import YOLO

import app.core.logging_config as logging_config
from app.config import ConfigManager

logger = logging_config.get_logger(__name__)


class YOLODetector:
    def __init__(self, model_path, imgsz=640):
        logger.info(
            f"Initializing YOLO detector with model: {model_path}", operation="init"
        )

        self.model = YOLO(model_path, task="detect")
        self.imgsz = imgsz
        self.results = None
        self.detection_count = 0

        logger.info(
            f"YOLO detector initialized successfully (imgsz={imgsz})",
            operation="init",
            status="success",
        )

    def detect(self, image):
        """Run detection on an image"""
        if image is None:
            logger.warning("Received None image for detection", operation="detect")
            return

        self.results = self.model(
            image, imgsz=self.imgsz, conf=ConfigManager().get().min_confidence
        )[0]

        self.detection_count += 1

        # Log periodically
        if self.detection_count % 100 == 0:
            logger.debug(
                f"Processed {self.detection_count} detections", operation="detect"
            )

    def get_annotated_image(self):
        """Get annotated image with detections."""
        try:
            if self.results is None:
                return None
            return self.results.plot()
        except Exception as e:
            logger.error(
                f"Error plotting annotations: {e}", operation="get_annotated_image"
            )
            return None

    def get_detections(self):
        """Get detection results as numpy arrays."""
        try:
            if self.results is None:
                logger.warning("No results available", operation="get_detections")
                return None

            return (
                self.results.boxes.xyxy.cpu().numpy(),
                self.results.boxes.conf.cpu().numpy(),
                self.results.boxes.cls.cpu().numpy(),
            )
        except Exception as e:
            logger.error(
                f"Error extracting detections: {e}", operation="get_detections"
            )
            return None
