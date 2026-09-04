#!/usr/bin/env python3
"""
MegaMart Flash-Sale Autonomous Load Generator
Runs concurrent shopping traffic without needing external compiled libraries (gevent/gcc).
Uses standard Python library (concurrent.futures, urllib.request).
"""
import sys
import time
import json
import random
import uuid
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

ALB_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
ALB_URL = ALB_URL.rstrip("/")
DURATION_SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
CONCURRENCY = int(sys.argv[3]) if len(sys.argv) > 3 else 30

PRODUCT_IDS = [f"prod-10{i}" for i in range(1, 10)]
SEARCH_TERMS = ["tv", "wireless", "mouse", "jacket", "headphones", "electronics"]

stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "latencies": [],
    "orders": 0
}

def make_request(url, data=None):
    t0 = time.time()
    try:
        if data:
            req_data = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")
        else:
            req = urllib.request.Request(url, method="GET")
            
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            resp.read()
            lat = (time.time() - t0) * 1000
            return status, lat
    except urllib.error.HTTPError as e:
        lat = (time.time() - t0) * 1000
        return e.code, lat
    except Exception as e:
        lat = (time.time() - t0) * 1000
        return 0, lat

def shopper_worker(worker_id, stop_time):
    user_id = f"shopper-{worker_id}-{uuid.uuid4().hex[:6]}"
    
    while time.time() < stop_time:
        roll = random.random()
        if roll < 0.45:
            # 45% Browse Catalog
            url = f"{ALB_URL}/api/catalog/products?limit=10"
            status, lat = make_request(url)
        elif roll < 0.70:
            # 25% Search Products
            term = random.choice(SEARCH_TERMS)
            url = f"{ALB_URL}/api/catalog/search?q={term}"
            status, lat = make_request(url)
        elif roll < 0.85:
            # 15% View Product Detail
            pid = random.choice(PRODUCT_IDS)
            url = f"{ALB_URL}/api/catalog/products/{pid}"
            status, lat = make_request(url)
        else:
            # 15% Place Order (Checkout)
            pid = random.choice(PRODUCT_IDS)
            payload = {
                "user_id": user_id,
                "customer_email": f"{user_id}@megamart.com",
                "items": [{
                    "product_id": pid,
                    "product_name": "MegaMart Flash Deal Item",
                    "unit_price": round(random.uniform(20.0, 300.0), 2),
                    "quantity": random.randint(1, 2)
                }],
                "shipping_address": {
                    "street": "100 Cloud Blvd",
                    "city": "Seattle",
                    "state": "WA",
                    "zip_code": "98101",
                    "country": "USA"
                },
                "payment_method": "CREDIT_CARD"
            }
            url = f"{ALB_URL}/api/orders/checkout"
            status, lat = make_request(url, data=payload)
            if 200 <= status < 300:
                stats["orders"] += 1

        stats["total"] += 1
        if 200 <= status < 300:
            stats["success"] += 1
            stats["latencies"].append(lat)
        else:
            stats["failed"] += 1
            
        time.sleep(random.uniform(0.05, 0.2))

def main():
    print("================================================================")
    print("?? MegaMart Flash-Sale Real-Time Load Generator")
    print("================================================================")
    print(f"Target URL:    {ALB_URL}")
    print(f"Concurrency:   {CONCURRENCY} concurrent shoppers")
    print(f"Duration:      {DURATION_SECONDS} seconds")
    print("----------------------------------------------------------------")
    print("Simulating browsing, searches, product views, and checkouts...")

    stop_time = time.time() + DURATION_SECONDS
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(shopper_worker, i, stop_time) for i in range(CONCURRENCY)]
        for f in futures:
            f.result()

    total_time = time.time() - start_time
    total = stats["total"]
    success = stats["success"]
    failed = stats["failed"]
    orders = stats["orders"]
    rps = total / total_time if total_time > 0 else 0
    
    lats = sorted(stats["latencies"])
    p50 = lats[int(len(lats) * 0.50)] if lats else 0
    p95 = lats[int(len(lats) * 0.95)] if lats else 0
    p99 = lats[int(len(lats) * 0.99)] if lats else 0
    avg_lat = (sum(lats) / len(lats)) if lats else 0

    print("\n================================================================")
    print("?? FLASH-SALE LOAD TEST RESULTS SUMMARY")
    print("================================================================")
    print(f"Total Requests:       {total:,}")
    print(f"Successful (2xx):     {success:,} ({(success/total*100) if total else 0:.1f}%)")
    print(f"Failed Requests:      {failed:,}")
    print(f"Orders Placed:        {orders:,} successful checkouts")
    print(f"Throughput:           {rps:.2f} Requests/Second (RPS)")
    print(f"Average Latency:      {avg_lat:.2f} ms")
    print(f"Latency P50 (Median): {p50:.2f} ms")
    print(f"Latency P95:          {p95:.2f} ms")
    print(f"Latency P99:          {p99:.2f} ms")
    print("================================================================")

if __name__ == "__main__":
    main()
