"""
Database Connection Factory
-----------------------------
Responsible for one thing: producing a live pyodbc connection.
(Single Responsibility Principle)

WHY not use a global connection:
  pyodbc connections are NOT thread-safe. Each thread / executor call
  must get its own connection and close it when done.

Future upgrade path:
  Replace get_db_connection() with an aioodbc pool for async-native access
  without changing any repository code.
"""

import pyodbc
from config import DB_CONFIG


def get_connection_string() -> str:
    """
    Build the ODBC connection string.

    Uses SQL Server auth (UID/PWD) when DB_PASSWORD is set in the environment.
    Falls back to Windows Integrated Authentication otherwise.
    """
    cfg = DB_CONFIG

    if cfg.get("password"):
        # SQL Server / Azure SQL auth — preferred for containerised deployments
        return (
            f"DRIVER={{{cfg['driver']}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['username']};"
            f"PWD={cfg['password']};"
            "TrustServerCertificate=yes;"
        )

    # Windows Integrated Authentication — only works on domain-joined Windows hosts
    return (
        f"DRIVER={{{cfg['driver']}}};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


def get_db_connection() -> pyodbc.Connection:
    """
    Open and return a new synchronous pyodbc connection.

    Callers are responsible for closing the connection (use try/finally).
    Do NOT store the returned connection as a long-lived global.
    """
    return pyodbc.connect(get_connection_string())
