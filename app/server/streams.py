from fastapi import FastAPI, APIRouter
from fastapi.responses import StreamingResponse, HTMLResponse
import uuid
from typing import Callable, List, Tuple
import asyncio

router = APIRouter()

streams: List[Tuple[str, str]] = []


@router.get('/', response_class=HTMLResponse)
async def home():
    links = [f'<a href="/streams{path}">{path}</a>' for path, endpoint in streams]
    return '<br>'.join(links)


def create_stream_route(
    app_instance: FastAPI,
    path: str,
    frame_source_func: Callable,
    endpoint: str | None = None
):
    """
    Dynamically create a streaming route for video frames.
    
    Args:
        app_instance: The FastAPI app instance
        path: URL path for the stream
        frame_source_func: Function that returns frame bytes
        endpoint: Optional endpoint name (auto-generated if not provided)
    """
    endpoint = endpoint or f"stream_{uuid.uuid4().hex}"
    
    async def dynamic_stream():
        async def generate():
            while True:
                # Run the frame source in an executor if it's blocking
                frame = await asyncio.to_thread(frame_source_func)
                
                if frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           frame + b'\r\n')
                else:
                    # Small delay if no frame to prevent tight loop
                    await asyncio.sleep(0.01)
        
        return StreamingResponse(
            generate(),
            media_type='multipart/x-mixed-replace; boundary=frame'
        )
    
    # Add route dynamically
    router.add_api_route(
        path,
        dynamic_stream,
        methods=["GET"],
        name=endpoint,
        response_class=StreamingResponse
    )
    
    streams.append((path, endpoint))