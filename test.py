from ultralytics import YOLO

model = YOLO('uploads/best.pt')

model.export(
    format='saved_model',
    half=False,
    # int8=True,
    # data="dataset/data.yaml",
    # imgsz=640
)