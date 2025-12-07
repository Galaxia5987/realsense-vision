from typing import Callable

import app.core.logging_config as logging_config
from app.components.detection.pipelines.pipeline_base import PipelineBase
from app.config import ConfigManager
from utils import AsyncLoopBase, frames_to_jpeg_bytes, generate_stream_disabled_image

logger = logging_config.get_logger(__name__)

""" Retarded JPEG """
disabled_jpeg = frames_to_jpeg_bytes(generate_stream_disabled_image())

LOOP_INTERVAL = 0.01  # 100 Hz


class PipelineRunner(AsyncLoopBase):
    def __init__(self, pipeline: PipelineBase, set_output_callback: Callable):
        super().__init__(LOOP_INTERVAL)
        logger.info(
            f"Initializing pipeline runner with {getattr(pipeline, 'name', '<unknown>')}",
            operation="init",
        )

        self.config = ConfigManager().get()
        self.pipeline = pipeline
        self.set_output_callback = set_output_callback
        assert set_output_callback, "set_output callback was empty! "

        logger.info(
            "Pipeline runner initialized successfully",
            operation="init",
            status="success",
        )

    def on_iteration(self):
        try:
            self.pipeline.iterate()

            output = self.pipeline.get_output()
            try:
                self.set_output_callback(output)
            except Exception as callback_exc:
                logger.error(
                    f"set_output_callback failed: {callback_exc}",
                    operation="loop",
                    exc_info=True,
                )
        except Exception as e:
            logger.error(
                f"Pipeline iteration failed: {e}", operation="loop", exc_info=True
            )

    def get_jpeg(self):
        """Get JPEG-encoded color frame."""
        if ConfigManager().get().color_frame.stream_enabled:
            return self.pipeline.get_jpeg()
        return None

    def get_output(self):
        """Get pipeline output. Returns None if using a non depth pipeline!"""
        return self.pipeline.get_output()

    def get_depth_jpeg(self):
        """Get JPEG-encoded depth frame."""
        if self.config.depth_frame.stream_enabled:
            return self.pipeline.get_depth_jpeg()
        return None
