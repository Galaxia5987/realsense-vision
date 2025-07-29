from flask import Flask
from detection.detector import YOLODetector
import detection.pipelines as pipelines
from camera import RealSenseCamera
from server import streams, routes
from config import config
from utils import comma_seperated_to_list
from detection.pipeline_runner import PipelineRunner

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' # TODO: Generate secret

config.load_config()

camera = RealSenseCamera(config.get_config().get("camera", {}).get("width", 1280),
                         config.get_config().get("camera", {}).get("height", 720),
                         config.get_config().get("camera", {}).get("fps", 30))

pipeline_config = config.get_config().get("pipeline", {})

pipeline_type = pipelines.pipelines.get(pipeline_config.get("type",""), pipelines.ColorPipeline)

camera.start()

runner = PipelineRunner(pipeline_type,camera,comma_seperated_to_list(pipeline_config.get("args", "")))

if config.get_config().get("color_frame", {}).get("stream", {}).get("enabled", False):
    streams.create_stream_route("/video_feed", lambda: runner.get_jpeg())
if config.get_config().get("depth_frame", {}).get("stream", {}).get("enabled", False):
    streams.create_stream_route("/depth_feed", lambda: runner.get_depth_jpeg())

app.register_blueprint(streams.bp, url_prefix='/streams')
app.register_blueprint(routes.bp)

app.run(host='0.0.0.0', port=5000)

