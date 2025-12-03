from contextlib import asynccontextmanager
import pkgutil
import importlib
from app.components.detection import pipelines

from fastapi import FastAPI

from app.core import logging_config
from app.core.initializer import Initializer

logger = logging_config.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RealSense Vision...", operation="startup")

    # Discover and register all pipelines automaticlly
    for _, module_name, _ in pkgutil.iter_modules(pipelines.__path__):
        if module_name == "pipeline_base":
            continue
        importlib.import_module(f"app.components.detection.pipelines.{module_name}")

    initializer = Initializer(app)
    initializer.load_app()

    logger.info("System startup complete", operation="startup", status="ready")

    # Provide control back to FastAPI request handling
    yield

    # Shutdown section
    logger.info("Shutting down RealSense Vision", operation="shutdown")
    initializer.stop_app()
    logger.info("Shutdown complete", operation="shutdown")
