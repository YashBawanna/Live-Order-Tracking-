"""
SQL Server Order Repository (Concrete Implementation)
-----------------------------------------------------
Implements the OrderRepository interface using pyodbc + SQL Server.

WHY a separate class:
  - Single Responsibility: this class ONLY knows how to talk to SQL Server.
  - Open/Closed: to support Postgres, create PostgresOrderRepository without
    touching this file or any route.
  - Liskov Substitution: anywhere an OrderRepository is expected, this class
    can be dropped in without breaking anything.

All DB calls are synchronous (pyodbc limitation). Callers must wrap them in
asyncio.run_in_executor() to avoid blocking the event loop.
"""

from database import get_db_connection
from models import OrderCreate
from repositories.base import OrderRepository


class SqlServerOrderRepository(OrderRepository):
    """
    Concrete repository backed by SQL Server via pyodbc.

    Each method opens its own connection and closes it on exit.
    For high-throughput use, replace with a connection pool (e.g. aioodbc).
    """

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        """
        Fetch every order sorted by newest first.
        Returns a list of plain dicts so the layer above stays DB-agnostic.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, customer_name, product_name, status,
                       CONVERT(VARCHAR, updated_at, 126) AS updated_at
                FROM orders
                ORDER BY id DESC
            """)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        finally:
            conn.close()  # Always release, even on exception

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def insert(self, order: OrderCreate) -> None:
        """
        Persist a new order row.
        The DB trigger fires automatically after this INSERT,
        writing a record into change_log for the SSE poller to pick up.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (customer_name, product_name, status) VALUES (?, ?, ?)",
                order.customer_name, order.product_name, order.status
            )
            conn.commit()
        finally:
            conn.close()

    def update_status(self, order_id: int, status: str) -> None:
        """
        Update the status column of an existing order.
        Also refreshes updated_at so the timestamp stays accurate.
        The DB trigger fires after this UPDATE.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = ?, updated_at = GETDATE() WHERE id = ?",
                status, order_id
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, order_id: int) -> None:
        """
        Hard-delete an order row.
        The DB trigger captures the deleted row into change_log before removal.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE id = ?", order_id)
            conn.commit()
        finally:
            conn.close()
