import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app, IN_MEMORY_ORDERS, init_aws_clients

init_aws_clients()
client = TestClient(app)

def test_order_probes():
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"
    
    resp_ready = client.get("/readyz")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"

def test_checkout_successful():
    payload = {
        "user_id": "usr-flash-8899",
        "customer_email": "shopper@megamart.com",
        "items": [
            {
                "product_id": "prod-101",
                "product_name": "MegaMart Ultra HD Smart TV 55-inch",
                "unit_price": 499.99,
                "quantity": 1
            },
            {
                "product_id": "prod-103",
                "product_name": "AeroGrip Wireless Mouse",
                "unit_price": 39.99,
                "quantity": 2
            }
        ],
        "shipping_address": {
            "street": "123 E-Commerce Way",
            "city": "Seattle",
            "state": "WA",
            "zip_code": "98101",
            "country": "USA"
        },
        "payment_method": "CREDIT_CARD"
    }
    resp = client.post("/api/orders/checkout", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "CONFIRMED"
    assert data["total_amount"] == 579.97
    assert data["item_count"] == 3
    assert data["order_id"].startswith("ord-")
    assert data["receipt_url"] is not None

    order_id = data["order_id"]
    resp_get = client.get(f"/api/orders/{order_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["order_id"] == order_id

def test_get_nonexistent_order():
    resp = client.get("/api/orders/ord-nonexistent-12345")
    assert resp.status_code == 404

def test_list_user_orders():
    resp = client.get("/api/orders/user/usr-flash-8899")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "usr-flash-8899"
    assert data["count"] >= 1

def test_order_metrics():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "orders_placed_total" in resp.text
