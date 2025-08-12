from ultralytics import YOLO
from config import config

class YOLODetector:
    def __init__(self, model_path, imgsz=640):
        self.model = YOLO(model_path, task="detect")
        self.imgsz = imgsz
        self.results = None
            

    def detect(self, image):
        self.results = self.model(image, imgsz=self.imgsz, conf=config.get_config().get("min_confidence", 0.85))[0]
    
    def get_annotated_image(self):
        return self.results.plot()

    def get_detections(self):
        return self.results.boxes.xyxy.cpu().numpy(), self.results.boxes.conf.cpu().numpy(), self.results.boxes.cls.cpu().numpy()
