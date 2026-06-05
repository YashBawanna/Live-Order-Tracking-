"""
Change Log Repository
---------------------
Encapsulates all reads and writes against the change_log table.

WHY separate from OrderRepository:
  - Single Responsibility: change_log is the CDC bridge between the DB trigger
    and the SSE poller. It has nothing to do with order CRUD.
  - The poller depends on this abstraction, not on raw SQL.
"""

from abc import ABC, abstractmethod
from database import get_db_connection


class AbstractChangeLogRepository(ABC):
    """Contract for reading and acknowledging change log entries."""

    @abstractmethod
    def fetch_unprocessed(self) -> list[dict]:
        """Return all rows where is_processed = 0, ordered by log_id."""
        ...

    @abstractmethod
    def mark_processed(self, log_ids: list[int]) -> None:
        """Flip is_processed = 1 for the given log_ids."""
        ...


class SqlServerChangeLogRepository(AbstractChangeLogRepository):
    """
    Concrete change_log repository for SQL Server.

    fetch_unprocessed + mark_processed are kept as two explicit steps
    (rather than one atomic SELECT + UPDATE) so the poller can broadcast
    first and acknowledge second — reducing the window for duplicate delivery.
    """

    def fetch_unprocessed(self) -> list[dict]:
        """
        Fetch every unprocessed change log row.
        Timestamps are returned in ISO-8601 format (style 126) for easy JSON serialisation.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT log_id, operation, order_id, customer_name,
                       product_name, status,
                       CONVERT(VARCHAR, changed_at, 126) AS changed_at
                FROM change_log
                WHERE is_processed = 0
                ORDER BY log_id
            """)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def mark_processed(self, log_ids: list[int]) -> None:
        """
        Bulk-update: mark all given log_ids as processed in one round-trip.
        Uses parameterised placeholders to avoid SQL injection.
        """
        if not log_ids:
            return
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(log_ids))
            cursor.execute(
                f"UPDATE change_log SET is_processed = 1 WHERE log_id IN ({placeholders})",
                log_ids
            )
            conn.commit()
        finally:
            conn.close()
