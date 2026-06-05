"""
db/init_db.py — One-time DB setup on app startup.
Creates tables, trigger, and seeds sample data if empty.
"""

from database import get_db_connection
from logger import get_logger

logger = get_logger(__name__)


def init_database():
    """Create orders table, change_log table, trigger, and seed data."""
    logger.info("Initialising database...")
    conn   = get_db_connection()
    cursor = conn.cursor()

    # ── orders table ─────────────────────────────────────────────────────────
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
    logger.info("Table 'orders' ready.")

    # ── change_log table ──────────────────────────────────────────────────────
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sysobjects WHERE name='change_log' AND xtype='U'
        )
        CREATE TABLE change_log (
            log_id        INT IDENTITY(1,1) PRIMARY KEY,
            operation     NVARCHAR(10)  NOT NULL,
            order_id      INT,
            customer_name NVARCHAR(255),
            product_name  NVARCHAR(255),
            status        NVARCHAR(50),
            changed_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
            is_processed  BIT           NOT NULL DEFAULT 0
        )
    """)
    logger.info("Table 'change_log' ready.")

    # ── T-SQL trigger ─────────────────────────────────────────────────────────
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
            IF EXISTS (SELECT 1 FROM inserted)
            BEGIN
                INSERT INTO change_log
                    (operation, order_id, customer_name, product_name, status)
                SELECT
                    CASE
                        WHEN EXISTS (SELECT 1 FROM deleted) THEN 'UPDATE'
                        ELSE 'INSERT'
                    END,
                    i.id, i.customer_name, i.product_name, i.status
                FROM inserted i;
            END
            IF NOT EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
            BEGIN
                INSERT INTO change_log
                    (operation, order_id, customer_name, product_name, status)
                SELECT 'DELETE', d.id, d.customer_name, d.product_name, d.status
                FROM deleted d;
            END
        END
    """)
    logger.info("Trigger 'trg_orders_change' created.")

    # ── seed data ─────────────────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            ("Alice Johnson", "Laptop Pro 15",       "pending"),
            ("Bob Smith",     "Wireless Headset",    "shipped"),
            ("Carol White",   "Mechanical Keyboard", "delivered"),
            ("David Brown",   "USB-C Hub",           "pending"),
            ("Eva Martinez",  "Monitor 4K",          "shipped"),
        ]
        cursor.executemany(
            "INSERT INTO orders (customer_name, product_name, status) VALUES (?, ?, ?)",
            seed_data,
        )
        logger.info("Seeded %d sample orders.", len(seed_data))
    else:
        logger.info("Orders table already has data — skipping seed.")

    conn.commit()
    conn.close()
    logger.info("Database initialised successfully.")
