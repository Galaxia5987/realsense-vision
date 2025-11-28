from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI

from app.core import logging_config
from app.core.reloader import set_reload_function
from app.components.supervisor import supervisor

from app.core.initialization import reload_app

logger = logging_config.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RealSense Vision...", operation="startup")

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Register reload handler
    set_reload_function(reload_app)

    # Initial load
    reload_app()

    # Start supervisor
    logger.info("Starting component supervisor", operation="startup")
    supervisor.start()

    # READY
    logger.info("System startup complete", operation="startup", status="ready")

    # Provide control back to FastAPI request handling
    yield

    # Shutdown section
    logger.info("Shutting down RealSense Vision", operation="shutdown")
    # stop_components()
    logger.info("Shutdown complete", operation="shutdown")