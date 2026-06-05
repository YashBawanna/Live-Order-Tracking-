"""
SSE Stream Route
----------------
Manages the /stream endpoint and the /clients utility endpoint.

The ChangeLogPoller is injected via FastAPI's dependency system.
This route only handles:
  - Registering / deregistering client queues with the poller
  - Streaming SSE payloads from the queue to the HTTP response
  - Sending keepalive pings to prevent proxy timeouts

WHY inject the poller:
  - Single Responsibility: the route doesn't own the poller lifecycle.
  - Testability: swap in a mock poller during tests.
"""

import asyncio
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse

from services.poller import ChangeLogPoller
from dependencies import get_poller
from config import SSE_KEEPALIVE_TIMEOUT

router = APIRouter(tags=["stream"])


# ---------------------------------------------------------------------------
# GET /stream  — SSE endpoint
# ---------------------------------------------------------------------------

@router.get("/stream")
async def stream(
    request: Request,
    poller: ChangeLogPoller = Depends(get_poller),
):
    """
    Long-lived SSE connection.

    Each connecting browser tab gets its own asyncio.Queue. The poller
    puts JSON payloads into every queue; this generator yields them as
    SSE-formatted strings.

    Keepalive comments (": keepalive") are sent every SSE_KEEPALIVE_TIMEOUT
    seconds to prevent reverse proxies from closing idle connections.
    """
    queue: asyncio.Queue = asyncio.Queue()
    await poller.add_client(queue)
    print(f"🟢 Client connected. Total: {poller.client_count}")

    async def event_generator():
        # Immediate handshake so the browser knows the connection is live
        yield 'data: {"type": "connected", "message": "Listening for order changes..."}\n\n'
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Block until a payload arrives or the keepalive timeout fires
                    payload = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_TIMEOUT)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # SSE comment — keeps the TCP connection alive through proxies
                    yield ": keepalive\n\n"
        finally:
            # Always deregister, whether the client disconnected cleanly or not
            await poller.remove_client(queue)
            print(f"🔴 Client disconnected. Total: {poller.client_count}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",       # No intermediary caching of the stream
            "X-Accel-Buffering": "no",         # Disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# GET /clients  — diagnostic utility
# ---------------------------------------------------------------------------

@router.get("/clients")
async def active_clients(poller: ChangeLogPoller = Depends(get_poller)):
    """Return the current number of connected SSE clients. Useful for monitoring."""
    return {"connected_clients": poller.client_count}
