import asyncio
import os
from pathlib import Path

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import ConfigManager
from app.core import logging_config
from convert_model import async_convert_model
from models.models import ChipType

UPLOAD_FOLDER = Path("uploads")
logger = logging_config.get_logger(__name__)


def secure_filename(name: str) -> str:
    # very simple sanitization
    return os.path.basename(name).replace("..", "").replace("/", "").replace("\\", "")


async def upload_model(file: UploadFile = File(...)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No selected file")

        raw_name = secure_filename(file.filename)
        path = Path(raw_name)
        suffix = path.suffix
        file_path = UPLOAD_FOLDER / path


        UPLOAD_FOLDER.mkdir(exist_ok=True)

        if file_path.exists():
            file_path.unlink()

        file_path.write_bytes(await file.read())
        logger.info(f"Finished uploading {file_path}", operation="upload")

        await asyncio.sleep(1)

        chip = ConfigManager().get().chip_type
        if chip == ChipType.rk3588:
            if suffix == ".pt":
                asyncio.create_task(async_convert_model(file_path, chip))
                return RedirectResponse(url="/upload_progress", status_code=303)
            else:
                return HTMLResponse("RKNN models should end with .pt for conversion!", status_code=400)
        elif chip == ChipType.qcs6490:
            if suffix == ".tflite":
                return RedirectResponse("/", status_code=303)
            else:
                return HTMLResponse("TFLITE(QNN) models should be in TFLITE format!", status_code=400)

    except Exception as e:
        logger.exception("Model conversion failed", operation="upload")
        raise HTTPException(status_code=500, detail=f"Error converting model: {e}")


def get_all_models() -> list[str]:
    try:
        if not UPLOAD_FOLDER.exists():
            return []
        config = ConfigManager().get()
        if config.chip_type == ChipType.rk3588:
            return [
                name
                for name in os.listdir(UPLOAD_FOLDER)
                if name.endswith("rknn_model") and (UPLOAD_FOLDER / name).is_dir()
            ]
        elif config.chip_type == ChipType.qcs6490:
            return [
                name
                for name in os.listdir(UPLOAD_FOLDER)
                if name.endswith(".tflite") and (UPLOAD_FOLDER / name).is_file()
            ]
        
        return []

    except Exception:
        logger.exception("Failed to list rknn models", operation="list_models")
        return []
