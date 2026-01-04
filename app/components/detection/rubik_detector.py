import time
import numpy as np
import cv2
from dataclasses import dataclass
from typing import List

try:
    from tensorflow.lite.python.interpreter import Interpreter
    from tensorflow.lite.python.interpreter import load_delegate
except ImportError:
    from tflite_runtime.interpreter import Interpreter, load_delegate


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
    if dtype == np.uint8:
        return (float(data[idx]) - zero_point) * scale
    return float(data[idx])


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


class RubikDetector:
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

    def is_quantized(self) -> bool:
        return self.input_details[0]["dtype"] == np.uint8

    def detect(self, image_bgr: np.ndarray, box_thresh=0.25, nms_thresh=0.45):
        input_info = self.input_details[0]
        _, h, w, c = input_info["shape"]

        if image_bgr.shape[:2] != (h, w):
            raise ValueError("Input image size mismatch")

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

        boxes = self.interpreter.get_tensor(self.output_details[0]["index"])
        scores = self.interpreter.get_tensor(self.output_details[1]["index"])
        classes = self.interpreter.get_tensor(self.output_details[2]["index"])

        box_q = self.output_details[0].get("quantization", (0.0, 0))
        score_q = self.output_details[1].get("quantization", (0.0, 0))

        box_scale, box_zp = box_q
        score_scale, score_zp = score_q

        num_boxes = boxes.shape[1]
        results = []

        for i in range(num_boxes):
            score = dequant_value(
                scores[0], i, score_zp, score_scale, scores.dtype
            )
            if score < box_thresh:
                continue

            x1 = dequant_value(boxes[0], i * 4 + 0, box_zp, box_scale, boxes.dtype)
            y1 = dequant_value(boxes[0], i * 4 + 1, box_zp, box_scale, boxes.dtype)
            x2 = dequant_value(boxes[0], i * 4 + 2, box_zp, box_scale, boxes.dtype)
            y2 = dequant_value(boxes[0], i * 4 + 3, box_zp, box_scale, boxes.dtype)

            x1 = np.clip(x1, 0, w)
            y1 = np.clip(y1, 0, h)
            x2 = np.clip(x2, 0, w)
            y2 = np.clip(y2, 0, h)

            if x1 >= x2 or y1 >= y2:
                continue

            results.append(
                DetectResult(
                    id=int(classes[0][i]),
                    obj_conf=float(score),
                    box=BoxRect(
                        left=int(round(x1)),
                        top=int(round(y1)),
                        right=int(round(x2)),
                        bottom=int(round(y2)),
                    ),
                )
            )

        return optimized_nms(results, nms_thresh)
