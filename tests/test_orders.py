"""
tests/test_orders.py — Unit + integration tests for all order CRUD endpoints.

Run with:
    pip install pytest httpx
    pytest tests/ -v

Tests use FastAPI's TestClient which runs the app in-process
without needing a real running server.

NOTE: These tests hit the REAL database.
      A test order is created, updated, and deleted in each test run.
      The DB is left clean after each test.
"""

import pytest
from fastapi.testclient import TestClient

# We need to add parent dir to path so imports work
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def create_test_order(customer="Test Customer", product="Test Product", status="pending"):
    """Helper to create an order and return the response."""
    return client.post("/orders/", json={
        "customer_name": customer,
        "product_name":  product,
        "status":        status,
    })


def get_latest_order_id() -> int:
    """Fetch all orders and return the ID of the most recent one."""
    res  = client.get("/orders/")
    data = res.json()
    assert len(data) > 0, "No orders found in DB"
    return data[0]["id"]   # orders are returned newest first


# ---------------------------------------------------------------------------
# GET /orders
# ---------------------------------------------------------------------------
class TestGetOrders:

    def test_get_orders_returns_200(self):
        """GET /orders should always return 200."""
        res = client.get("/orders/")
        assert res.status_code == 200

    def test_get_orders_returns_list(self):
        """Response should be a JSON list."""
        res  = client.get("/orders/")
        data = res.json()
        assert isinstance(data, list)

    def test_get_orders_fields_present(self):
        """Each order row should have the expected fields."""
        res  = client.get("/orders/")
        data = res.json()
        if data:
            order = data[0]
            assert "id"            in order
            assert "customer_name" in order
            assert "product_name"  in order
            assert "status"        in order
            assert "updated_at"    in order


# ---------------------------------------------------------------------------
# POST /orders
# ---------------------------------------------------------------------------
class TestCreateOrder:

    def test_create_order_returns_201(self):
        """Valid order creation should return 201."""
        res = create_test_order()
        assert res.status_code == 201

    def test_create_order_success_message(self):
        """Response should contain a success message."""
        res  = create_test_order()
        data = res.json()
        assert "message" in data
        assert "created" in data["message"].lower()

    def test_create_order_appears_in_list(self):
        """After creation, order should appear in GET /orders."""
        create_test_order(customer="Unique_Customer_XYZ", product="Unique_Product_XYZ")
        res  = client.get("/orders/")
        data = res.json()
        names = [o["customer_name"] for o in data]
        assert "Unique_Customer_XYZ" in names

    def test_create_order_default_status_is_pending(self):
        """Order created without explicit status should default to 'pending'."""
        res = client.post("/orders/", json={
            "customer_name": "Default Status Test",
            "product_name":  "Some Product",
        })
        assert res.status_code == 201
        res2 = client.get("/orders/")
        order = next(
            (o for o in res2.json() if o["customer_name"] == "Default Status Test"),
            None
        )
        assert order is not None
        assert order["status"] == "pending"

    def test_create_order_invalid_status_rejected(self):
        """Order with invalid status should be rejected (422)."""
        res = client.post("/orders/", json={
            "customer_name": "Bad Status",
            "product_name":  "Product",
            "status":        "flying",        # invalid
        })
        assert res.status_code == 422

    def test_create_order_missing_fields_rejected(self):
        """Order missing required fields should return 422."""
        res = client.post("/orders/", json={"customer_name": "No Product"})
        assert res.status_code == 422

    @pytest.mark.parametrize("status", ["pending", "shipped", "delivered", "cancelled"])
    def test_create_order_all_valid_statuses(self, status):
        """All valid statuses should be accepted."""
        res = create_test_order(
            customer=f"Status Test {status}",
            product="Test Product",
            status=status,
        )
        assert res.status_code == 201


