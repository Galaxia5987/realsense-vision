import uvicorn
from fastapi import FastAPI

from config import ConfigManager
from models.models import RootConfig

app = FastAPI(
    title="Realsense Vision",
    description="Good Vision",
    version="1.0.0",
    docs_url="/api_docs",
)

@app.post("/update_config")
def update_config(config: RootConfig):
    ConfigManager().update(config)
    return {"status": "success"}

def run():
    # uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )