import asyncio
import os
import time
from fastapi import File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse

from app.config import ConfigManager
from app.core import logging_config
from convert_model import async_convert_model

UPLOAD_FOLDER = "uploads"

logger = logging_config.get_logger(__name__)


async def upload_model(file: UploadFile = File(...)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No selected file")

        filename = file.filename

        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        if not filename.endswith(".pt"):
            filename += ".pt"

        file_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))

        if os.path.exists(file_path):
            os.remove(file_path)

        # Save uploaded file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Finished uploading {file_path}!", operation="upload")

        time.sleep(1)
        chip = ConfigManager().get().rknn_chip_type
        # reset_realtime()
        asyncio.create_task(async_convert_model(file_path, chip))

        return RedirectResponse(url="/upload_progress", status_code=303)
    except Exception as e:
        logger.exception("Model conversion failed", operation="upload")
        raise HTTPException(status_code=500, detail=f"Error converting model: {e}")
