from typing import Callable
from models.detection_model import Detection
import cv2

def draw_depth_text(img, text, x, y, color=(0, 255, 255)):
    cv2.putText(
        img,
        text,
        (x, y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
    )

def draw_center_dot(img, x, y, color=(0, 255, 255)):
    cv2.circle(img, (x, y), 5, color, -1)

def annotate_detections(img, detections, text_lambda: Callable[[Detection], str]):
    for det in detections:
        cx, cy = det.center.x, det.center.y

        text = text_lambda(det)

        draw_depth_text(img, text, cx, cy)
        draw_center_dot(img, cx, cy)