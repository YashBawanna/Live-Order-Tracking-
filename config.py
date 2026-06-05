"""
Application Configuration
--------------------------
Single source of truth for all environment-driven settings.

WHY centralise config:
  - Any change to an env var name is made here, nowhere else.
  - Modules import named constants — they never call os.getenv() directly.
  - Makes it trivial to swap config sources (e.g. AWS SSM) in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "server":   os.getenv("DB_SERVER", "localhost"),
    "database": os.getenv("DB_NAME", "OrdersDB"),
    "username": os.getenv("DB_USER", "sa"),
    "password": os.getenv("DB_PASSWORD"),           # No hardcoded fallback — must be set in .env
    "driver":   os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Comma-separated origins in .env e.g. "http://localhost:3000,https://myapp.com"
# Defaults to "*" for local dev only — NEVER use "*" in production.
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

# ---------------------------------------------------------------------------
# Poller / SSE tuning
# ---------------------------------------------------------------------------

# How often (seconds) the background poller queries change_log
POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "1"))

# Seconds between SSE keepalive pings (prevents proxy from closing idle connections)
SSE_KEEPALIVE_TIMEOUT: float = float(os.getenv("SSE_KEEPALIVE_TIMEOUT", "15"))
