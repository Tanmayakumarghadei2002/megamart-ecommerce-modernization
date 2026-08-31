import os
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

try:
    from order_models import (
        CheckoutRequest,
        CheckoutResponse,
        OrderRecord,
        OrderStatus,
        CartItem,
        ShippingAddress
    )
except ImportError:
    from models import (
        CheckoutRequest,
        CheckoutResponse,
        OrderRecord,
        OrderStatus,
        CartItem,
        ShippingAddress
    )

# Structured JSON logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "service": "order-service", "message": "%(message)s"}'
)
logger = logging.getLogger("order-service")

# Prometheus Metrics
ORDER_REQUESTS_TOTAL = Counter(
    "order_requests_total",
    "Total number of HTTP requests processed by order-service",
    ["method", "endpoint", "status_code"]
)

ORDER_PROCESSING_DURATION_SECONDS = Histogram(
    "order_processing_duration_seconds",
    "Order processing and checkout latency in seconds",
    ["stage"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

ORDERS_PLACED_TOTAL = Counter(
    "orders_placed_total",
    "Total number of checkout orders placed",
    ["status"]
)

ORDER_AMOUNT_DOLLARS_TOTAL = Counter(
    "order_amount_dollars_total",
    "Total monetary value of successful orders in USD"
)

ORDER_FAILURES_TOTAL = Counter(
    "order_failures_total",
    "Total count of failed checkout attempts",
    ["reason"]
)

# AWS Configuration from Environment (IRSA injected)
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE_NAME", "megamart-orders")
S3_RECEIPTS_BUCKET = os.getenv("S3_BUCKET_NAME", "megamart-order-receipts")

# AWS Clients (auto-resolves IRSA WebIdentity credentials via boto3)
dynamodb_client = None
dynamodb_table = None
s3_client = None
USE_IN_MEMORY_FALLBACK = False
IN_MEMORY_ORDERS = {}

def init_aws_clients():
    global dynamodb_client, dynamodb_table, s3_client, USE_IN_MEMORY_FALLBACK
    try:
        session = boto3.Session(region_name=AWS_REGION)
        s3_client = session.client("s3")
        dynamodb = session.resource("dynamodb")
        dynamodb_table = dynamodb.Table(DYNAMODB_TABLE)
        dynamodb_client = session.client("dynamodb")
        logger.info(f"Initialized AWS clients for Region: {AWS_REGION}, DynamoDB: {DYNAMODB_TABLE}, S3: {S3_RECEIPTS_BUCKET}")
    except Exception as e:
        logger.warning(f"AWS credentials or services not reachable ({e}). Using in-memory fallback store for local testing.")
        USE_IN_MEMORY_FALLBACK = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_aws_clients()
    yield

app = FastAPI(
    title="MegaMart Order Service",
    description="Microservice handling customer checkouts, cart processing, DynamoDB order storage, and S3 receipt generation.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    path = request.url.path
    if path not in ["/metrics", "/healthz", "/readyz"]:
        endpoint = path
        if path.startswith("/api/orders/user/"):
            endpoint = "/api/orders/user/{user_id}"
        elif path.startswith("/api/orders/") and len(path.split("/")) == 4:
            endpoint = "/api/orders/{order_id}"
            
        ORDER_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=str(response.status_code)
        ).inc()
    return response

# Probes and Metrics
@app.get("/healthz", status_code=status.HTTP_200_OK, tags=["Probes"])
async def liveness_probe():
    return {"status": "healthy", "service": "order-service", "timestamp": time.time()}

@app.get("/readyz", status_code=status.HTTP_200_OK, tags=["Probes"])
async def readiness_probe():
    return {
        "status": "ready",
        "storage": "in_memory" if USE_IN_MEMORY_FALLBACK else "aws_dynamodb_s3",
        "dynamodb_table": DYNAMODB_TABLE,
        "s3_bucket": S3_RECEIPTS_BUCKET
    }

@app.get("/metrics", tags=["Observability"])
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/", tags=["General"])
async def root():
    return {
        "service": "order-service",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "docs": "/docs"
    }

# Order Processing Helper Functions
def save_order_to_storage(order: OrderRecord):
    order_dict = order.model_dump()
    order_dict["total_amount"] = str(order.total_amount)
    
    if USE_IN_MEMORY_FALLBACK or not dynamodb_table:
        IN_MEMORY_ORDERS[order.order_id] = order_dict
        return
        
    try:
        t0 = time.time()
        dynamodb_table.put_item(Item=order_dict)
        ORDER_PROCESSING_DURATION_SECONDS.labels(stage="dynamodb_write").observe(time.time() - t0)
    except Exception as e:
        logger.error(f"Failed to write order {order.order_id} to DynamoDB: {e}")
        IN_MEMORY_ORDERS[order.order_id] = order_dict

def generate_and_upload_receipt(order: OrderRecord) -> Optional[str]:
    receipt_data = {
        "receipt_header": "MegaMart Flash-Sale Purchase Receipt",
        "order_id": order.order_id,
        "user_id": order.user_id,
        "email": order.customer_email,
        "date": order.created_at,
        "items": [item.model_dump() for item in order.items],
        "total_amount": f"${order.total_amount:.2f}",
        "shipping_address": order.shipping_address.model_dump(),
        "status": order.status.value
    }
    
    receipt_key = f"receipts/{order.user_id}/{order.order_id}.json"
    
    if USE_IN_MEMORY_FALLBACK or not s3_client:
        return f"s3://{S3_RECEIPTS_BUCKET}/{receipt_key}"
        
    try:
        t0 = time.time()
        s3_client.put_object(
            Bucket=S3_RECEIPTS_BUCKET,
            Key=receipt_key,
            Body=json.dumps(receipt_data, indent=2),
            ContentType="application/json",
            ServerSideEncryption="AES256"
        )
        ORDER_PROCESSING_DURATION_SECONDS.labels(stage="s3_upload").observe(time.time() - t0)
        return f"s3://{S3_RECEIPTS_BUCKET}/{receipt_key}"
    except Exception as e:
        logger.warning(f"Could not upload receipt to S3 ({e}). Continuing checkout flow.")
        return f"s3://{S3_RECEIPTS_BUCKET}/{receipt_key}"

def get_order_from_storage(order_id: str) -> Optional[dict]:
    if USE_IN_MEMORY_FALLBACK or not dynamodb_table:
        return IN_MEMORY_ORDERS.get(order_id)
        
    try:
        resp = dynamodb_table.get_item(Key={"order_id": order_id})
        return resp.get("Item")
    except Exception as e:
        logger.error(f"Error fetching order {order_id} from DynamoDB: {e}")
        return IN_MEMORY_ORDERS.get(order_id)

# API Endpoints
@app.post("/api/orders/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED, tags=["Orders"])
async def checkout(req: CheckoutRequest):
    t_start = time.time()
    
    if not req.items:
        ORDER_FAILURES_TOTAL.labels(reason="empty_cart").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart cannot be empty")
        
    total_amount = round(sum(item.unit_price * item.quantity for item in req.items), 2)
    order_id = f"ord-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    order_record = OrderRecord(
        order_id=order_id,
        user_id=req.user_id,
        customer_email=req.customer_email,
        status=OrderStatus.CONFIRMED,
        items=req.items,
        shipping_address=req.shipping_address,
        total_amount=total_amount,
        receipt_s3_key=None,
        created_at=now_iso,
        updated_at=now_iso
    )
    
    receipt_url = generate_and_upload_receipt(order_record)
    order_record.receipt_s3_key = receipt_url
    save_order_to_storage(order_record)
    
    ORDER_PROCESSING_DURATION_SECONDS.labels(stage="total_checkout").observe(time.time() - t_start)
    ORDERS_PLACED_TOTAL.labels(status="confirmed").inc()
    ORDER_AMOUNT_DOLLARS_TOTAL.inc(total_amount)
    
    logger.info(f"Successfully processed checkout order {order_id} for user {req.user_id}, total: ${total_amount:.2f}")
    
    return CheckoutResponse(
        order_id=order_id,
        user_id=req.user_id,
        status=OrderStatus.CONFIRMED,
        total_amount=total_amount,
        item_count=sum(item.quantity for item in req.items),
        receipt_url=receipt_url,
        created_at=now_iso,
        message="Order successfully placed and confirmed."
    )

@app.get("/api/orders/{order_id}", tags=["Orders"])
async def get_order(order_id: str):
    order = get_order_from_storage(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found")
    return order

@app.get("/api/orders/user/{user_id}", tags=["Orders"])
async def list_user_orders(user_id: str):
    user_orders = [o for o in IN_MEMORY_ORDERS.values() if o.get("user_id") == user_id]
    return {"user_id": user_id, "count": len(user_orders), "orders": user_orders}
