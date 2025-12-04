import asyncio
import threading
import cv2
import numpy as np
import subprocess
import logging


def frames_to_jpeg_bytes(frame, resolution=(640, 480)):
    resized = cv2.resize(frame, resolution)
    ret, jpeg = cv2.imencode(".jpg", resized)
    if not ret:
        return None
    return jpeg.tobytes()


def unflatten_dict(flat, sep="."):
    result = {}
    for key, value in flat.items():
        parts = key.split(sep)
        d = result
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value
    return result


def flatten_with_types(d, parent_key="", sep="."):
    items = {}
    for k, v in d.items():
        full_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            # Handle enum case separately
            if "enum" in v and "value" in v and isinstance(v["enum"], list):
                items[full_key + ".value"] = type(v["value"])
            else:
                items.update(flatten_with_types(v, full_key, sep=sep))
        else:
            items[full_key] = type(v)
    return items


def get_enum_options_by_path(d, path):
    for key in path:
        d = d.get(key, {})
    return d.get("enum", [])


def comma_seperated_to_list(value):
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def generate_stream_disabled_image(width=640, height=480, text="Stream Disabled"):
    image = np.zeros((height, width, 3), dtype=np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    font_color = (255, 255, 255)  # white
    thickness = 2

    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size

    x = (width - text_width) // 2
    y = (height + text_height) // 2

    cv2.putText(
        image,
        text,
        (x, y),
        font,
        font_scale,
        font_color,
        thickness,
        lineType=cv2.LINE_AA,
    )

    return image


def restart_service():
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "realsense-vision.service"], check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.exception("Failed to restart service: %s", e)
        return False


def singleton(class_):
    instances = {}

    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]

    return getinstance


# Global background loop
_background_loop = None
_background_thread = None


def _ensure_background_loop():
    global _background_loop, _background_thread

    if _background_loop is not None:
        return _background_loop

    _background_loop = asyncio.new_event_loop()

    def run_loop():
        _background_loop.run_forever()  # type: ignore

    _background_thread = threading.Thread(target=run_loop, daemon=True)
    _background_thread.start()

    return _background_loop


class AsyncLoopBase:
    def __init__(self, interval):
        self.interval = interval
        self._task = None
        self._stop = asyncio.Event()

    def on_iteration(self):
        raise NotImplementedError

    async def _runner(self):
        try:
            while not self._stop.is_set():
                await asyncio.to_thread(self.on_iteration)

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
                except asyncio.TimeoutError:
                    pass

        except asyncio.CancelledError:
            pass

    def start(self):
        """Start the loop from sync or async context."""
        if self._task:
            # Already running or previously started
            if hasattr(self._task, "done") and not self._task.done():
                return

        self._stop.clear()

        try:
            loop = asyncio.get_running_loop()
            # Async context
            self._task = loop.create_task(self._runner())
        except RuntimeError:
            # No running loop, sync context
            loop = _ensure_background_loop()
            self._task = asyncio.run_coroutine_threadsafe(self._runner(), loop)

    async def stop(self):
        """Async stop, awaits the task."""
        self._stop.set()

        if isinstance(self._task, asyncio.Task):
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def stop_sync(self):
        """Sync stop that waits for completion."""
        self._stop.set()

        if not self._task:
            return

        if hasattr(self._task, "result"):
            # Threadsafe future
            try:
                self._task.result()
            except Exception:
                pass
