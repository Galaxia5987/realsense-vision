from utils import frames_to_jpeg_bytes
from detection.detector import YOLODetector
import cv2

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
                x, y = center
                depth_text = f"{depth:.2f}m"
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
            centers = [(int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)) for bbox in bboxs]
            depths = [depth_frame.get_distance(center[0], center[1]) for center in centers]
            self.detections = [{'bbox': bbox, 'center': center, 'depth': depth} for bbox, center, depth in zip(bboxs, centers, depths)]


    def get_output(self):
        if hasattr(self, 'detections'):
            return self.detections
        return None

class DepthPipeline:
    def __init__(self, camera):
        self.camera = camera
        self.frame = None

    def loop(self):
        pass
        # self.frame = self.camera.get_latest_depth_frame()

    def get_jpeg(self):
        if self.frame is None:
            return None
        return frames_to_jpeg_bytes(self.frame, resolution=(self.camera.width, self.camera.height))

class ColorPipeline:
    def __init__(self, camera):
        self.camera = camera
        self.frame = None

    def loop(self):
        self.frame = self.camera.get_latest_color_frame()

    def get_jpeg(self):
        if self.frame is None:
            return None
        return frames_to_jpeg_bytes(self.frame, resolution=(self.camera.width, self.camera.height))
    

pipelines = {
    "detection": DetectionDepthPipeline, 
    "depth": DepthPipeline,
    "color": ColorPipeline
}

