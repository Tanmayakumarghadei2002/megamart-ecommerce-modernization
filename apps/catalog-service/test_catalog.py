import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app, PRODUCTS_DB, load_products

load_products()
client = TestClient(app)

def test_health_and_ready_probes():
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"
    
    resp_ready = client.get("/readyz")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"

def test_list_products():
    resp = client.get("/api/catalog/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 10
    assert len(data["products"]) >= 10

def test_get_product_by_id():
    resp = client.get("/api/catalog/products/prod-101")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "prod-101"
    assert data["name"] == "MegaMart Ultra HD Smart TV 55-inch"
    assert data["category"] == "Electronics"

def test_get_product_not_found():
    resp = client.get("/api/catalog/products/non-existent-999")
    assert resp.status_code == 404

def test_search_products():
    resp = client.get("/api/catalog/search?q=wireless")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matches_count"] >= 2
    for item in data["results"]:
        matches = "wireless" in item["name"].lower() or "wireless" in item["description"].lower() or any("wireless" in t.lower() for t in item["tags"])
        assert matches

def test_check_inventory_available():
    payload = {
        "items": [
            {"product_id": "prod-101", "quantity": 2},
            {"product_id": "prod-102", "quantity": 1}
        ]
    }
    resp = client.post("/api/catalog/inventory/check", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_available"] is True
    assert len(data["results"]) == 2

def test_check_inventory_insufficient():
    payload = {
        "items": [
            {"product_id": "prod-101", "quantity": 99999}
        ]
    }
    resp = client.post("/api/catalog/inventory/check", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_available"] is False
    assert data["results"][0]["available"] is False

def test_prometheus_metrics():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "catalog_requests_total" in resp.text
