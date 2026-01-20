import cv2
import numpy as np
from typing import Optional
from app.components.detection.realsense_camera import RealSenseCamera
from app.core import logging_config
from app.components.detection.pipelines.pipeline_base import PipelineBase
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

        if self.camera.latest_depth_frame is not None:
            self._depth_frame = self.camera.latest_depth_frame
        
        self._process(color_frame)
        
    def _process(self, color_frame):
        frame = color_frame.copy()
        self.hsv_threshold_output = self.__hsv_threshold(frame)

        point_cloud = self.camera.get_latest_pointcloud()
        h, w = self.hsv_threshold_output.shape

        # Reshape point cloud to image-aligned format
        point_cloud = point_cloud.reshape(h, w, 3)

        # Apply HSV mask and keep track of pixel coordinates
        mask = self.hsv_threshold_output > 0
        
        # Get pixel coordinates where mask is True
        pixel_coords = np.argwhere(mask)  # Returns (row, col) pairs
        
        # Get corresponding 3D points
        ball_points = point_cloud[mask]

        # Remove invalid depth and corresponding pixel coordinates
        valid_depth_mask = ball_points[:, 2] > 0
        ball_points = ball_points[valid_depth_mask]
        pixel_coords = pixel_coords[valid_depth_mask]

        clustered_balls = self.cluster_by_depth(ball_points, pixel_coords)
        self._output_frame = self._create_visualization(clustered_balls)


    def get_color_jpeg(self) -> Optional[bytes]:
        """Return the original color frame as JPEG bytes."""
        if self._color_frame is None or self._output_frame is None:
            return None
        return frames_to_jpeg_bytes(self._output_frame, resolution=(self.camera.width, self.camera.height))

    def get_depth_jpeg(self) -> Optional[bytes]:
        """No Depth Frame"""
        if self._depth_frame is None:
            return None
        return frames_to_jpeg_bytes(self._depth_frame, resolution=(self.camera.width, self.camera.height))

    def get_output(self) -> None:
        pass

    def cluster_by_depth(self, ball_points, pixel_coords):
        if ball_points.shape[0] == 0 or ball_points is None:
            return []
        
        clustering = DBSCAN(eps=0.05, min_samples=5).fit(ball_points)
        labels = clustering.labels_

        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label

        clusters = []
        for label in unique_labels:
            # Get all points belonging to this cluster
            cluster_mask = labels == label
            cluster_points = ball_points[cluster_mask]
            cluster_pixels = pixel_coords[cluster_mask]
            
            num_points = len(cluster_points)
            
            # Discard clusters with fewer than 400 points (noise)
            if num_points < 400:
                continue
            
            # Calculate cluster properties
            centroid_3d = np.mean(cluster_points, axis=0)  # [X, Y, Z]
            centroid_2d = np.mean(cluster_pixels, axis=0).astype(int)  # [row, col]
            depth = centroid_3d[2]  # Z coordinate
            
            clusters.append({
                'id': label,
                'points': cluster_points,
                'pixels': cluster_pixels,  # Store 2D pixel coordinates
                'centroid_3d': centroid_3d,
                'centroid_2d': centroid_2d,
                'depth': depth,
                'num_points': num_points
            })
            
        # clusters.sort(key=lambda c: c['depth'])
        return clusters

    def _create_visualization(self, clustered_balls) -> Optional[np.ndarray]:
        if self._color_frame is None:
            return None

        output = self._color_frame.copy()  # Avoid modifying original frame

        if len(clustered_balls) == 0:
            return output

        clusters = clustered_balls
        colors = [(255, 0, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0), (128, 0, 255)]

        for cluster_idx, cluster in enumerate(clusters):
            cluster_color = colors[cluster_idx % len(colors)]
            pixels = cluster['pixels']  # 2D pixel coordinates (row, col)

            # bounding box
            rows, cols = pixels[:, 0], pixels[:, 1]
            y_min, y_max = int(rows.min()), int(rows.max())
            x_min, x_max = int(cols.min()), int(cols.max())
            
            x, y = x_min, y_min
            w, h = x_max - x_min, y_max - y_min

            # Draw bounding box
            cv2.rectangle(output, (x, y), (x + w, y + h), cluster_color, 2)

            # Draw centre (convert row, col to x, y)
            cx, cy = cluster['centroid_2d'][1], cluster['centroid_2d'][0]
            cv2.circle(output, (cx, cy), 5, (0, 0, 255), -1)

            info_lines = [f"Points: {cluster['num_points']}"]
            if cluster.get('depth') is not None and cluster['depth'] > 0:
                depth_m = cluster['depth'] / 1000.0
                info_lines.append(f"Depth: {depth_m:.2f}m")

            y_offset = y - 10
            for line in reversed(info_lines):
                text_size = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                cv2.putText(output, line, (x + 2, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset -= (text_size[1] + 6)

        info_text = f"Clusters: {len(clusters)}"
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