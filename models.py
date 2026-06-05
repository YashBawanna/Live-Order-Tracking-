"""
Pydantic Models (Data Contracts)
----------------------------------
Defines the shape and validation rules for data entering the API.

WHY Pydantic:
  - Validates request bodies automatically before they reach route handlers.
  - Replaces raw `dict` access (e.g. body["customer_name"]) that raises
    KeyError on missing fields with clear HTTP 422 responses.
  - Acts as living documentation of the API's expected input.

Encapsulation in practice:
  The Literal type on `status` centralises the allowed-values constraint here
  rather than scattering it across routes, the DB CHECK constraint, and trigger logic.
"""

from typing import Literal
from pydantic import BaseModel, Field

# Shared type alias — update in one place if statuses ever change
OrderStatus = Literal["pending", "shipped", "delivered", "cancelled"]


class OrderCreate(BaseModel):
    """Payload required to create a new order."""

    customer_name: str = Field(..., min_length=1, max_length=255, description="Full name of the customer")
    product_name: str  = Field(..., min_length=1, max_length=255, description="Name of the ordered product")
    status: OrderStatus = Field("pending", description="Initial order status")


class OrderStatusUpdate(BaseModel):
    """Payload for PATCH /orders/{id} — only status can be changed."""

    status: OrderStatus = Field(..., description="New status for the order")
