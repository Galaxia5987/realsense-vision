from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from app.core import logging_config
from app.config import ConfigManager

from app.core import logging_config
from app.config import ConfigManager

from app.core.app_lifespan import lifespan
from app.core.uploader import upload_model
from app.server import streams
from utils import restart_service

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
app.include_router(streams.router, prefix="/streams")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
    "index.html",
    {
        "request": request,
        "cfg": ConfigManager().get()
    }
)

@app.get('/restart')
async def restart():
    restart_service()
    return RedirectResponse(url='/', status_code=303)

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    await upload_model(file)

def run():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
