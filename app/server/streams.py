import asyncio
import uuid
from typing import Callable

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

router = APIRouter(prefix="/streams")

streams: list[tuple[str, str]] = []


@router.get("/", response_class=HTMLResponse)
async def home():
    links = [f'<a href="/streams{path}">{path}</a>' for path, endpoint in streams]
    return "<br>".join(links)


def create_stream_route(
    app_instance: FastAPI,
    path: str,
    frame_source_func: Callable,
    endpoint: str | None = None,
    fps: int = 30
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
    frame_delay = 1.0 / fps

    async def dynamic_stream():
        async def generate():
            loop = asyncio.get_event_loop()

            while True:
                start_time = loop.time()

                # Run the frame source in an executor if it's blocking
                frame = await asyncio.to_thread(frame_source_func)

                if frame is not None:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame +
                        b"\r\n"
                    )
                    end_time = loop.time()
                    processing_time = end_time - start_time
                    sleep_time = max(0, frame_delay - processing_time)
                    await asyncio.sleep(sleep_time)
                else:
                    # Small delay if no frame to prevent tight loop
                    await asyncio.sleep(0.01)

        return StreamingResponse(
            generate(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    # Add route dynamically
    app_instance.add_api_route(
        router.prefix + path,
        dynamic_stream,
        methods=["GET"],
        name=endpoint,
        response_class=StreamingResponse,
    )

    streams.append((path, endpoint))