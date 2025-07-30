from utils import frames_to_jpeg_bytes
from detection.detector import YOLODetector
import cv2
from pyrealsense2 import rs2_deproject_pixel_to_point

class DetectionDepthPipeline:
    def __init__(self, camera, model_path):
        self.camera = camera
        self.detector = YOLODetector(model_path)

    def get_jpeg(self):
        detected = self.detector.get_annotated_image()
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
    
    def get_depth_jpeg(self):
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
    
    def loop(self):
        frame = self.camera.get_latest_frame()
        depth_frame = self.camera.get_latest_depth_data()
        if frame is None or depth_frame is None:
            return
        self.detector.detect(frame)
        detections = self.detector.get_detections()
        if detections:
            bboxs = detections[0]
            if len(bboxs) < 1:
                return
            intrinsics = depth_frame.profile.as_video_stream_profile().get_intrinsics()
            centers = [(int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)) for bbox in bboxs]
            depths = [depth_frame.get_distance(center[0], center[1]) for center in centers]
            points = [rs2_deproject_pixel_to_point(intrinsics, center, depth) for center, depth in zip(centers, depths)]
            self.detections = [{'bbox': bbox, 'center': center, 'depth': depth, 'point': point} for bbox, center, depth, point in zip(bboxs, centers, depths, points)]
            print(self.detections)


    def get_output(self):
        if hasattr(self, 'detections'):
            return self.detections
        return None

class RegularPipeline:
    def __init__(self, camera):
        self.camera = camera
        self.frame = None

    def loop(self):
        self.frame = self.camera.get_latest_frame()
        self.depth_frame = self.camera.get_latest_depth_frame()
        
    def get_depth_jpeg(self):
        if self.depth_frame is None:
            return None
        return frames_to_jpeg_bytes(self.depth_frame, resolution=(self.camera.width, self.camera.height))

    def get_jpeg(self):
        if self.frame is None:
            return None
        return frames_to_jpeg_bytes(self.frame, resolution=(self.camera.width, self.camera.height))
    

pipelines = {
    "detection": DetectionDepthPipeline, 
    "regular": RegularPipeline
}

