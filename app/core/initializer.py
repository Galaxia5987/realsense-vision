from datetime import datetime

from fastapi import FastAPI

from app.components.detection.camera_base import DISABLED_STREAM_IMAGE
from app.components.detection.camera_factory import create_camera
from app.components.detection.pipeline_runner import PipelineRunner
from app.components.detection.pipelines.pipeline_base import create_pipeline_by_name
from app.components.network_tables import NetworkTablesPublisher
from app.config import ConfigManager
from app.core import logging_config
from app.core.logging_config import get_logger
from app.server import streams
from utils.utils import frames_to_jpeg_bytes

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
        self.setup_file_logging()
        self.init_pipeline_component()
        self.setup_stream_routes()

    def stop_app(self):
        if self.runner:
            self.runner.stop_sync()
        if self.camera:
            self.camera.stop_pipeline()

    def init_camera(self):
        """Initialize camera component."""
        self.camera = create_camera()
        if self.camera and self.camera.is_connected():
            self.camera.start()
        else:
            logger.warning("Camera not connected!")

    def init_network_tables_component(self):
        logger.info("Initializing NetworkTables", operation="reload_app")
        self.publisher = NetworkTablesPublisher()

    def setup_file_logging(self):
        date = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        match_string = "unknown"
        if self.publisher:
            match_string = (
                self.publisher.get_event_name()
                + "-"
                + str(self.publisher.get_match_number())
            )
        logging_config.add_file_logging(f"logs/rs-vision-{date}-{match_string}.log")

    def init_pipeline_component(self):
        logger.info("Initializing pipeline runner", operation="reload_app")

        if self.camera is None:
            logger.warning(
                "Skipping pipeline initialization because camera failed",
                operation="reload_app",
            )
            self.runner = None
            return
        try:
            self.pipeline = create_pipeline_by_name(self.config.pipeline, self.camera)
            assert self.pipeline

            def _publish(output):
                if self.publisher:
                    self.publisher.publish_detections(output)

            self.runner = PipelineRunner(self.pipeline, _publish)
            self.runner.start()
        except TypeError:
            logger.warning(
                "Incompatible number of arguments were passed to the pipeline"
            )
        except AssertionError:
            logger.warning(f"Pipline named {self.config.pipeline} was not found.")

    def setup_stream_routes(self):
        logger.info("Configuring stream routes", operation="reload_app")

        resolution_str = ConfigManager().get().camera.resolution.value
        width, height = list(map(int, resolution_str.split("x")))
        disabled_frame = frames_to_jpeg_bytes(
            DISABLED_STREAM_IMAGE, resolution=(width, height)
        )

        def video(depth: bool):
            if not self.runner:
                return disabled_frame
            if depth:
                img = self.runner.get_depth_jpeg()
            else:
                img = self.runner.get_color_jpeg()
            return img or disabled_frame

        def video_color():
            return video(False)

        def video_depth():
            return video(True)

        streams.create_stream_route(self.app_instance, "/video_feed", video_color)
        streams.create_stream_route(self.app_instance, "/depth_feed", video_depth)

        logger.info(
            "Stream routes configured successfully",
            operation="reload_app",
            status="success",
        )
