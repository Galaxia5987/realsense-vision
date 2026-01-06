import asyncio
import threading

# Global background loop
_background_loop = None
_background_thread = None


def _ensure_background_loop():
    global _background_loop, _background_thread

    if _background_loop is not None:
        return _background_loop

    _background_loop = asyncio.new_event_loop()

    def run_loop():
        try:
            _background_loop.run_forever()  # type: ignore
        finally:
            _background_loop.close()  # type: ignore

    _background_thread = threading.Thread(target=run_loop, daemon=True)
    _background_thread.start()

    return _background_loop


def shutdown_background_loop(timeout: float = 1.0):
    """Stop the global background loop and thread if they are running."""
    global _background_loop, _background_thread
    if _background_loop is None:
        return
    if _background_loop.is_running():
        _background_loop.call_soon_threadsafe(_background_loop.stop)
    if _background_thread is not None:
        _background_thread.join(timeout=timeout)
    _background_loop = None
    _background_thread = None


class AsyncLoopBase:
    def __init__(self, interval):
        self.interval = interval
        self._task = None
        self._loop = None
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
        self._loop = loop

    async def stop(self):
        """Async stop, awaits the task."""
        self._stop.set()

        if isinstance(self._task, asyncio.Task):
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def stop_sync(self):
        """Sync stop that waits for completion."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop.set)
        else:
            self._stop.set()

        if not self._task:
            return

        if hasattr(self._task, "result"):
            # Threadsafe future
            try:
                self._task.result()
            except Exception:
                pass
        self._task = None
