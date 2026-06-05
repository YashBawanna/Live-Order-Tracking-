"""
services/poller.py — Background poller that reads change_log
and broadcasts events to all connected SSE clients.
"""
 
import asyncio
import json
 
from config import POLL_INTERVAL as POLL_INTERVAL_SECONDS
from database import get_db_connection
from logger import get_logger
 
logger = get_logger(__name__)
 
# ---------------------------------------------------------------------------
# Client registry — lives HERE, not in dependencies.py
# routes/stream.py imports connected_clients from here
# ---------------------------------------------------------------------------
connected_clients: list[asyncio.Queue] = []
 
 
# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------
async def broadcast(payload: str):
    """Push a JSON string to every connected client's queue."""
    dead = []
    for q in connected_clients:
        try:
            await q.put(payload)
        except Exception as e:
            logger.warning("Failed to push to a client queue: %s", e)
            dead.append(q)
    for q in dead:
        connected_clients.remove(q)
        logger.info("Removed dead client. Total: %d", len(connected_clients))
 
 
# ---------------------------------------------------------------------------
# Sync DB fetch (runs in thread executor)
# ---------------------------------------------------------------------------
def fetch_unprocessed_changes() -> list[dict]:
    """
    Fetch all change_log rows where is_processed = 0,
    mark them as processed, and return them as dicts.
    """
    conn   = get_db_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        SELECT log_id, operation, order_id, customer_name,
               product_name, status,
               CONVERT(VARCHAR, changed_at, 126) AS changed_at
        FROM change_log
        WHERE is_processed = 0
        ORDER BY log_id
    """)
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    changes = [dict(zip(cols, row)) for row in rows]
 
    if changes:
        ids          = [c["log_id"] for c in changes]
        placeholders = ",".join("?" * len(ids))
        cursor.execute(
            f"UPDATE change_log SET is_processed = 1 WHERE log_id IN ({placeholders})",
            ids,
        )
        conn.commit()
        logger.info(
            "Fetched & marked %d change(s): %s",
            len(changes),
            [f"{c['operation']} order#{c['order_id']}" for c in changes],
        )
 
    conn.close()
    return changes
 
 
# ---------------------------------------------------------------------------
# Main poller loop
# ---------------------------------------------------------------------------
async def poll_change_log():
    """
    Runs forever in the background.
    Every POLL_INTERVAL_SECONDS it checks change_log for new rows
    and broadcasts them to all connected SSE clients.
    """
    logger.info("Change-log poller started. Interval: %ds", POLL_INTERVAL_SECONDS)
    loop = asyncio.get_event_loop()
 
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
 
        if not connected_clients:
            continue                    # no one listening — skip DB call
 
        try:
            changes = await loop.run_in_executor(None, fetch_unprocessed_changes)
            for change in changes:
                await broadcast(json.dumps(change))
 
        except Exception as exc:
            logger.error("Poller error: %s", exc, exc_info=True)
 
 
# ---------------------------------------------------------------------------
# ChangeLogPoller class — wraps poll_change_log() so dependencies.py
# can instantiate it and main.py can call poller.run()
# ---------------------------------------------------------------------------
class ChangeLogPoller:
    """
    Thin wrapper so the rest of the app can treat the poller as an object.
    dependencies.py creates one instance; main.py calls .run() on it.
    """
 
    def __init__(self, repository=None):
        # repository arg accepted for compatibility with dependencies.py
        # actual DB access is handled inside fetch_unprocessed_changes()
        pass
 
    async def run(self):
        """Start the polling loop."""
        await poll_change_log()