from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from app.config import ConfigManager

from app.core import logging_config
from app.core.app_lifespan import lifespan
from app.server import streams

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
# app.include_router(routes.router)
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

def run():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