# ---------------------------------------------------------------------------
# PATCH /orders/{id}
# ---------------------------------------------------------------------------
class TestUpdateOrder:

    def setup_method(self):
        """Create a fresh order before each update test."""
        create_test_order(customer="Update Test Customer", product="Update Test Product")
        self.order_id = get_latest_order_id()

    def test_update_status_returns_200(self):
        """PATCH with valid status should return 200."""
        res = client.patch(f"/orders/{self.order_id}", json={"status": "shipped"})
        assert res.status_code == 200

    def test_update_status_success_message(self):
        """Response should confirm the update."""
        res  = client.patch(f"/orders/{self.order_id}", json={"status": "delivered"})
        data = res.json()
        assert "message" in data
        assert "updated" in data["message"].lower()

    def test_update_status_reflected_in_get(self):
        """After update, GET /orders should show new status."""
        client.patch(f"/orders/{self.order_id}", json={"status": "shipped"})
        res   = client.get("/orders/")
        order = next((o for o in res.json() if o["id"] == self.order_id), None)
        assert order is not None
        assert order["status"] == "shipped"

    def test_update_nonexistent_order_returns_404(self):
        """PATCH on non-existent order ID should return 404."""
        res = client.patch("/orders/999999", json={"status": "shipped"})
        assert res.status_code == 404

    def test_update_invalid_status_rejected(self):
        """Invalid status value should return 422."""
        res = client.patch(f"/orders/{self.order_id}", json={"status": "lost"})
        assert res.status_code == 422

    @pytest.mark.parametrize("status", ["pending", "shipped", "delivered", "cancelled"])
    def test_update_all_valid_statuses(self, status):
        """All valid statuses should be accepted on update."""
        res = client.patch(f"/orders/{self.order_id}", json={"status": status})
        assert res.status_code == 200

    def teardown_method(self):
        """Clean up test order after each test."""
        client.delete(f"/orders/{self.order_id}")


# ---------------------------------------------------------------------------
# DELETE /orders/{id}
# ---------------------------------------------------------------------------
class TestDeleteOrder:

    def setup_method(self):
        """Create a fresh order before each delete test."""
        create_test_order(customer="Delete Test Customer", product="Delete Test Product")
        self.order_id = get_latest_order_id()

    def test_delete_order_returns_200(self):
        """DELETE on existing order should return 200."""
        res = client.delete(f"/orders/{self.order_id}")
        assert res.status_code == 200

    def test_delete_order_success_message(self):
        """Response should confirm the deletion."""
        res  = client.delete(f"/orders/{self.order_id}")
        data = res.json()
        assert "message" in data
        assert "deleted" in data["message"].lower()

    def test_delete_order_no_longer_in_list(self):
        """After deletion, order should not appear in GET /orders."""
        client.delete(f"/orders/{self.order_id}")
        res = client.get("/orders/")
        ids = [o["id"] for o in res.json()]
        assert self.order_id not in ids

    def test_delete_nonexistent_order_returns_404(self):
        """DELETE on non-existent ID should return 404."""
        client.delete(f"/orders/{self.order_id}")   # delete it first
        res = client.delete(f"/orders/{self.order_id}")  # try again
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Full flow test
# ---------------------------------------------------------------------------
class TestFullOrderLifecycle:

    def test_create_update_delete_flow(self):
        """
        End-to-end test:
        Create → verify → update → verify → delete → verify gone
        """
        # 1. Create
        res = create_test_order(customer="Lifecycle Test", product="Lifecycle Product")
        assert res.status_code == 201

        # 2. Verify created
        order_id = get_latest_order_id()
        res  = client.get("/orders/")
        order = next((o for o in res.json() if o["id"] == order_id), None)
        assert order is not None
        assert order["customer_name"] == "Lifecycle Test"
        assert order["status"] == "pending"

        # 3. Update to shipped
        res = client.patch(f"/orders/{order_id}", json={"status": "shipped"})
        assert res.status_code == 200

        # 4. Verify updated
        res   = client.get("/orders/")
        order = next((o for o in res.json() if o["id"] == order_id), None)
        assert order["status"] == "shipped"

        # 5. Update to delivered
        res = client.patch(f"/orders/{order_id}", json={"status": "delivered"})
        assert res.status_code == 200

        # 6. Delete
        res = client.delete(f"/orders/{order_id}")
        assert res.status_code == 200

        # 7. Verify deleted
        res = client.get("/orders/")
        ids = [o["id"] for o in res.json()]
        assert order_id not in ids
