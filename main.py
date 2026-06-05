"""
Real-Time Order Notification System
-------------------------------------
Entry point — intentionally thin.

Responsibilities of main.py:
  1. Create the FastAPI app instance
  2. Register middleware
  3. Mount routers
  4. Manage application lifespan (DB init + background poller)

Nothing else belongs here. Business logic, DB access, and SSE mechanics
each live in their own modules.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from db.init_db import init_database
from dependencies import get_poller
from routes.orders import router as orders_router
from routes.stream import router as stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
      - Initialise the DB schema, trigger, and seed data (idempotent).
      - Start the ChangeLogPoller as a background asyncio task.

    Shutdown:
      - Cancel the poller task cleanly when the server stops.
    """
    # --- startup ---
    init_database()
    poller = get_poller()
    task = asyncio.create_task(poller.run())

    yield  # App runs here

    # --- shutdown ---
    task.cancel()


app = FastAPI(
    title="Real-Time Orders API",
    description="FastAPI + SQL Server + SSE — demonstrating OOP, SOLID, and clean architecture.",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,   # Configured via .env, not hardcoded
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(orders_router)   # /orders  (CRUD)
app.include_router(stream_router)   # /stream, /clients (SSE)
