from fastapi import FastAPI
from app.components.detection.camera import RealSenseCamera

from app.config import ConfigManager
from app.components.detection.pipeline_runner import PipelineRunner, disabled_jpeg
from app.components.detection.pipelines.pipeline_base import create_pipeline_by_name
from app.components.network_tables import NetworkTablesPublisher
from app.server import streams
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class Initializer:
    camera = None
    runner = None
    publisher = None

    def __init__(self, app_instance: FastAPI) -> None:
        self.app_instance = app_instance
        self.config = ConfigManager().get()

    def load_app(self):
        logger.info("Starting application reload", operation="reload_app")

        self.init_camera()
        self.init_network_tables_component()
        self.init_pipeline_component()
        self.setup_stream_routes()

    def init_camera(self):
        """Initialize camera component."""
        resolution_str = ConfigManager().get().camera.resolution.value
        res = list(map(int, resolution_str.split("x")))
        self.camera = RealSenseCamera(
            res[0],
            res[1],
            ConfigManager().get().camera.fps
        )
        if self.camera.realsense_connected():
            self.camera.start()

    def init_network_tables_component(self):
        logger.info("Initializing NetworkTables", operation="reload_app")
        NetworkTablesPublisher()

    def init_pipeline_component(self):
        logger.info("Initializing pipeline runner", operation="reload_app")

        if self.camera is None:
            logger.warning("Skipping pipeline initialization because camera failed", operation="reload_app")
            self.runner = None
            return
        
        self.runner = create_pipeline_by_name(self.config.pipeline, self.camera)
        

    def setup_stream_routes(self):
        logger.info("Configuring stream routes", operation="reload_app")

        streams.create_stream_route(self.app_instance,"/video_feed", lambda: self.runner.get_jpeg() if self.runner else disabled_jpeg)
        streams.create_stream_route(self.app_instance,"/depth_feed", lambda: self.runner.get_jpeg() if self.runner else disabled_jpeg)

        logger.info("Stream routes configured successfully", operation="reload_app", status="success")
