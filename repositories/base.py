"""
Abstract Repository (Dependency Inversion Principle)
----------------------------------------------------
This module defines the CONTRACT that any order data store must fulfil.

WHY:
  Routes and services depend on this abstraction, NOT on a concrete DB driver.
  Swapping SQL Server → Postgres → an in-memory store requires zero changes
  to routes or services — only a new concrete class here.

SOLID principles applied:
  - D (Dependency Inversion): high-level modules depend on abstractions
  - O (Open/Closed): extend by adding a new subclass, not by editing routes
  - I (Interface Segregation): two focused interfaces — read vs. write
"""

from abc import ABC, abstractmethod
from models import OrderCreate


class OrderReaderRepository(ABC):
    """
    Read-only contract for order data.
    Segregated from writes so read-only consumers don't carry mutation methods.
    (Interface Segregation Principle)
    """

    @abstractmethod
    def get_all(self) -> list[dict]:
        """Return every order, newest first."""
        ...


class OrderWriterRepository(ABC):
    """
    Write contract for order data.
    Kept separate from reads for the same ISP reason.
    """

    @abstractmethod
    def insert(self, order: OrderCreate) -> None:
        """Persist a new order."""
        ...

    @abstractmethod
    def update_status(self, order_id: int, status: str) -> None:
        """Change the status of an existing order."""
        ...

    @abstractmethod
    def delete(self, order_id: int) -> None:
        """Remove an order permanently."""
        ...


class OrderRepository(OrderReaderRepository, OrderWriterRepository):
    """
    Combined read+write contract.
    Concrete implementations inherit from this single class for convenience
    while still honouring the segregated interfaces above.
    """
    pass
