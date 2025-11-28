import sys
import asyncio
import websockets
import threading
from collections import deque
import logging
import app.core.reloader

log_buffer = deque(maxlen=500)
connected_clients = set()
lock = threading.Lock()


class StdInterceptor:
    def __init__(self, stream_name):
        self.original = getattr(sys, stream_name)
        self.stream_name = stream_name

    def write(self, message):
        if isinstance(message, bytes):
            try:
                message = message.decode('utf-8')
            except UnicodeDecodeError:
                message = message.decode('utf-8', errors='replace')

        if not isinstance(message, str):
            message = str(message)

        if not message.strip():
            return

        with lock:
            self.original.write(message)
            self.original.flush()

            cleaned = message.rstrip('\n')
            log_buffer.append(cleaned)
            if reloader.is_finished:
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.run_coroutine_threadsafe(
                        broadcast(cleaned),
                        loop
                    )
                except RuntimeError:
                    logging.warning("No running asyncio loop yet!")

    def flush(self):
        self.original.flush()


async def broadcast(message):
    if connected_clients:
        await asyncio.gather(*[
            client.send(message) for client in connected_clients if client.open
        ])

async def ws_handler(connection):
    connected_clients.add(connection)
    print("[WebSocket] Client connected")
    try:
        # Send old logs on connection
        with lock:
            for line in log_buffer:
                await connection.send(line)

        # Keep connection open
        await connection.wait_closed()
    finally:
        connected_clients.remove(connection)
        print("[WebSocket] Client disconnected")

def start_ws_log_server(host="0.0.0.0", port=8765):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start():
        print(f"[wslog] Starting WebSocket server on ws://{host}:{port}")
        return await websockets.serve(ws_handler, host, port)

    server = loop.run_until_complete(start())
    return loop
