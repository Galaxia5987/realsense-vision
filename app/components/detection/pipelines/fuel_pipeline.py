import cv2
import numpy as np
from typing import Optional
from app.components.detection.realsense_camera import RealSenseCamera
from app.core import logging_config
from components.detection.pipelines.pipeline_base import PipelineBase
from models.models import Pipeline

from utils.utils import frames_to_jpeg_bytes

logger = logging_config.get_logger(__name__)


class FuelPipeline(PipelineBase):
    name = "fuel"
    
    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        
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
        
        self.process(color_frame)
        
        # Create visualization output
        self._output_frame = self._create_visualization()
            

    def process(self, frame):
        """
        Runs the pipeline and sets all outputs to new values.
        
        Args:
            source0: Input BGR image from camera
        """
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
        return None        

    def get_output(self) -> dict:
        """Return pipeline output data including contours and detections."""
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
            
            detections.append({
                "center": (cx, cy),
                "bounding_box": (x, y, w, h),
                "area": area,
                "contour_points": len(contour)
            })
        
        return {
            "contours_found": len(detections),
            "detections": detections,
        }

    def _create_visualization(self) -> Optional[np.ndarray]:
        """Create a visualization frame with contours and detections drawn."""
        if self._color_frame is None or self.find_contours_output is None:
            return None
        
        # Create a copy to draw on
        output = self._color_frame.copy()
        
        # Draw all contours
        cv2.drawContours(output, self.find_contours_output, -1, (0, 255, 0), 2)
        
        # Draw detection info
        output_data = self.get_output()
        for detection in output_data["detections"]:
            cx, cy = detection["center"]
            x, y, w, h = detection["bounding_box"]
            
            # Draw bounding box
            cv2.rectangle(output, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            # Draw center point
            cv2.circle(output, (cx, cy), 5, (0, 0, 255), -1)
            
            # Draw area label
            cv2.putText(
                output, 
                f"Area: {int(detection['area'])}", 
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                (255, 255, 255), 
                1
            )
        
        # Draw summary info
        info_text = f"Fuel Targets: {output_data['contours_found']}"
        cv2.putText(
            output, 
            info_text, 
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (0, 255, 0), 
            2
        )
        
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