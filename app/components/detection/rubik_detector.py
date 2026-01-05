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

    def is_quantized(self) -> bool:
        return self.model.is_quantized()

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
        if self._last_image is None:
            return None
        
        if not self._last_results:
            return self._last_image

        # if self._last_image is None or not self._last_results:
            # return None

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
