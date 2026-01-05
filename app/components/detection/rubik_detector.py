import time
import numpy as np
import cv2
from dataclasses import dataclass
from typing import List
from app.core import logging_config
from app.components.detection.detector_base import DetectorBase
from utils.utils import frames_to_jpeg_bytes
import rubik_detector as rubik

class RubikPiDetector(DetectorBase):
    def __init__(self, model_path: str):
        self.model = rubik.RubikDetector(model_path, True)
        self.detections: List[rubik.DetectionResult] = []

    def is_quantized(self) -> bool:
        return self.model.is_quantized()

    def detect(self, image: np.ndarray, box_thresh=0.8, nms_thresh=0.45):
        self.last_image = image
        self.detections: List[rubik.DetectionResult] = self.model.detect(image, box_thresh, nms_thresh)
        

    def get_detections(self):
        if not self.detections:
            return None

        boxes = np.array(
            [
                [det.box.left, det.box.top, det.box.right, det.box.bottom]
                for det in self.detections
            ],
            dtype=np.float32,
        )
        confs = np.array([det.confidence for det in self.detections], dtype=np.float32)
        classes = np.array([det.id for det in self.detections], dtype=np.int32)
        return boxes, confs, classes

    def get_annotated_image(self):
        if self.detections is None:
            return None
        
        if not self.detections:
            return self.last_image

        for det in self.detections:
            box = det.box
            cv2.rectangle(
                self.last_image,
                (box.left, box.top),
                (box.right, box.bottom),
                (0, 255, 0),
                2,
            )
            label = f"{det.id}:{det.confidence:.2f}"
            cv2.putText(
                self.last_image,
                label,
                (box.left, max(box.top - 6, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        return self.last_image
