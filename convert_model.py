from ultralytics import YOLO

def convert_model(model_path, chip='rk3588'):
    model = YOLO(model_path)
    
    out_path = model.export(format='rknn', name=chip)
    
    return out_path

if __name__ == "__main__":
    convert_model("best.pt")