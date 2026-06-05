"""
Dependency Injection Container
--------------------------------
Central place where concrete implementations are wired to abstractions.

WHY this file exists:
  - Open/Closed Principle: to swap SQL Server for Postgres, edit ONLY this file.
  - All routes import from here — they never instantiate repositories directly.
  - The poller singleton is created once and shared across all requests.

FastAPI's Depends() system calls these factory functions per-request (for repos)
or returns the shared singleton (for the poller).
"""

from repositories.sqlserver import SqlServerOrderRepository
from repositories.change_log import SqlServerChangeLogRepository
from repositories.base import OrderRepository
from services.poller import ChangeLogPoller

# ---------------------------------------------------------------------------
# Singleton poller instance
# Shared across all requests — owns the connected client list.
# Created once at module import time; started in main.py lifespan.
# ---------------------------------------------------------------------------
_change_log_repo = SqlServerChangeLogRepository()
_poller = ChangeLogPoller(repository=_change_log_repo)


def get_poller() -> ChangeLogPoller:
    """
    Return the shared ChangeLogPoller singleton.
    Injected into SSE routes via FastAPI Depends().
    """
    return _poller


def get_order_repository() -> OrderRepository:
    """
    Factory for the order repository.

    Returns a fresh SqlServerOrderRepository per request.
    To switch to Postgres: return PostgresOrderRepository() here.
    Routes never know which concrete class they're getting.
    """
    return SqlServerOrderRepository()
