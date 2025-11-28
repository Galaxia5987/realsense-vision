from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI

from app.core import logging_config
from core.initializer import Initializer

logger = logging_config.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RealSense Vision...", operation="startup")

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    initializer = Initializer(app)
    initializer.load_app()

    logger.info("System startup complete", operation="startup", status="ready")

    # Provide control back to FastAPI request handling
    yield

    # Shutdown section
    logger.info("Shutting down RealSense Vision", operation="shutdown")
    # stop_components()
    logger.info("Shutdown complete", operation="shutdown")