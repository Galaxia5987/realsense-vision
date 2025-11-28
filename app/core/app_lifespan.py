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
    stop_components
)

logger = get_logger(__name__)


def _start_websocket_log_server():
    """Launch WS logging server in its own thread."""
    loop = start_ws_log_server()
    loop.run_forever()


@asynccontextmanager
async def lifespan(app):
    logger.info("Starting RealSense Vision...", operation="startup")

    # Intercept stdout/stderr to WebSocket logger
    sys.stdout = StdInterceptor("stdout")
    sys.stderr = StdInterceptor("stderr")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Start WebSocket logging thread
    threading.Thread(
        target=_start_websocket_log_server,
        daemon=True
    ).start()
    logger.info("WebSocket log server started", operation="startup")

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started", operation="startup")

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
    stop_components()
    logger.info("Shutdown complete", operation="shutdown")