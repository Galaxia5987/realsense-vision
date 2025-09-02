import os
from flask import flash
from ultralytics import YOLO
import scheduler

def convert_model(model_path, chip='rk3588', flash_after=True):
    os.chdir(os.path.dirname(model_path))
    model = YOLO(model_path)
    
    out_path = model.export(format='rknn', name=chip)
    if flash_after:
        scheduler.flash_scheduler_message = f'Model converted and saved to {out_path}'
    os.chdir('..')
    return out_path

if __name__ == "__main__":
    convert_model("best.pt")