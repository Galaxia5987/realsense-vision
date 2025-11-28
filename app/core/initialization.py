from app.components.detection.camera import RealSenseCamera

from app.config import ConfigManager

from components.network_tables import NetworkTablesPublisher
from server import streams
from core.logging_config import get_logger

logger = get_logger(__name__)

camera = None
runner = None
publisher = None

def reload_app():
    logger.info("Starting application reload", operation="reload_app")

    init_camera_component()
    init_network_tables_component()
    init_pipeline_component()
    setup_stream_routes()

def _init_camera():
    """Initialize camera component."""
    resolution_str = ConfigManager().get().camera.resolution.value
    res = list(map(int, resolution_str.split("x")))
    camera = RealSenseCamera(
        res[0],
        res[1],
        ConfigManager().get().camera.fps
    )
    camera.start()
    return camera

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

def init_camera_component():
    global camera, errors
    logger.info("Initializing camera", operation="reload_app")

    camera, cam_error = safe_init(
        "camera",
        _init_camera,
        fallback_value=None,
        max_attempts=3
    )

    if cam_error:
        errors.append(f"Failed to initialize camera: {cam_error}")
    elif camera:
        supervisor.register_component(
            "camera",
            health_check=lambda: camera.is_healthy() if camera else False,
            recovery_handler=lambda: _recover_camera()
        )

def init_network_tables_component():
    logger.info("Initializing NetworkTables", operation="reload_app")

    # Init Networkstables
    nt_instance = NetworkTablesPublisher()

    supervisor.register_component(
        "network_tables",
        health_check=lambda: NetworkTablesPublisher().is_healthy(),
        recovery_handler=lambda: (nt_instance.__init__() or True)
    )

def init_pipeline_component():
    global runner, errors, camera, publisher
    logger.info("Initializing pipeline runner", operation="reload_app")

    if camera is None:
        logger.warning("Skipping pipeline initialization because camera failed", operation="reload_app")
        runner = None
        return

    runner, runner_error = safe_init(
        "pipeline_runner",
        init_pipeline_runner,
        fallback_value=None,
        max_attempts=3,
        camera=camera,
        publisher=publisher
    )

    if runner_error:
        errors.append(f"Failed to initialize pipeline runner: {runner_error}")
    elif runner:
        supervisor.register_component(
            "pipeline_runner",
            health_check=lambda: runner.is_healthy() if runner else False,
            recovery_handler=lambda: recover_pipeline_runner()
        )

def setup_stream_routes():
    global runner, errors
    logger.info("Configuring stream routes", operation="reload_app")

    try:
        if runner is not None:
            streams.create_stream_route("/video_feed", lambda: runner.get_jpeg())
            streams.create_stream_route("/depth_feed", lambda: runner.get_depth_jpeg())
        else:
            streams.create_stream_route("/video_feed", lambda: disabled_jpeg)
            streams.create_stream_route("/depth_feed", lambda: disabled_jpeg)

        logger.info("Stream routes configured successfully", operation="reload_app", status="success")

    except Exception as e:
        msg = f"Failed to set up stream routes: {e}"
        logger.exception(msg, operation="reload_app")
        errors.append(msg)
