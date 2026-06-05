"""
routes/orders.py — CRUD endpoints for the orders table.
Each operation triggers trg_orders_change automatically.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from database import get_db_connection
from models import OrderCreate, OrderStatusUpdate
from logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/")
def get_orders():
    """Return all orders, most recent first."""
    logger.info("GET /orders — fetching all orders")
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, customer_name, product_name, status,
               CONVERT(VARCHAR, updated_at, 126) AS updated_at
        FROM orders
        ORDER BY id DESC
    """)
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()
    logger.info("Returned %d orders.", len(rows))
    return JSONResponse(content=rows)


@router.post("/", status_code=201)
def create_order(body: OrderCreate):
    """INSERT a new order — fires the DB trigger → change_log → SSE."""
    logger.info(
        "POST /orders — Creating order: customer=%s product=%s status=%s",
        body.customer_name, body.product_name, body.status,
    )
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (customer_name, product_name, status) VALUES (?, ?, ?)",
            body.customer_name, body.product_name, body.status,
        )
        conn.commit()
        conn.close()
        logger.info("Order created successfully for customer: %s", body.customer_name)
        return {"message": "Order created successfully"}
    except Exception as e:
        logger.error("Failed to create order: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create order")


@router.patch("/{order_id}")
def update_order_status(order_id: int, body: OrderStatusUpdate):
    """UPDATE order status — fires the DB trigger."""
    logger.info("PATCH /orders/%d — Updating status to '%s'", order_id, body.status)
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = ?, updated_at = GETDATE() WHERE id = ?",
            body.status, order_id,
        )
        if cursor.rowcount == 0:
            conn.close()
            logger.warning("Order #%d not found for update.", order_id)
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        conn.commit()
        conn.close()
        logger.info("Order #%d updated to '%s'.", order_id, body.status)
        return {"message": f"Order {order_id} updated to '{body.status}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update order #%d: %s", order_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update order")


@router.delete("/{order_id}")
def delete_order(order_id: int):
    """DELETE an order — fires the DB trigger."""
    logger.info("DELETE /orders/%d", order_id)
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id = ?", order_id)
        if cursor.rowcount == 0:
            conn.close()
            logger.warning("Order #%d not found for deletion.", order_id)
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        conn.commit()
        conn.close()
        logger.info("Order #%d deleted successfully.", order_id)
        return {"message": f"Order {order_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete order #%d: %s", order_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete order")
