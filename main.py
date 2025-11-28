from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.core import logging_config
from app.core.app_lifespan import lifespan
from server import routes, streams

logger = logging_config.get_logger(__name__)

app = FastAPI(
    title="Realsense Vision",
    version="1.0.0",
    docs_url="/api_docs",
    lifespan=lifespan,
)

# static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# routers
app.include_router(routes.router)
app.include_router(streams.router, prefix="/streams")


@app.get("/")
def root():
    return {"status": "running", "application": "Realsense Vision"}

def run():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
