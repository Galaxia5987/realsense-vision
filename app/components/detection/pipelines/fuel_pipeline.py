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
        depth = self._depth_frame.copy()[:, :, 0]

        # Normalize depth to 0-255 uint8
        depth_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # HSV mask (uint8, 0/255)
        hsv_mask = self.__hsv_threshold(color_frame).astype(np.uint8)        

        # Mask depth with HSV
        depth_roi = cv2.bitwise_and(
            depth_norm, depth_norm, mask=hsv_mask
        )

        contours, _ = cv2.findContours(
            depth_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        self._create_visualization(color_frame, contours)



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

    def _create_visualization(self, frame, contours) -> Optional[np.ndarray]:
        if frame is None:
            return None

        output = frame.copy()

        if contours:
            for i, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                if area < 500:
                    continue

                # Draw contour
                cv2.drawContours(output, [cnt], -1, (0, 255, 0), 2)

                # Bounding box
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(output, (x, y), (x + w, y + h), (255, 0, 0), 2)

                # Compute center of mass
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    # Draw center
                    cv2.circle(output, (cx, cy), 4, (0, 0, 255), -1)
                    
                    # label
                    cv2.putText(output, f"C{i}\n Area: {area}", (cx + 5, cy - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                else:
                    cx, cy = x + w // 2, y + h // 2  # fallback

        self._output_frame = output


    def get_visualization_jpeg(self) -> Optional[bytes]:
        """Return the visualization frame as JPEG bytes."""
        if self._output_frame is None:
            return None
        return frames_to_jpeg_bytes(self._output_frame)


    def __hsv_threshold(self, input):
        out = cv2.cvtColor(input, cv2.COLOR_BGR2HSV)
        return cv2.inRange(out, self.lower, self.upper)