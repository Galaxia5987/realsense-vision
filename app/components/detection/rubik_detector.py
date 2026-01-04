import time
import numpy as np
import cv2
from dataclasses import dataclass
from typing import List
from app.core import logging_config
from app.components.detection.detector_base import DetectorBase

try:
    from tensorflow.lite.python.interpreter import Interpreter
    from tensorflow.lite.python.interpreter import load_delegate
except ImportError:
    from tflite_runtime.interpreter import Interpreter, load_delegate

logger = logging_config.get_logger(__name__)

@dataclass
class BoxRect:
    left: int
    top: int
    right: int
    bottom: int


@dataclass
class DetectResult:
    id: int
    box: BoxRect
    obj_conf: float


def dequant_value(data, idx, zero_point, scale, dtype):
    value = data.flatten()[idx]
    
    if dtype == np.uint8:
        return (float(value) - zero_point) * scale
    return float(value)


def calculate_iou(a: BoxRect, b: BoxRect) -> float:
    x1 = max(a.left, b.left)
    y1 = max(a.top, b.top)
    x2 = min(a.right, b.right)
    y2 = min(a.bottom, b.bottom)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    inter = (x2 - x1) * (y2 - y1)
    area1 = (a.right - a.left) * (a.bottom - a.top)
    area2 = (b.right - b.left) * (b.bottom - b.top)

    return inter / float(area1 + area2 - inter)


def optimized_nms(candidates: List[DetectResult], threshold: float):
    if not candidates:
        return []

    candidates.sort(key=lambda d: d.obj_conf, reverse=True)
    suppressed = [False] * len(candidates)
    results = []

    for i, det in enumerate(candidates):
        if suppressed[i]:
            continue

        results.append(det)

        for j in range(i + 1, len(candidates)):
            if suppressed[j]:
                continue
            if candidates[j].id != det.id:
                continue

            if calculate_iou(det.box, candidates[j].box) > threshold:
                suppressed[j] = True

    return results


class RubikDetector(DetectorBase):
    def __init__(self, model_path: str):
        delegates = []

        try:
            delegates.append(
                load_delegate(
                    "libQnnTFLiteDelegate.so",
                    {
                        "backend_type": "htp",
                        "htp_use_conv_hmx": "1",
                        "htp_performance_mode": "2",
                    },
                )
            )
            print("INFO: QNN delegate loaded")
        except Exception as e:
            print("WARNING: Delegate not loaded:", e)

        self.interpreter = Interpreter(
            model_path=model_path,
            experimental_delegates=delegates if delegates else None,
        )

        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self._last_results: list[DetectResult] | None = None
        self._last_image = None

    def is_quantized(self) -> bool:
        return self.input_details[0]["dtype"] == np.uint8

    def detect(self, image_bgr: np.ndarray, box_thresh=0.25, nms_thresh=0.45):
        input_info = self.input_details[0]
        _, h, w, c = input_info["shape"]
        image_bgr = cv2.resize(image_bgr, (h, w))
        self._last_image = image_bgr.copy()

        if image_bgr.shape[:2] != (h, w):
            raise ValueError(f"Input image size mismatch, expected {w},{h} but got {image_bgr.shape[:2]}")

        if image_bgr.shape[2] != 3:
            raise ValueError("Expected 3-channel image")

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        if self.is_quantized():
            input_tensor = rgb.astype(np.uint8)
        else:
            input_tensor = rgb.astype(np.float32) / 255.0

        input_tensor = np.expand_dims(input_tensor, axis=0)
        self.interpreter.set_tensor(input_info["index"], input_tensor)

        start = time.monotonic()
        self.interpreter.invoke()
        elapsed = (time.monotonic() - start) * 1000.0
        print(f"INFO: Inference time {elapsed:.2f} ms")

        boxes = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
        scores = self.interpreter.get_tensor(self.output_details[1]["index"])[0]
        classes = self.interpreter.get_tensor(self.output_details[2]["index"])[0]

        # Flatten boxes if needed
        boxes_flat = boxes.ravel()
        
        # Dequantize ALL values at once
        if scores.dtype == np.uint8:
            score_scale, score_zp = self.output_details[1].get("quantization", (1.0, 0))
            scores = (scores.astype(np.float32) - score_zp) * score_scale
        
        if boxes.dtype == np.uint8:
            box_scale, box_zp = self.output_details[0].get("quantization", (1.0, 0))
            boxes_flat = (boxes_flat.astype(np.float32) - box_zp) * box_scale
        
        # Determine number of boxes
        num_boxes = len(scores)
        
        # Filter by threshold
        mask = scores >= box_thresh
        
        results = []
        for i in np.where(mask)[0]:
            x1, y1, x2, y2 = boxes_flat[i * 4 : i * 4 + 4]
            
            x1 = np.clip(x1, 0, w)
            y1 = np.clip(y1, 0, h)
            x2 = np.clip(x2, 0, w)
            y2 = np.clip(y2, 0, h)
            
            if x1 >= x2 or y1 >= y2:
                continue
            
            results.append(
                DetectResult(
                    id=int(classes[i]),
                    obj_conf=float(scores[i]),
                    box=BoxRect(
                        left=int(round(x1)),
                        top=int(round(y1)),
                        right=int(round(x2)),
                        bottom=int(round(y2)),
                    )
                )
            )
        
        self._last_results = optimized_nms(results, nms_thresh)
        return self._last_results

    def get_detections(self):
        if not self._last_results:
            return None

        boxes = np.array(
            [
                [det.box.left, det.box.top, det.box.right, det.box.bottom]
                for det in self._last_results
            ],
            dtype=np.float32,
        )
        confs = np.array([det.obj_conf for det in self._last_results], dtype=np.float32)
        classes = np.array([det.id for det in self._last_results], dtype=np.int32)
        return boxes, confs, classes

    def get_annotated_image(self):
        if self._last_image is None or not self._last_results:
            return None

        annotated = self._last_image.copy()
        for det in self._last_results:
            box = det.box
            cv2.rectangle(
                annotated,
                (box.left, box.top),
                (box.right, box.bottom),
                (0, 255, 0),
                2,
            )
            label = f"{det.id}:{det.obj_conf:.2f}"
            cv2.putText(
                annotated,
                label,
                (box.left, max(box.top - 6, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        return annotated
