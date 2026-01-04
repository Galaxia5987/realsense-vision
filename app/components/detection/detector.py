import cv2
import numpy as np

import app.core.logging_config as logging_config
from app.config import ConfigManager

logger = logging_config.get_logger(__name__)

try:
    from tflite_runtime.interpreter import Interpreter, load_delegate
except ImportError:  # pragma: no cover - fallback for dev environments
    from tensorflow.lite.python.interpreter import Interpreter, load_delegate


class TFLiteDetector:
    def __init__(self, model_path, imgsz=640):
        logger.info(
            f"Initializing TFLite detector with model: {model_path}", operation="init"
        )

        self.interpreter = Interpreter(model_path=str(model_path), experimental_delegates=[load_delegate("libQnnTFLiteDelegate.so", {"backend_type": "htp"})])
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.input_index = self.input_details[0]["index"]
        input_shape = self.input_details[0]["shape"]
        self.input_height = int(input_shape[1])
        self.input_width = int(input_shape[2])
        self.input_dtype = self.input_details[0]["dtype"]
        self.input_quant = self.input_details[0].get("quantization", (0.0, 0))
        self.imgsz = imgsz
        self.results = None
        self.last_image = None
        self.last_boxes = None
        self.last_scores = None
        self.last_classes = None
        self.detection_count = 0

        logger.info(
            f"TFLite detector initialized successfully (input={self.input_width}x{self.input_height})",
            operation="init",
            status="success",
        )

    def detect(self, image):
        """Run detection on an image"""
        if image is None:
            logger.warning("Received None image for detection", operation="detect")
            return

        self.last_image = image
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_width, self.input_height))
        input_tensor = resized.astype(np.float32)

        if self.input_dtype == np.float32:
            input_tensor = input_tensor / 255.0
        elif self.input_dtype in (np.uint8, np.int8):
            scale, zero_point = self.input_quant
            if scale and scale > 0:
                input_tensor = input_tensor / 255.0
                input_tensor = input_tensor / scale + zero_point
            input_tensor = np.clip(
                input_tensor,
                np.iinfo(self.input_dtype).min,
                np.iinfo(self.input_dtype).max,
            ).astype(self.input_dtype)
        else:
            input_tensor = input_tensor.astype(self.input_dtype)

        input_tensor = np.expand_dims(input_tensor, axis=0)
        self.interpreter.set_tensor(self.input_index, input_tensor)
        self.interpreter.invoke()

        outputs = [
            self.interpreter.get_tensor(detail["index"])
            for detail in self.output_details
        ]

        self.results = self._postprocess_outputs(outputs, image.shape)

        self.detection_count += 1

        # Log periodically
        if self.detection_count % 100 == 0:
            logger.debug(
                f"Processed {self.detection_count} detections", operation="detect"
            )

    def get_annotated_image(self):
        """Get annotated image with detections."""
        try:
            if self.last_image is None:
                return None
            annotated = self.last_image.copy()
            if self.last_boxes is None:
                return annotated

            for box, score, cls in zip(
                self.last_boxes, self.last_scores, self.last_classes
            ):
                x_min, y_min, x_max, y_max = map(int, box)
                cv2.rectangle(annotated, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                label = f"{int(cls)} {score:.2f}"
                cv2.putText(
                    annotated,
                    label,
                    (x_min, max(0, y_min - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )

            return annotated
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

            return self.results
        except Exception as e:
            logger.error(
                f"Error extracting detections: {e}", operation="get_detections"
            )
            return None

    def _postprocess_outputs(self, outputs, image_shape):
        boxes, scores, classes = self._extract_detections(outputs, image_shape)
        if boxes is None or scores is None or classes is None:
            self.last_boxes = None
            self.last_scores = None
            self.last_classes = None
            return None

        min_conf = ConfigManager().get().min_confidence
        keep = scores >= min_conf
        boxes = boxes[keep]
        scores = scores[keep]
        classes = classes[keep]

        if boxes.size == 0:
            self.last_boxes = None
            self.last_scores = None
            self.last_classes = None
            return (boxes, scores, classes)

        boxes, scores, classes = self._nms(boxes, scores, classes)
        self.last_boxes = boxes
        self.last_scores = scores
        self.last_classes = classes
        return (boxes, scores, classes)

    def _extract_detections(self, outputs, image_shape):
        if not outputs:
            return None, None, None

        if len(outputs) >= 4 and outputs[0].shape[-1] == 4:
            boxes = outputs[0].squeeze()
            classes = outputs[1].squeeze()
            scores = outputs[2].squeeze()
            count = outputs[3].squeeze()
            if np.isscalar(count):
                count = int(count)
                boxes = boxes[:count]
                classes = classes[:count]
                scores = scores[:count]
            boxes = self._scale_boxes_yxyx(boxes, image_shape)
            return boxes, scores.astype(np.float32), classes.astype(np.float32)

        output = outputs[0].squeeze()
        if output.ndim == 1:
            return None, None, None
        if output.ndim == 3:
            output = output[0]
        if output.shape[0] < output.shape[1]:
            output = output.transpose()

        if output.shape[1] < 6:
            return None, None, None

        if output.shape[1] == 6:
            boxes = output[:, :4]
            scores = output[:, 4]
            classes = output[:, 5]
        else:
            boxes = output[:, :4]
            class_scores = output[:, 4:]
            classes = np.argmax(class_scores, axis=1)
            scores = class_scores[np.arange(class_scores.shape[0]), classes]

        boxes = self._scale_boxes_xyxy(boxes, image_shape)
        return boxes, scores.astype(np.float32), classes.astype(np.float32)

    def _scale_boxes_yxyx(self, boxes, image_shape):
        if boxes.size == 0:
            return boxes.reshape(0, 4)
        height, width = image_shape[:2]
        boxes = boxes.astype(np.float32)
        if np.max(boxes) <= 1.5:
            boxes[:, [0, 2]] *= height
            boxes[:, [1, 3]] *= width
        else:
            scale_x = width / self.input_width
            scale_y = height / self.input_height
            boxes[:, [0, 2]] *= scale_y
            boxes[:, [1, 3]] *= scale_x
        boxes = np.stack([boxes[:, 1], boxes[:, 0], boxes[:, 3], boxes[:, 2]], axis=1)
        return self._clip_boxes(boxes, width, height)

    def _scale_boxes_xyxy(self, boxes, image_shape):
        if boxes.size == 0:
            return boxes.reshape(0, 4)
        height, width = image_shape[:2]
        boxes = boxes.astype(np.float32)

        if np.max(boxes) <= 1.5:
            boxes = self._maybe_xywh_to_xyxy(boxes)
            boxes[:, [0, 2]] *= self.input_width
            boxes[:, [1, 3]] *= self.input_height
        else:
            boxes = self._maybe_xywh_to_xyxy(boxes)

        scale_x = width / self.input_width
        scale_y = height / self.input_height
        boxes[:, [0, 2]] *= scale_x
        boxes[:, [1, 3]] *= scale_y
        return self._clip_boxes(boxes, width, height)

    def _maybe_xywh_to_xyxy(self, boxes):
        if boxes.size == 0:
            return boxes.reshape(0, 4)
        xyxy_like = np.sum(boxes[:, 2] >= boxes[:, 0]) >= boxes.shape[0] * 0.9
        if xyxy_like:
            return boxes
        x, y, w, h = boxes.T
        x1 = x - w / 2
        y1 = y - h / 2
        x2 = x + w / 2
        y2 = y + h / 2
        return np.stack([x1, y1, x2, y2], axis=1)

    def _clip_boxes(self, boxes, width, height):
        boxes[:, 0] = np.clip(boxes[:, 0], 0, width - 1)
        boxes[:, 2] = np.clip(boxes[:, 2], 0, width - 1)
        boxes[:, 1] = np.clip(boxes[:, 1], 0, height - 1)
        boxes[:, 3] = np.clip(boxes[:, 3], 0, height - 1)
        return boxes

    def _nms(self, boxes, scores, classes, iou_threshold=0.45):
        if boxes.size == 0:
            return boxes, scores, classes

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]

        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter)

            order = order[1:][iou <= iou_threshold]

        keep = np.array(keep, dtype=np.int32)
        return boxes[keep], scores[keep], classes[keep]
