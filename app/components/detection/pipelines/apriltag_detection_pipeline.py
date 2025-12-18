import numpy as np
import cv2
from pupil_apriltags import Detector 
from pyrealsense2 import rs2_deproject_pixel_to_point

import app.core.logging_config as logging_config
from app.components.detection.pipelines.pipeline_base import PipelineBase
from app.components.detection.realsense_camera import RealSenseCamera, StreamType
from models.detection_model import Detection, Point2d, Point3d
from utils import drawing_utils
from utils.utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)

# --- Detector Class ---

class AprilTagDetector:
    """A wrapper for pupil_apriltags.Detector."""
    def __init__(self, tag_family: str = "tag36h11"):
        self.detector = Detector(families=tag_family)
        self.latest_frame = None
        self.latest_detections = None

    def detect(self, frame_image: np.ndarray, estimate_pose=False, camera_params=None, tag_size=None):
        """Detects AprilTags."""
        self.latest_frame = frame_image

        # Always convert to grayscale for detection
        if frame_image.ndim == 3:
            gray_image = cv2.cvtColor(frame_image, cv2.COLOR_BGR2GRAY)
        else:
            gray_image = frame_image

        self.latest_detections = self.detector.detect(
            gray_image,
            estimate_tag_pose=estimate_pose,
            camera_params=camera_params,
            tag_size=tag_size
        )

    def get_detections(self):
        """Returns tuple (results_list, raw_tags_list)."""
        if self.latest_detections is None:
            return None
        
        results = []
        for tag in self.latest_detections:
            x_coords = tag.corners[:, 0]
            y_coords = tag.corners[:, 1]
            x_min, y_min = np.min(x_coords), np.min(y_coords)
            x_max, y_max = np.max(x_coords), np.max(y_coords)
            
            bbox = [x_min, y_min, x_max, y_max]
            results.append((bbox, tag.tag_id))
            
        return (results, self.latest_detections)

    def get_annotated_image(self) -> np.ndarray | None:
        """Returns a BGR annotated image."""
        if self.latest_frame is None or self.latest_detections is None:
            return None

        frame = self.latest_frame

        # Ensure 3-channel BGR
        if frame.ndim == 2 or (frame.ndim == 3 and frame.shape[2] == 1):
            annotated_image = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.ndim == 3 and frame.shape[2] == 3:
            annotated_image = frame.copy()
        else:
            # Fallback
            annotated_image = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        for tag in self.latest_detections:
            for idx in range(len(tag.corners)):
                cv2.line(
                    annotated_image,
                    tuple(tag.corners[idx - 1].astype(int)),
                    tuple(tag.corners[idx].astype(int)),
                    (0, 255, 0),
                    2
                )

            center = tag.center.astype(int)
            cv2.circle(annotated_image, tuple(center), 3, (0, 0, 255), -1)
            cv2.putText(
                annotated_image,
                f"ID: {tag.tag_id}",
                (center[0], center[1] - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

        return annotated_image


# --- Pipeline Class ---

class AprilTagDetectionPipeline(PipelineBase):
    name = "AprilTagPipeline"
    stream_type = StreamType.INFRARED

    TAG_FAMILY = "tag36h11"
    TAG_SIZE = 0.05  # METERS

    def __init__(self, camera: RealSenseCamera):
        self.camera = camera
        self.detections: list[Detection] = []
        self.detector = AprilTagDetector(tag_family=self.TAG_FAMILY)

    # --- Utility methods ---
    def _clamp(self, val, min_val, max_val):
        return max(min_val, min(val, max_val))

    def _prepare_bbox(self, bbox, width, height):
        x_min, y_min, x_max, y_max = map(int, bbox)
        x_min, x_max = self._clamp(x_min, 0, width - 1), self._clamp(x_max, 0, width - 1)
        y_min, y_max = self._clamp(y_min, 0, height - 1), self._clamp(y_max, 0, height - 1)
        center_x, center_y = (x_min + x_max) // 2, (y_min + y_max) // 2
        return x_min, y_min, x_max, y_max, center_x, center_y

    def _median_depth_meters(self, depth_mat, x_min, y_min, x_max, y_max):
        depth_crop = depth_mat[y_min:y_max, x_min:x_max]
        mask = depth_crop != 0

        sample_x, sample_y = (x_min + x_max) // 2, (y_min + y_max) // 2
        depth_meters = 0.0

        if np.any(mask):
            non_zero_values = depth_crop[mask]
            depth_meters = np.median(non_zero_values) * self.camera.depth_scale

        return sample_x, sample_y, depth_meters

    def _process_sensor_depth_pass(self, detection_results, raw_tags, depth_mat, rs_intrinsics):
        height, width = depth_mat.shape
        detections: list[Detection] = []
        fallback_tag_ids: set[int] = set()

        for ((bbox, tag_id), raw_tag) in zip(detection_results, raw_tags):
            try:
                x_min, y_min, x_max, y_max, center_x, center_y = self._prepare_bbox(
                    bbox, width, height
                )

                sample_x, sample_y, depth_meters = self._median_depth_meters(
                    depth_mat, x_min, y_min, x_max, y_max
                )

                if depth_meters > 0.1:
                    # NOTE: Axis order intentionally unchanged (y, z, x) for first pass
                    y, z, x = rs2_deproject_pixel_to_point(
                        rs_intrinsics, [sample_x, sample_y], depth_meters
                    )
                    detections.append(
                        Detection(
                            point=Point3d(x, y, z),
                            center=Point2d(center_x, center_y),
                            depth=depth_meters,
                            label=str(tag_id),
                        )
                    )
                else:
                    fallback_tag_ids.add(tag_id)

            except Exception as e:
                logger.warning(f"Error processing Tag {tag_id}: {e}")

        return detections, fallback_tag_ids

    def _process_fallback_pass(
        self,
        frame,
        depth_mat,
        fallback_tag_ids,
        rs_intrinsics,
    ):
        cam_params = self.camera.camera_intrinsics
        self.detector.detect(
            frame, estimate_pose=True, camera_params=cam_params, tag_size=self.TAG_SIZE
        )
        detections_tuple = self.detector.get_detections()

        if not detections_tuple or not detections_tuple[0]:
            return []

        detection_results, raw_tags = detections_tuple
        _, width = depth_mat.shape
        detections: list[Detection] = []

        for (bbox, tag_id), raw_tag in zip(detection_results, raw_tags):
            if fallback_tag_ids and tag_id not in fallback_tag_ids:
                continue

            x_min, y_min, x_max, y_max, center_x, center_y = self._prepare_bbox(
                bbox, width, height
            )
            center_x = self._clamp(center_x, 0, width - 1)
            center_y = self._clamp(center_y, 0, height - 1)

            d_val = depth_mat[center_y, center_x] * self.camera.depth_scale

            if d_val > 0.1:
                x, y, z = rs2_deproject_pixel_to_point(rs_intrinsics, [center_x, center_y], d_val)
                depth = d_val
            elif raw_tag.pose_t is not None:
                x = raw_tag.pose_t[0][0]
                y = raw_tag.pose_t[1][0]
                z = raw_tag.pose_t[2][0]
                depth = z
            else:
                continue

            detections.append(
                Detection(
                    point=Point3d(x, y, z),
                    center=Point2d(center_x, center_y),
                    depth=depth,
                    label=str(tag_id) + "F",
                )
            )

        return detections

    # --- Color / IR JPEG ---
    def get_color_jpeg(self):
        detected = self.detector.get_annotated_image()
        if detected is None:
            return None

        # Safe annotation
        drawing_utils.annotate_detections(
            detected, self.detections, lambda det: f"ID:{det.label} X:{det.point.x:.2f} Z:{det.point.z:.2f}"
        )

        return frames_to_jpeg_bytes(
            detected, resolution=(self.camera.width, self.camera.height)
        )

    # --- Depth JPEG ---
    def get_depth_jpeg(self):
        depth_frame = self.camera.latest_depth_frame 
        if depth_frame is None:
            return None

        drawing_utils.annotate_detections(
            depth_frame, self.detections, lambda det: f"{det.depth:.2f}m"
        )

        return frames_to_jpeg_bytes(
            depth_frame, resolution=(self.camera.width, self.camera.height)
        )

    # --- Iteration (Detection + Depth) ---
    def iterate(self):
        frame = self.camera.latest_frame
        depth_frame = self.camera.latest_depth_data

        if frame is None or depth_frame is None:
            self.detections = []
            return

        # First pass: detect without pose
        self.detector.detect(frame, estimate_pose=False)
        detections_tuple = self.detector.get_detections()

        if not detections_tuple or not detections_tuple[0]:
            self.detections = []
            return

        detection_results, raw_tags = detections_tuple

        depth_mat = np.asanyarray(depth_frame.get_data())
        rs_intrinsics = depth_frame.profile.as_video_stream_profile().get_intrinsics()

        temp_detections, fallback_tag_ids = self._process_sensor_depth_pass(
            detection_results, raw_tags, depth_mat, rs_intrinsics
        )

        if fallback_tag_ids:
            temp_detections.extend(
                self._process_fallback_pass(
                    frame, depth_mat, fallback_tag_ids, rs_intrinsics
                )
            )

        self.detections = temp_detections

    def get_output(self) -> list[Detection]:
        return self.detections
