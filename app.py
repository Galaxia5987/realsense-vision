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


app = None
camera = None
runner = None
publisher = None
errors = []

def reload_app():
    global app, camera, runner, publisher, errors
    stop()
        
    # Load config
    try:
        config.load_config()
    except Exception as e:
        msg = f"Failed to load config: {e}"
        logging.exception(msg)
        errors.append(msg)

    # Initialize camera
    try:
        resolution_str = config.get_config().get("camera", {}).get("resolution", {}).get("value", "640x480")
        res = list(map(int, resolution_str.split("x")))
        camera = RealSenseCamera(
            res[0],
            res[1],
            config.get_config().get("camera", {}).get("fps", 30)
        )
        camera.start()
    except Exception as e:
        msg = f"Failed to initialize camera: {e}"
        logging.exception(msg)
        errors.append(msg)
        camera = None

    # Initialize NetworkTables
    try:
        publisher = NetworkTablesPublisher(
            table_name=config.get_config().get("network_tables", {}).get("table", "RealsenseVision"),
            server=config.get_config().get("network_tables", {}).get("server", "10.0.0.2"),
        )
    except Exception as e:
        msg = f"Failed to initialize NetworkTables: {e}"
        logging.exception(msg)
        errors.append(msg)
        publisher = None

    # Initialize pipeline runner
    try:
        if camera is not None:
            pipeline_config = config.get_config().get("pipeline", {})
            pipeline_type = pipelines.pipelines.get(
                pipeline_config.get("type", ""), pipelines.RegularPipeline
            )
            runner = PipelineRunner(
                pipeline_type,
                camera,
                comma_seperated_to_list(pipeline_config.get("args", "")),
                lambda detections: publisher.publish_detections(detections) if publisher else None
            )
    except Exception as e:
        msg = f"Failed to initialize pipeline: {e}"
        logging.exception(msg)
        errors.append(msg)
        runner = None

def run():
    global app, camera, runner, publisher, errors

    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    sys.stdout = StdInterceptor("stdout")
    sys.stderr = StdInterceptor("stderr")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


    def run_ws_server():
        loop = start_ws_log_server()
        loop.run_forever()

    threading.Thread(target=run_ws_server, daemon=True).start()
    scheduler.scheduler.start()

    reloader.set_reload_function(reload_app)
    
    reload_app()
    
    # Create stream routes
    try:
        if runner is not None:
            streams.create_stream_route("/video_feed", lambda: runner.get_jpeg()) # type: ignore
            streams.create_stream_route("/depth_feed", lambda: runner.get_depth_jpeg()) # type: ignore
        else:
            streams.create_stream_route("/video_feed", lambda: disabled_jpeg)
            streams.create_stream_route("/depth_feed", lambda: disabled_jpeg)
    except Exception as e:
        msg = f"Failed to set up stream routes: {e}"
        logging.exception(msg)
        errors.append(msg)

    # Register Flask blueprints
    try:
        app.register_blueprint(streams.bp, url_prefix="/streams")
        app.register_blueprint(routes.bp)
    except Exception as e:
        msg = f"Failed to register blueprints: {e}"
        logging.exception(msg)
        errors.append(msg)

    @app.before_request
    def flash_errors():
        for error in errors:
            flash(error, 'error')
        if scheduler.flash_scheduler_message != "":
            flash(scheduler.flash_scheduler_message, 'success')
            scheduler.flash_scheduler_message = ""

    app.run(host="0.0.0.0", port=5000)
    reloader.is_finished = True

def stop():
    global camera, runner
    if runner:
        runner.stop()
    if camera:
        camera.stop()
    

    
