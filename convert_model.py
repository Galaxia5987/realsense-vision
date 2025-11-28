import asyncio
import os
from ultralytics import YOLO

def convert_model(model_path, chip='rk3588'):
    os.chdir(os.path.dirname(model_path))
    model = YOLO(model_path)
    
    out_path = model.export(format='rknn', name=chip)
    os.chdir('..')
    return out_path

async def async_convert_model(model_path, chip='rk3588s'):
    await asyncio.to_thread(
        convert_model,
        model_path,
        chip,
      )

if __name__ == "__main__":
    convert_model("./uploads/best.pt")
