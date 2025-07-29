from flask import Blueprint, Response
import uuid

bp = Blueprint('streams', __name__)
streams = []

@bp.route('/')
def home():
    return '<br>'.join(f'<a href="/streams{path}">{path}</a>' for path, endpoint in streams)

def create_stream_route(path, frame_source_func,endpoint=None):
    endpoint = endpoint or f"stream_{uuid.uuid4().hex}"
    def dynamic_stream():
        def generate():
            while True:
                frame = frame_source_func()
                if frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           frame + b'\r\n')
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    bp.add_url_rule(path, endpoint=endpoint, view_func=dynamic_stream)
    streams.append((path, endpoint))
