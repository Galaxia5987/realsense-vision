from flask import Flask, request, flash
import logging
import secrets
from detection.detector import YOLODetector
import detection.pipelines as pipelines
from camera import RealSenseCamera
import scheduler
from server import streams, routes
from config import config
from utils import comma_seperated_to_list
from detection.pipeline_runner import PipelineRunner, disabled_jpeg
from network_tables import NetworkTablesPublisher
from wslog import start_ws_log_server, StdInterceptor
import threading
import sys
import reloader
import logging_config
from retry_utils import safe_init
from supervisor import supervisor

# Setup structured logging
logging_config.setup_logging(level=logging.INFO)
logger = logging_config.get_logger(__name__)


app = None
camera = None
runner = None
publisher = None
errors = []

def reload_app():
    """Reload application components with proper error handling and logging."""
    global app, camera, runner, publisher, errors
    
    logger.info("Starting application reload", operation="reload_app")
    
    # Stop existing components
    stop()
    
    # Clear errors
    errors = []
    
    # Load config
    logger.info("Loading configuration", operation="reload_app")
    try:
        config.load_config()
        logger.info("Configuration loaded successfully", operation="reload_app", status="success")
    except Exception as e:
        msg = f"Failed to load config: {e}"
        logger.exception(msg, operation="reload_app")
        errors.append(msg)

    # Initialize camera with retry logic
    logger.info("Initializing camera", operation="reload_app")
    camera, camera_error = safe_init(
        "camera",
        _init_camera,
        fallback_value=None,
        max_attempts=3
    )
    
    if camera_error:
        errors.append(f"Failed to initialize camera: {camera_error}")
    elif camera:
        # Register camera with supervisor
        supervisor.register_component(
            "camera",
            health_check=lambda: camera.is_healthy() if camera else False,
            recovery_handler=lambda: _recover_camera()
        )

    # Initialize NetworkTables with retry logic
    logger.info("Initializing NetworkTables", operation="reload_app")
    publisher, nt_error = safe_init(
        "network_tables",
        _init_network_tables,
        fallback_value=None,
        max_attempts=3
    )
    
    if nt_error:
        errors.append(f"Failed to initialize NetworkTables: {nt_error}")
    elif publisher:
        # Register NetworkTables with supervisor
        supervisor.register_component(
            "network_tables",
            health_check=lambda: publisher.is_healthy() if publisher else False,
            recovery_handler=lambda: _recover_network_tables()
        )

    # Initialize pipeline runner with retry logic
    logger.info("Initializing pipeline", operation="reload_app")
    if camera is not None:
        runner, runner_error = safe_init(
            "pipeline_runner",
            _init_pipeline_runner,
            fallback_value=None,
            max_attempts=3,
            camera=camera,
            publisher=publisher
        )
        
        if runner_error:
            errors.append(f"Failed to initialize pipeline: {runner_error}")
        elif runner:
            # Register pipeline runner with supervisor
            supervisor.register_component(
                "pipeline_runner",
                health_check=lambda: runner.is_healthy() if runner else False,
                recovery_handler=lambda: _recover_pipeline_runner()
            )
    else:
        logger.warning(
            "Skipping pipeline initialization due to camera failure",
            operation="reload_app"
        )
        runner = None
    
    logger.info(
        f"Application reload complete (errors: {len(errors)})",
        operation="reload_app",
        status="complete"
    )


def _init_camera():
    """Initialize camera component."""
    resolution_str = config.get_config().get("camera", {}).get("resolution", {}).get("value", "640x480")
    res = list(map(int, resolution_str.split("x")))
    camera = RealSenseCamera(
        res[0],
        res[1],
        config.get_config().get("camera", {}).get("fps", 30)
    )
    camera.start()
    return camera


def _init_network_tables():
    """Initialize NetworkTables component."""
    return NetworkTablesPublisher(
        table_name=config.get_config().get("network_tables", {}).get("table", "RealsenseVision"),
        server=config.get_config().get("network_tables", {}).get("server", "10.0.0.2"),
    )


def _init_pipeline_runner(camera, publisher):
    """Initialize pipeline runner component."""
    pipeline_config = config.get_config().get("pipeline", {})
    pipeline_type = pipelines.pipelines.get(
        pipeline_config.get("type", ""), pipelines.RegularPipeline
    )
    return PipelineRunner(
        pipeline_type,
        camera,
        comma_seperated_to_list(pipeline_config.get("args", "")),
        lambda detections: publisher.publish_detections(detections) if publisher else None
    )


def _recover_camera():
    """Attempt to recover the camera component."""
    global camera
    logger.info("Attempting camera recovery", operation="recovery")
    
    try:
        if camera:
            camera.stop()
        
        camera, error = safe_init(
            "camera",
            _init_camera,
            fallback_value=None,
            max_attempts=2
        )
        
        if camera and not error:
            logger.info("Camera recovery successful", operation="recovery", status="success")
            return True
        else:
            logger.error(f"Camera recovery failed: {error}", operation="recovery")
            return False
    except Exception as e:
        logger.exception(f"Error during camera recovery: {e}", operation="recovery")
        return False


