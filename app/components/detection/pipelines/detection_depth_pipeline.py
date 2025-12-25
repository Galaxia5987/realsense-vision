import numpy as np
from pydantic import BaseModel
from pyrealsense2 import rs2_deproject_pixel_to_point

import app.core.logging_config as logging_config
from app.components.detection.detector import YOLODetector
from app.components.detection.pipelines.pipeline_base import PipelineBase
from app.config import ConfigManager
from app.core.uploader import UPLOAD_FOLDER
from models.detection_model import Detection, Point2d, Point3d
from utils import drawing_utils
from utils.utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)


class DetectionDepthPipeline(PipelineBase):
    class Properties(BaseModel):
        model_path: str
    name = "DetectionDepthPipeline"
    props = Properties

    def __init__(self, camera, props: Properties):
        self.camera = camera
        model_path = f"./{UPLOAD_FOLDER}/{props.model_path}"
        self.detections: list[Detection] = []
        config = ConfigManager().get()
        self.detector = YOLODetector(model_path, imgsz=config.image_size)

    def get_color_jpeg(self):
        """Get JPEG-encoded annotated image."""
        detected = self.detector.get_annotated_image()
        if detected is None:
            return None

        drawing_utils.annotate_detections(
            detected, self.detections, lambda det: str(det.point)
        )

        return frames_to_jpeg_bytes(
            detected, resolution=(self.camera.width, self.camera.height)
        )

    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame with annotations."""
        depth_frame = self.camera.latest_depth_frame
        if depth_frame is None:
            return None

        drawing_utils.annotate_detections(
            depth_frame, self.detections, lambda det: f"{det.depth:.2f}m"
        )

        return frames_to_jpeg_bytes(
            depth_frame, resolution=(self.camera.width, self.camera.height)
        )

    def iterate(self):
        """Main detection loop with error handling."""
        frame = self.camera.latest_frame
        depth_frame = self.camera.latest_depth_data

        if frame is None or depth_frame is None:
            logger.error("Camera frame is None!")
            self.detections = []
            return

        self.detector.detect(frame)
        detections = self.detector.get_detections()

        if not detections or detections[0] is None:
            self.detections = []
            return

        bboxs = detections[0]
        depth_mat = np.asanyarray(depth_frame.get_data())
        height, width = depth_mat.shape
        intrinsics = depth_frame.profile.as_video_stream_profile().get_intrinsics()
        self.detections = []

        def clamp(val, min_val, max_val):
            return max(min_val, min(val, max_val))

        for bbox in bboxs:
            try:
                x_min, y_min, x_max, y_max = map(int, bbox)
                x_min, x_max = clamp(x_min, 0, width - 1), clamp(x_max, 0, width - 1)
                y_min, y_max = clamp(y_min, 0, height - 1), clamp(y_max, 0, height - 1)

                center_x, center_y = (x_min + x_max) // 2, (y_min + y_max) // 2

                depth_crop = depth_mat[y_min:y_max, x_min:x_max]
                mask = depth_crop != 0

                if np.any(mask):
                    mask_coords = np.argwhere(mask)
                    min_idx = np.argmin(depth_crop[mask])
                    min_y_local, min_x_local = mask_coords[min_idx]
                    min_x, min_y = x_min + min_x_local, y_min + min_y_local
                    min_value_mm = depth_mat[min_y, min_x]
                else:
                    min_x, min_y = center_x, center_y
                    min_value_mm = 0

                depth_meters = min_value_mm / 1000.0
                point = rs2_deproject_pixel_to_point(
                    intrinsics, [min_x, min_y], depth_meters
                )
                y, z, x = point
                self.detections.append(
                    Detection(
                        Point3d(x, y, z), Point2d(center_x, center_y), depth_meters
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Error processing detection bbox: {e}", operation="loop"
                )

    def get_output(self) -> list[Detection]:
        return self.detections
