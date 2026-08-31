import random
import uuid
from locust import HttpUser, task, between, tag

class FlashSaleShopper(HttpUser):
    wait_time = between(0.5, 2.0)
    
    product_ids = [
        "prod-101", "prod-102", "prod-103", "prod-104", "prod-105",
        "prod-106", "prod-107", "prod-108", "prod-109", "prod-110"
    ]
    search_keywords = ["wireless", "tv", "jacket", "espresso", "cotton", "yoga", "4k"]

    def on_start(self):
        self.user_id = f"usr-locust-{uuid.uuid4().hex[:8]}"

    @task(5)
    @tag("browse")
    def browse_catalog(self):
        self.client.get("/api/catalog/products?limit=10", name="/api/catalog/products")

    @task(3)
    @tag("search")
    def search_products(self):
        keyword = random.choice(self.search_keywords)
        self.client.get(f"/api/catalog/search?q={keyword}", name="/api/catalog/search")

    @task(4)
    @tag("details")
    def view_product_details(self):
        prod_id = random.choice(self.product_ids)
        self.client.get(f"/api/catalog/products/{prod_id}", name="/api/catalog/products/{id}")

    @task(2)
    @tag("checkout")
    def perform_checkout(self):
        prod_id = random.choice(self.product_ids)
        payload = {
            "user_id": self.user_id,
            "customer_email": f"{self.user_id}@megamart-shopper.com",
            "items": [
                {
                    "product_id": prod_id,
                    "product_name": "MegaMart Flash Deal Item",
                    "unit_price": round(random.uniform(20.0, 200.0), 2),
                    "quantity": random.randint(1, 3)
                }
            ],
            "shipping_address": {
                "street": "100 Innovation Way",
                "city": "Dallas",
                "state": "TX",
                "zip_code": "75001",
                "country": "USA"
            },
            "payment_method": "CREDIT_CARD"
        }
        self.client.post("/api/orders/checkout", json=payload, name="/api/orders/checkout")