def _recover_network_tables():
    """Attempt to recover NetworkTables connection."""
    global publisher
    logger.info("Attempting NetworkTables recovery", operation="recovery")
    
    try:
        publisher, error = safe_init(
            "network_tables",
            _init_network_tables,
            fallback_value=None,
            max_attempts=2
        )
        
        if publisher and not error:
            logger.info("NetworkTables recovery successful", operation="recovery", status="success")
            return True
        else:
            logger.error(f"NetworkTables recovery failed: {error}", operation="recovery")
            return False
    except Exception as e:
        logger.exception(f"Error during NetworkTables recovery: {e}", operation="recovery")
        return False


def _recover_pipeline_runner():
    """Attempt to recover the pipeline runner."""
    global runner, camera, publisher
    logger.info("Attempting pipeline runner recovery", operation="recovery")
    
    try:
        if runner:
            runner.stop()
        
        if camera is None:
            logger.warning("Cannot recover pipeline without camera", operation="recovery")
            return False
        
        runner, error = safe_init(
            "pipeline_runner",
            _init_pipeline_runner,
            fallback_value=None,
            max_attempts=2,
            camera=camera,
            publisher=publisher
        )
        
        if runner and not error:
            logger.info("Pipeline runner recovery successful", operation="recovery", status="success")
            return True
        else:
            logger.error(f"Pipeline runner recovery failed: {error}", operation="recovery")
            return False
    except Exception as e:
        logger.exception(f"Error during pipeline runner recovery: {e}", operation="recovery")
        return False

def run():
    """Main application entry point with supervisor integration."""
    global app, camera, runner, publisher, errors

    logger.info("Starting RealSense Vision application", operation="run")

    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    sys.stdout = StdInterceptor("stdout")
    sys.stderr = StdInterceptor("stderr")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Start WebSocket log server
    def run_ws_server():
        loop = start_ws_log_server()
        loop.run_forever()

    threading.Thread(target=run_ws_server, daemon=True).start()
    logger.info("WebSocket log server started", operation="run")
    
    # Start scheduler
    scheduler.scheduler.start()
    logger.info("Scheduler started", operation="run")

    # Set reload function
    reloader.set_reload_function(reload_app)
    
    # Initial application load
    reload_app()
    
    # Start supervisor for component monitoring
    logger.info("Starting component supervisor", operation="run")
    supervisor.start()
    
    # Create stream routes
    logger.info("Setting up stream routes", operation="run")
    try:
        if runner is not None:
            streams.create_stream_route("/video_feed", lambda: runner.get_jpeg()) # type: ignore
            streams.create_stream_route("/depth_feed", lambda: runner.get_depth_jpeg()) # type: ignore
        else:
            streams.create_stream_route("/video_feed", lambda: disabled_jpeg)
            streams.create_stream_route("/depth_feed", lambda: disabled_jpeg)
        logger.info("Stream routes configured", operation="run", status="success")
    except Exception as e:
        msg = f"Failed to set up stream routes: {e}"
        logger.exception(msg, operation="run")
        errors.append(msg)

    # Register Flask blueprints
    logger.info("Registering Flask blueprints", operation="run")
    try:
        app.register_blueprint(streams.bp, url_prefix="/streams")
        app.register_blueprint(routes.bp)
        logger.info("Flask blueprints registered", operation="run", status="success")
    except Exception as e:
        msg = f"Failed to register blueprints: {e}"
        logger.exception(msg, operation="run")
        errors.append(msg)

    @app.before_request
    def flash_errors():
        for error in errors:
            flash(error, 'error')
        if scheduler.flash_scheduler_message != "":
            flash(scheduler.flash_scheduler_message, 'success')
            scheduler.flash_scheduler_message = ""

    logger.info(
        "Starting Flask application on 0.0.0.0:5000",
        operation="run", status="starting"
    )
    
    try:
        app.run(host="0.0.0.0", port=5000)
    except Exception as e:
        logger.exception(f"Flask application crashed: {e}", operation="run")
    finally:
        reloader.is_finished = True
        supervisor.stop()
        logger.info("Application shutdown complete", operation="run")

def stop():
    """Stop all application components gracefully."""
    global camera, runner
    
    logger.info("Stopping application components", operation="stop")
    
    if runner:
        try:
            logger.debug("Stopping pipeline runner", operation="stop")
            runner.stop()
            logger.debug("Pipeline runner stopped", operation="stop")
        except Exception as e:
            logger.exception(f"Error stopping pipeline runner: {e}", operation="stop")
    
    if camera:
        try:
            logger.debug("Stopping camera", operation="stop")
            camera.stop()
            logger.debug("Camera stopped", operation="stop")
        except Exception as e:
            logger.exception(f"Error stopping camera: {e}", operation="stop")
    
    logger.info("Application components stopped", operation="stop", status="complete")
    

    
