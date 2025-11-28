from contextlib import asynccontextmanager
import threading
import logging
import sys

from app.wslog import StdInterceptor, start_ws_log_server
from app.scheduler import scheduler
from app.core.reloader import set_reload_function
from app.core.logging_config import get_logger
from app.components.supervisor import supervisor

from app.core.initialization import (
    reload_app,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app):
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