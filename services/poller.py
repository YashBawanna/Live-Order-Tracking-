"""
Change Log Poller Service
--------------------------
Encapsulates the background SSE broadcast loop as a class.

WHY a class instead of bare functions:
  - Single Responsibility: ChangeLogPoller owns exactly one job — watch the
    change_log table and push updates to connected clients.
  - Encapsulation: the client list and the asyncio lock live inside the object,
    not as module-level globals.
  - Testability: inject a mock repository and a mock client list to unit-test
    broadcast logic without touching a real DB.

Dependency Inversion in action:
  ChangeLogPoller depends on AbstractChangeLogRepository (the abstraction),
  not on SqlServerChangeLogRepository (the detail). Swap the repo → poller
  keeps working unchanged.
"""

import asyncio
import json

from config import POLL_INTERVAL
from repositories.change_log import AbstractChangeLogRepository


class ChangeLogPoller:
    """
    Background service that polls change_log and broadcasts to SSE clients.

    Lifecycle:
        poller = ChangeLogPoller(repo)
        task   = asyncio.create_task(poller.run())   # start
        task.cancel()                                 # stop (on shutdown)

    Client management:
        poller.add_client(queue)      # called by the SSE endpoint on connect
        poller.remove_client(queue)   # called by the SSE endpoint on disconnect
    """

    def __init__(self, repository: AbstractChangeLogRepository) -> None:
        """
        Args:
            repository: Any concrete AbstractChangeLogRepository.
                        Injected here so the poller never imports a specific DB driver.
        """
        self._repo = repository
        self._clients: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()  # Guards mutations of _clients across coroutines

    # ------------------------------------------------------------------
    # Client registration (called by SSE route)
    # ------------------------------------------------------------------

    async def add_client(self, queue: asyncio.Queue) -> None:
        """Register a new SSE client queue. Thread-safe via asyncio lock."""
        async with self._lock:
            self._clients.append(queue)

    async def remove_client(self, queue: asyncio.Queue) -> None:
        """Deregister a client queue on disconnect. Thread-safe via asyncio lock."""
        async with self._lock:
            if queue in self._clients:
                self._clients.remove(queue)

    @property
    def client_count(self) -> int:
        """Current number of connected SSE clients (snapshot, not locked)."""
        return len(self._clients)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Infinite poll loop. Designed to run as an asyncio background task.

        Flow each iteration:
          1. Sleep POLL_INTERVAL seconds (non-blocking).
          2. Skip DB round-trip if no clients are connected.
          3. Offload the synchronous DB fetch to a thread executor.
          4. Broadcast each change to all queued clients.
          5. Mark changes as processed in the DB.
        """
        print("🔄 ChangeLogPoller started.")
        while True:
            await asyncio.sleep(POLL_INTERVAL)

            async with self._lock:
                has_clients = bool(self._clients)

            if not has_clients:
                continue  # Skip DB work when nobody is listening

            try:
                loop = asyncio.get_running_loop()

                # Run sync DB call off the event loop thread
                changes = await loop.run_in_executor(None, self._repo.fetch_unprocessed)

                if changes:
                    await self._broadcast(changes)
                    # Acknowledge AFTER broadcast — reduces duplicate-delivery window
                    log_ids = [c["log_id"] for c in changes]
                    await loop.run_in_executor(None, self._repo.mark_processed, log_ids)

            except Exception as exc:
                print(f"⚠️  Poller error: {exc}")

    # ------------------------------------------------------------------
    # Internal broadcast helper
    # ------------------------------------------------------------------

    async def _broadcast(self, changes: list[dict]) -> None:
        """
        Push each change payload into every client's asyncio.Queue.
        Dead queues (clients that errored) are collected and removed.
        """
        async with self._lock:
            dead: list[asyncio.Queue] = []

            for change in changes:
                payload = json.dumps(change)
                for q in self._clients:
                    try:
                        await q.put(payload)
                    except Exception:
                        # Queue is broken — schedule for removal
                        dead.append(q)

            # Clean up dead clients in the same lock pass
            for q in dead:
                self._clients.remove(q)
