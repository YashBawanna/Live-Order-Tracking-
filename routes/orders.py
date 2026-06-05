"""
Order CRUD Routes
-----------------
FastAPI router for creating, reading, updating, and deleting orders.

Dependency Inversion in action:
  These routes depend on OrderRepository (the abstraction), NOT on
  SqlServerOrderRepository (the detail). The concrete repo is injected
  via FastAPI's dependency injection system (Depends).

  To swap databases: change the factory in dependencies.py — zero edits here.

All DB helpers are sync (pyodbc). They are wrapped in run_in_executor()
so the event loop stays unblocked during I/O.
"""

import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from models import OrderCreate, OrderStatusUpdate
from repositories.base import OrderRepository
from dependencies import get_order_repository

router = APIRouter(prefix="/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# GET /orders  — list all orders
# ---------------------------------------------------------------------------

@router.get("")
async def get_orders(repo: OrderRepository = Depends(get_order_repository)):
    """
    Return all orders sorted by newest first.

    The repo is injected by FastAPI — the route doesn't know (or care)
    whether data comes from SQL Server, Postgres, or an in-memory store.
    """
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, repo.get_all)
    return JSONResponse(content=rows)


# ---------------------------------------------------------------------------
# POST /orders  — create a new order
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_order(
    body: OrderCreate,
    repo: OrderRepository = Depends(get_order_repository),
):
    """
    Insert a new order.
    The DB trigger fires automatically → writes to change_log → SSE poller picks up.

    Body is validated by Pydantic (OrderCreate) before reaching this handler.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, repo.insert, body)
    return {"message": "Order created"}


# ---------------------------------------------------------------------------
# PATCH /orders/{order_id}  — update status
# ---------------------------------------------------------------------------

@router.patch("/{order_id}")
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    repo: OrderRepository = Depends(get_order_repository),
):
    """
    Change the status of an existing order.
    Accepted values are enforced by the OrderStatusUpdate Pydantic model.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, repo.update_status, order_id, body.status)
    return {"message": "Order updated"}


# ---------------------------------------------------------------------------
# DELETE /orders/{order_id}  — remove an order
# ---------------------------------------------------------------------------

@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    repo: OrderRepository = Depends(get_order_repository),
):
    """
    Hard-delete an order row.
    The DB trigger writes the deleted snapshot to change_log before removal.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, repo.delete, order_id)
    return {"message": "Order deleted"}
