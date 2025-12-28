import asyncio
import logging

import uvicorn
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.components.detection.pipelines.pipeline_base import get_all_pipeline_names
from app.config import ConfigManager
from app.core import logging_config
from app.core.app_lifespan import lifespan
from app.core.logging_config import get_last_log
from app.core.uploader import get_all_models, upload_model
from app.server import streams
from convert_model import realtime
from models.log_model import Log
from models.models import RootConfig, default_config
from utils.utils import restart_service

logging_config.setup_logging()

logger = logging_config.get_logger(__name__)

app = FastAPI(
    title="Realsense Vision",
    version="1.0.0",
    docs_url="/api_docs",
    lifespan=lifespan,
)

# templates
templates = Jinja2Templates(directory="templates")

# static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# routers
app.include_router(streams.router)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "cfg": ConfigManager().get(),
            "pipelines": get_all_pipeline_names(),
            "log_level": logging_config.get_root_level(),
            "models": get_all_models(),
        },
    )


@app.get("/favicon.png", include_in_schema=False)
def favicon():
    return FileResponse("favicon.png")


@app.post("/update_config")
async def update_config(data: RootConfig):
    ConfigManager().update(data)
    return {"status": "success"}


@app.get("/restart")
async def restart():
    async def _delayed_restart():
        await asyncio.sleep(1)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, restart_service)

    asyncio.create_task(_delayed_restart())
    return RedirectResponse(url="/", status_code=303)


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    return await upload_model(file)


@app.get("/get_upload_progress")
async def get_upload_progress():
    return HTMLResponse("".join(realtime))


@app.get("/upload_progress")
async def upload_progress(request: Request):
    return templates.TemplateResponse("upload_progress.html", {"request": request})


@app.post("/restore_config")
async def restore_config():
    ConfigManager().update(default_config)
    return {"status": "success"}


@app.get("/logs")
async def log_endpoint(force_latest: bool):
    return Log(log=get_last_log(force_latest), latency=app.state.initializer.runner.latency)


@app.post("/set_log_level")
async def set_log_level(level: str):
    logging_config.set_root_level(getattr(logging, level))
    return {"status": "success"}


def run():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
