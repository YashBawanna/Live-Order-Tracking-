"""
Database Initialisation
------------------------
Creates tables, the CDC trigger, and seeds starter data on first run.
Every statement is idempotent — safe to call on each app startup.

WHY separate from repositories:
  - Single Responsibility: this module is about schema setup, not data access.
  - Repositories assume the schema already exists; this module ensures it does.

Trigger design (trg_orders_change):
  SQL Server triggers expose two pseudo-tables:
    inserted — rows after INSERT or UPDATE
    deleted  — rows before DELETE or UPDATE
  We use both to distinguish INSERT vs UPDATE vs DELETE in a single trigger.
"""

from database import get_db_connection

SEED_DATA = [
    ("Alice Johnson", "Laptop Pro 15",       "pending"),
    ("Bob Smith",     "Wireless Headset",    "shipped"),
    ("Carol White",   "Mechanical Keyboard", "delivered"),
    ("David Brown",   "USB-C Hub",           "pending"),
    ("Eva Martinez",  "Monitor 4K",          "shipped"),
]


def init_database() -> None:
    """
    Entry point called once at app startup.
    Delegates each concern to a private helper for readability.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    _create_orders_table(cursor)
    _create_change_log_table(cursor)
    _create_trigger(cursor)
    _seed_if_empty(cursor)

    conn.commit()
    conn.close()
    print("✅ Database initialised successfully.")


def _create_orders_table(cursor) -> None:
    """Create the orders table if it doesn't already exist."""
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sysobjects WHERE name='orders' AND xtype='U'
        )
        CREATE TABLE orders (
            id            INT IDENTITY(1,1) PRIMARY KEY,
            customer_name NVARCHAR(255) NOT NULL,
            product_name  NVARCHAR(255) NOT NULL,
            status        NVARCHAR(50)  NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','shipped','delivered','cancelled')),
            updated_at    DATETIME2     NOT NULL DEFAULT GETDATE()
        )
    """)


def _create_change_log_table(cursor) -> None:
    """
    Create the change_log table if it doesn't already exist.

    change_log is the CDC bridge:
      DB trigger writes here → poller reads here → SSE pushes to clients.
    is_processed = 0 means "not yet sent to clients".
    """
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sysobjects WHERE name='change_log' AND xtype='U'
        )
        CREATE TABLE change_log (
            log_id        INT IDENTITY(1,1) PRIMARY KEY,
            operation     NVARCHAR(10)  NOT NULL,   -- INSERT / UPDATE / DELETE
            order_id      INT,
            customer_name NVARCHAR(255),
            product_name  NVARCHAR(255),
            status        NVARCHAR(50),
            changed_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
            is_processed  BIT           NOT NULL DEFAULT 0
        )
    """)


def _create_trigger(cursor) -> None:
    """
    Drop and recreate trg_orders_change.

    The trigger fires AFTER any INSERT, UPDATE, or DELETE on orders
    and writes a snapshot of the affected row into change_log.

    Note: DROP + CREATE on every startup is acceptable for dev/staging.
    For production with zero-downtime deployments, use ALTER TRIGGER instead.
    """
    cursor.execute("""
        IF OBJECT_ID('trg_orders_change', 'TR') IS NOT NULL
            DROP TRIGGER trg_orders_change
    """)
    cursor.execute("""
        CREATE TRIGGER trg_orders_change
        ON orders
        AFTER INSERT, UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;

            -- INSERT and UPDATE: new row data is in the 'inserted' pseudo-table
            IF EXISTS (SELECT 1 FROM inserted)
            BEGIN
                INSERT INTO change_log (operation, order_id, customer_name, product_name, status)
                SELECT
                    CASE
                        WHEN EXISTS (SELECT 1 FROM deleted) THEN 'UPDATE'
                        ELSE 'INSERT'
                    END,
                    i.id, i.customer_name, i.product_name, i.status
                FROM inserted i;
            END

            -- DELETE: deleted row data is only in 'deleted' (nothing in 'inserted')
            IF NOT EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
            BEGIN
                INSERT INTO change_log (operation, order_id, customer_name, product_name, status)
                SELECT 'DELETE', d.id, d.customer_name, d.product_name, d.status
                FROM deleted d;
            END
        END
    """)


def _seed_if_empty(cursor) -> None:
    """Insert starter rows only if the orders table is completely empty."""
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO orders (customer_name, product_name, status) VALUES (?, ?, ?)",
            SEED_DATA
        )
