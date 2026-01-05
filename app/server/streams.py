import asyncio
import uuid
from dataclasses import dataclass
from typing import Callable
from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import queue
import threading

router = APIRouter(prefix="/streams")
streams: list[tuple[str, str]] = []
_stream_workers = {}


@dataclass
class _StreamWorker:
    stop_event: threading.Event
    thread: threading.Thread

    def stop(self, timeout: float = 1.0):
        self.stop_event.set()
        self.thread.join(timeout=timeout)

def create_stream_route(
    app_instance: FastAPI,
    path: str,
    frame_source_func: Callable,
    endpoint: str | None = None,
):
    """
    Dynamically create a streaming route for video frames.
    """
    endpoint = endpoint or f"stream_{uuid.uuid4().hex}"

    if path in _stream_workers:
        # Avoid spawning duplicate capture threads on reloads.
        return
    
    # Shared frame buffer with fixed size to prevent memory buildup
    frame_queue = queue.Queue(maxsize=2)  # Only keep latest 2 frames
    stop_event = threading.Event()
    
    def frame_capture_worker():
        """Background thread that captures frames continuously"""
        while not stop_event.is_set():
            try:
                frame = frame_source_func()
                if frame is not None:
                    # Non-blocking put - if queue full, drop oldest frame
                    try:
                        frame_queue.put_nowait(frame)
                    except queue.Full:
                        # Drop old frame and add new one
                        try:
                            frame_queue.get_nowait()
                            frame_queue.put_nowait(frame)
                        except:
                            pass
            except Exception as e:
                print(f"Frame capture error: {e}")
    
    # Start background thread once
    capture_thread = threading.Thread(target=frame_capture_worker, daemon=True)
    capture_thread.start()
    _stream_workers[path] = _StreamWorker(stop_event=stop_event, thread=capture_thread)
    
    async def dynamic_stream():
        async def generate():
            try:
                while True:
                    # Get frame from queue without blocking
                    try:
                        frame = await asyncio.to_thread(frame_queue.get, timeout=1.0)
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                            + frame +
                            b"\r\n"
                        )
                    except queue.Empty:
                        await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                # Client disconnected - cleanup happens automatically
                pass
        
        return StreamingResponse(
            generate(), media_type="multipart/x-mixed-replace; boundary=frame"
        )
    
    app_instance.add_api_route(
        router.prefix + path,
        dynamic_stream,
        methods=["GET"],
        name=endpoint,
        response_class=StreamingResponse,
    )
    streams.append((path, endpoint))


def stop_all_streams(timeout: float = 1.0):
    """Stop all background capture threads."""
    for worker in list(_stream_workers.values()):
        worker.stop(timeout=timeout)
    _stream_workers.clear()
