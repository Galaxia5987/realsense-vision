import threading
from utils import generate_stream_disabled_image,frames_to_jpeg_bytes, fail_restart
from config import config

disabled_jpeg = frames_to_jpeg_bytes(generate_stream_disabled_image())

class PipelineRunner:
    def __init__(self, pipeline_type, camera, args=[], set_output_callback=None):
        try:
            self.pipeline_type = pipeline_type
            self.args = args
            self.camera = camera
            self.set_output_callback = set_output_callback
            self.stop_event = threading.Event()
            self.thread = threading.Thread(target=self.loop, daemon=True).start()
        except Exception as e:
            # fail_restart()
            raise Exception("Exception while initializing pipeline: " + str(e))
    

    def loop(self):
        try:
            self.pipeline = self.pipeline_type(self.camera,*self.args)
            while not self.stop_event.is_set():
                self.pipeline.loop()
                if self.set_output_callback and hasattr(self.pipeline, 'get_output'):
                    self.set_output_callback(self.pipeline.get_output())
        except Exception as e:
            # fail_restart()
            raise Exception("Exception while on pipeline loop: " + str(e))

    def stop(self):
        self.stop_event.set()

    def get_jpeg(self):
        if config.get_config().get("color_frame", {}).get("stream", {}).get("enabled", False):
            return self.pipeline.get_jpeg()
        else:
            return disabled_jpeg
    
    def get_output(self):
        return self.pipeline.get_output()

    def get_depth_jpeg(self):
        if hasattr(self.pipeline, 'get_depth_jpeg'):
            if config.get_config().get("depth_frame", {}).get("stream", {}).get("enabled", False):
                return self.pipeline.get_depth_jpeg()
            else:
                return disabled_jpeg
        return None