import cv2
import numpy as np
from typing import Optional
from app.components.detection.realsense_camera import RealSenseCamera
from app.core import logging_config
from components.detection.pipelines.pipeline_base import PipelineBase
from models.models import Pipeline
from sklearn.cluster import DBSCAN

from utils.utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)


class FuelPipeline(PipelineBase):
    name = "fuel"
    
    def __init__(self, camera):
        super().__init__()
        self.camera: RealSenseCamera = camera
        
        # HSV threshold parameters for fuel
        self.lower = np.array([19.424460431654676, 98.60611510791367, 98.60611510791367])
        self.upper = np.array([34.54545454545455, 255.0, 255.0])

        self.hsv_threshold_output = None
        self.__find_contours_external_only = False
        self.find_contours_output = None
        

        # Store latest frames
        self._color_frame = None
        self._depth_frame = None
        self._output_frame = None
        
        logger.info("FuelPipeline initialized")

    def iterate(self):
        """Process one iteration of the pipeline."""
        # Get frames from camera
        color_frame = self.camera._latest_frame
        
        if color_frame is None:
            logger.warning("No color frame received from camera")
            return
        
        self._color_frame = color_frame

        if self.camera.latest_depth_frame:
            self._depth_frame = self.camera.latest_depth_frame
        
        self.process(color_frame)
        
        # Create visualization output
        self._output_frame = self._create_visualization()
            

    def process(self, frame):
        # Step HSV_Threshold0:
        self.hsv_threshold_output = self.__hsv_threshold(
            frame, 
        )

        # Step Find_Contours0:
        self.find_contours_output = self.__find_contours(
            self.hsv_threshold_output, 
            self.__find_contours_external_only
        )

    def get_color_jpeg(self) -> Optional[bytes]:
        """Return the original color frame as JPEG bytes."""
        if self._color_frame is None:
            return None
        return frames_to_jpeg_bytes(self._output_frame)

    def get_depth_jpeg(self) -> Optional[bytes]:
        """No Depth Frame"""
        return frames_to_jpeg_bytes(self._depth_frame)

    def get_output(self) -> dict:
        """Return pipeline output data including contours and depth-based detections."""
        if self.find_contours_output is None:
            return {
                "contours_found": 0,
                "detections": []
            }
        
        detections = []
        for contour in self.find_contours_output:
            # Calculate contour properties
            area = cv2.contourArea(contour)
            
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Get center point
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = x + w // 2, y + h // 2
            
            depth_value = None
            avg_depth = None
            if self._depth_frame is not None:
                depth_value = self._depth_frame[cy, cx]
                
                # Calculate average depth over the contour region
                mask = np.zeros(self._depth_frame.shape, dtype=np.uint8)
                cv2.drawContours(mask, [contour], -1, (0,255,0), -1)
                depth_values = self._depth_frame[mask == 255]
                avg_depth = np.median(depth_values[depth_values > 0])
            
            detections.append({
                "center": (cx, cy),
                "bounding_box": (x, y, w, h),
                "area": area,
                "contour_points": len(contour),
                "depth": depth_value,
                "avg_depth": avg_depth
            })
        
        return {
            "contours_found": len(detections),
            "detections": detections,
        }

    def cluster_by_depth(self, detections, eps=50, min_samples=1):
        """
        Cluster detections in 3D space using DBSCAN.
        
        Args:
            detections: List of detection dictionaries
            eps: Maximum distance between points in same cluster (in mm)
            min_samples: Minimum points to form a cluster
            
        Returns:
            List of clusters with their detections
        """
        if not detections:
            return []
        
        # Filter valid detections with depth
        valid_detections = [d for d in detections if d.get('avg_depth') is not None and d['avg_depth'] > 0]
        
        if len(valid_detections) < 1:
            return [detections]
        
        # Create 3D points (x, y, depth)
        points_3d = np.array([
            [d['center'][0], d['center'][1], d['avg_depth']]
            for d in valid_detections
        ])
        
        # Normalize x, y coordinates to match depth scale (approximate)
        # Adjust scale_factor based on your camera FOV and resolution
        scale_factor = 1.0  # Tune this value
        points_3d[:, :2] *= scale_factor
        
        # Perform DBSCAN clustering
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(points_3d)
        
        # Group detections by cluster
        clusters = {}
        for idx, label in enumerate(clustering.labels_):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(valid_detections[idx])
        
        return list(clusters.values())

    def _create_visualization(self) -> Optional[np.ndarray]:
        """Create a visualization frame with contours, detections, and depth info."""
        if self._color_frame is None or self.find_contours_output is None:
            return None
        
        output = self._color_frame.copy()
        
        cv2.drawContours(output, self.find_contours_output, -1, (0, 255, 0), 2)
        
        output_data = self.get_output()
        
        clusters = self.cluster_by_depth(output_data["detections"])
        
        colors = [(255, 0, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0), (128, 0, 255)]
        
        for cluster_idx, cluster in enumerate(clusters):
            cluster_color = colors[cluster_idx % len(colors)]
            
            for detection in cluster:
                cx, cy = detection["center"]
                x, y, w, h = detection["bounding_box"]
                
                cv2.rectangle(output, (x, y), (x + w, y + h), cluster_color, 2)
                
                cv2.circle(output, (cx, cy), 5, (0, 0, 255), -1)
                
                info_lines = [f"Area: {int(detection['area'])}"]
                
                if detection.get('avg_depth') is not None and detection['avg_depth'] > 0:
                    depth_m = detection['avg_depth'] / 1000.0
                    info_lines.append(f"Depth: {depth_m:.2f}m")
                
                y_offset = y - 10
                for line in reversed(info_lines):
                    text_size = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                    cv2.rectangle(output, 
                                (x, y_offset - text_size[1] - 4),
                                (x + text_size[0] + 4, y_offset + 2),
                                (0, 0, 0), -1)
                    cv2.putText(output, line, (x + 2, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset -= (text_size[1] + 6)
        
        info_text = f"Fuel Targets: {output_data['contours_found']} | Clusters: {len(clusters)}"
        
        text_size = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.rectangle(output, (5, 5), (15 + text_size[0], 40), (0, 0, 0), -1)
        cv2.putText(output, info_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return output

    def get_visualization_jpeg(self) -> Optional[bytes]:
        """Return the visualization frame as JPEG bytes."""
        if self._output_frame is None:
            return None
        return frames_to_jpeg_bytes(self._output_frame)


    def __hsv_threshold(self, input):
        out = cv2.cvtColor(input, cv2.COLOR_BGR2HSV)
        return cv2.inRange(out, self.lower, self.upper)

    @staticmethod
    def __find_contours(input, external_only):
        """Find contours in a binary image.
        
        Args:
            input: A numpy.ndarray binary image.
            external_only: A boolean. If true only external contours are found.
            
        Return:
            A list of numpy.ndarray where each one represents a contour.
        """
        if external_only:
            mode = cv2.RETR_EXTERNAL
        else:
            mode = cv2.RETR_LIST
        method = cv2.CHAIN_APPROX_SIMPLE
        
        # Handle different OpenCV versions
        contours_output = cv2.findContours(input, mode=mode, method=method)
        
        # OpenCV 3.x returns (image, contours, hierarchy)
        # OpenCV 4.x returns (contours, hierarchy)
        if len(contours_output) == 3:
            contours = contours_output[1]
        else:
            contours = contours_output[0]
        
        return contours