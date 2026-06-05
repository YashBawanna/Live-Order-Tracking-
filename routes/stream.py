"""
routes/stream.py — Server-Sent Events (SSE) endpoint.
Each browser tab that connects gets its own asyncio.Queue.
The poller in services/poller.py pushes payloads into every queue.
"""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from config import SSE_KEEPALIVE_TIMEOUT
from services.poller import connected_clients
from logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Stream"])


@router.get("/stream")
async def stream(request: Request):
    """
    SSE endpoint — browser connects here and receives live DB change events.
    Connection stays open until the browser tab is closed.
    """
    queue: asyncio.Queue = asyncio.Queue()
    connected_clients.append(queue)
    logger.info("Client connected. Total connected: %d", len(connected_clients))

    async def event_generator():
        yield 'data: {"type": "connected", "message": "Listening for order changes..."}\n\n'
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected (request ended).")
                    break
                try:
                    payload = await asyncio.wait_for(
                        queue.get(), timeout=SSE_KEEPALIVE_TIMEOUT
                    )
                    logger.info("Broadcasting event to client: %s", payload[:80])
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in connected_clients:
                connected_clients.remove(queue)
            logger.info("Client removed. Total connected: %d", len(connected_clients))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/clients")
def active_clients():
    """Utility endpoint — returns count of currently connected SSE clients."""
    count = len(connected_clients)
    logger.info("GET /clients — %d client(s) connected.", count)
    return {"connected_clients": count}
