from utils import frames_to_jpeg_bytes
from detection.detector import YOLODetector
import cv2
import numpy as np
from pyrealsense2 import rs2_deproject_pixel_to_point
import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)

class DetectionDepthPipeline:
    def __init__(self, camera, model_path):
        self.camera = camera
        np.set_printoptions(threshold=100000)
        
        try:
            self.detector = YOLODetector(model_path)
            self.detections = []
        except Exception as e:
            logger.exception(f"Failed to initialize DetectionDepthPipeline: {e}", operation="init")
            raise

    def get_jpeg(self):
        """Get JPEG-encoded annotated image."""
        try:
            detected = self.detector.get_annotated_image()
            if detected is None:
                logger.warning("No annotated image available", operation="get_jpeg")
                return None
                
            if hasattr(self, 'detections'):
                for detection in self.detections:
                    center = detection['center']
                    depth = detection['depth']
                    point = detection['point']
                    point = [round(coord, 2) for coord in point]
                    x, y = center
                    depth_text = f"{point}"
                    cv2.putText(detected, depth_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.circle(detected, center, 5, (0, 255, 255), -1)
            return frames_to_jpeg_bytes(detected, resolution=(self.camera.width, self.camera.height))
        except Exception as e:
            logger.error(f"Error generating JPEG: {e}", operation="get_jpeg")
            return None
    
    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame with annotations."""
        try:
            depth_frame = self.camera.get_latest_depth_frame()
            if depth_frame is None:
                return None
            if hasattr(self, 'detections'):
                for detection in self.detections:
                    center = detection['center']
                    depth = detection['depth']
                    x, y = center
                    cv2.putText(depth_frame, f"{depth:.2f}m", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.circle(depth_frame, center, 5, (0, 255, 255), -1)
            return frames_to_jpeg_bytes(depth_frame, resolution=(self.camera.width, self.camera.height))
        except Exception as e:
            logger.error(f"Error generating depth JPEG: {e}", operation="get_depth_jpeg")
            return None
    
    def loop(self):
        """Main detection loop with error handling."""
        try:
            frame = self.camera.get_latest_frame()
            depth_frame = self.camera.get_latest_depth_data()
            
            if frame is None or depth_frame is None:
                return
            
            self.detector.detect(frame)
            detections = self.detector.get_detections()
            
            if not detections:
                self.detections = []
                return
                
            bboxs = detections[0]
            if len(bboxs) < 1:
                self.detections = []
                return
            
            intrinsics = depth_frame.profile.as_video_stream_profile().get_intrinsics()
            self.detections = []

            depth_mat = np.asanyarray(depth_frame.get_data())  # shape: (height, width), uint16 in mm
            height, width = depth_mat.shape

            for bbox in bboxs:
                try:
                    # Convert to absolute integer pixel coordinates
                    x_min, y_min, x_max, y_max = map(int, bbox)

                    # Clamp to image bounds
                    x_min = max(0, min(x_min, width - 1))
                    x_max = max(0, min(x_max, width - 1))
                    y_min = max(0, min(y_min, height - 1))
                    y_max = max(0, min(y_max, height - 1))

                    center_x = (x_min + x_max) // 2
                    center_y = (y_min + y_max) // 2

                    depth_crop = depth_mat[y_min:y_max, x_min:x_max]

                    mask = (depth_crop != 0)
                    if np.any(mask):
                        min_idx = np.argmin(depth_crop[mask])
                        mask_coords = np.argwhere(mask)
                        min_y_local, min_x_local = mask_coords[min_idx]

                        min_x = x_min + min_x_local
                        min_y = y_min + min_y_local
                        min_value_mm = depth_mat[min_y, min_x]
                    else:
                        min_x, min_y = center_x, center_y
                        min_value_mm = 0

                    depth_meters = min_value_mm / 1000.0
                    point = rs2_deproject_pixel_to_point(intrinsics, [min_x, min_y], depth_meters)

                    self.detections.append({
                        'bbox': bbox,
                        'center': (center_x, center_y),
                        'depth': min_value_mm,
                        'point': point
                    })
                except Exception as e:
                    logger.warning(f"Error processing detection bbox: {e}", operation="loop")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in detection loop: {e}", operation="loop")
            self.detections = []




    def get_output(self):
        if hasattr(self, 'detections'):
            return self.detections
        return None

class RegularPipeline:
    def __init__(self, camera):
        logger.info("Initializing RegularPipeline", operation="init")
        self.camera = camera
        self.frame = None
        logger.info("RegularPipeline initialized", operation="init", status="success")

    def loop(self):
        """Main processing loop."""
        try:
            self.frame = self.camera.get_latest_frame()
            self.depth_frame = self.camera.get_latest_depth_frame()
        except Exception as e:
            logger.error(f"Error in regular pipeline loop: {e}", operation="loop")
        
    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        try:
            if self.depth_frame is None:
                return None
            return frames_to_jpeg_bytes(self.depth_frame, resolution=(self.camera.width, self.camera.height))
        except Exception as e:
            logger.error(f"Error generating depth JPEG: {e}", operation="get_depth_jpeg")
            return None

    def get_jpeg(self):
        """Get JPEG-encoded color frame."""
        try:
            if self.frame is None:
                return None
            return frames_to_jpeg_bytes(self.frame, resolution=(self.camera.width, self.camera.height))
        except Exception as e:
            logger.error(f"Error generating JPEG: {e}", operation="get_jpeg")
            return None
    

pipelines = {
    "detection": DetectionDepthPipeline, 
    "regular": RegularPipeline
}

