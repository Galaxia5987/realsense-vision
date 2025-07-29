import threading

class PipelineRunner:
    def __init__(self, pipeline_type, camera, args=[]):
        self.pipeline_type = pipeline_type
        self.args = args
        self.camera = camera
        self.thread = threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        self.pipeline = self.pipeline_type(self.camera,*self.args)
        while True:
            self.pipeline.loop()

    def get_jpeg(self):
        return self.pipeline.get_jpeg()
    
    def get_output(self):
        return self.pipeline.get_output()

    def get_depth_jpeg(self):
        if hasattr(self.pipeline, 'get_depth_jpeg'):
            return self.pipeline.get_depth_jpeg()
        return None