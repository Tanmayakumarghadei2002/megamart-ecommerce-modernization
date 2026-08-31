import os
import json
import time
import logging
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

try:
    from catalog_models import (
        Product,
        ProductListResponse,
        InventoryCheckRequest,
        InventoryCheckResponse,
        InventoryCheckItemResult,
        SearchQueryResponse
    )
except ImportError:
    from models import (
        Product,
        ProductListResponse,
        InventoryCheckRequest,
        InventoryCheckResponse,
        InventoryCheckItemResult,
        SearchQueryResponse
    )

# Configure structured JSON logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "service": "catalog-service", "message": "%(message)s"}'
)
logger = logging.getLogger("catalog-service")

# Prometheus Metrics
CATALOG_REQUESTS_TOTAL = Counter(
    "catalog_requests_total",
    "Total number of HTTP requests processed by catalog-service",
    ["method", "endpoint", "status_code"]
)

CATALOG_REQUEST_DURATION_SECONDS = Histogram(
    "catalog_request_duration_seconds",
    "HTTP request latency in seconds for catalog-service",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

CATALOG_SEARCH_QUERIES_TOTAL = Counter(
    "catalog_search_queries_total",
    "Total number of search queries executed",
    ["query_type"]
)

INVENTORY_LOOKUPS_TOTAL = Counter(
    "catalog_inventory_lookups_total",
    "Total number of inventory checks performed",
    ["result"]
)

# In-memory product cache
PRODUCTS_DB: List[Product] = []

def load_products():
    global PRODUCTS_DB
    data_file = os.path.join(os.path.dirname(__file__), "data", "products.json")
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            PRODUCTS_DB = [Product(**item) for item in raw_data]
            logger.info(f"Successfully loaded {len(PRODUCTS_DB)} products into catalog memory cache.")
    else:
        logger.warning(f"Products data file not found at {data_file}. Starting with empty catalog.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_products()
    yield

app = FastAPI(
    title="MegaMart Catalog Service",
    description="Microservice handling product discovery, search queries, and inventory lookups for MegaMart.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telemetry Middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    path = request.url.path
    if path not in ["/metrics", "/healthz", "/readyz"]:
        endpoint = path
        if path.startswith("/api/catalog/products/") and len(path.split("/")) > 4:
            endpoint = "/api/catalog/products/{id}"
        
        status_code = str(response.status_code)
        CATALOG_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        CATALOG_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)
        
    return response

# Probes and Metrics Endpoints
@app.get("/healthz", status_code=status.HTTP_200_OK, tags=["Probes"])
async def liveness_probe():
    """Kubernetes liveness probe."""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/readyz", status_code=status.HTTP_200_OK, tags=["Probes"])
async def readiness_probe():
    """Kubernetes readiness probe."""
    if len(PRODUCTS_DB) >= 0:
        return {"status": "ready", "products_loaded": len(PRODUCTS_DB)}
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Catalog not initialized")

@app.get("/metrics", tags=["Observability"])
async def prometheus_metrics():
    """Exposes Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/", tags=["General"])
async def root():
    return {
        "service": "catalog-service",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "docs": "/docs"
    }

# Catalog API Endpoints
@app.get("/api/catalog/products", response_model=ProductListResponse, tags=["Catalog"])
async def list_products(
    category: Optional[str] = Query(None, description="Filter products by category"),
    in_stock_only: bool = Query(False, description="Filter only in-stock items"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Limit results count")
):
    filtered = PRODUCTS_DB
    if category:
        filtered = [p for p in filtered if p.category.lower() == category.lower()]
    if in_stock_only:
        filtered = [p for p in filtered if p.in_stock and p.inventory > 0]
        
    total = len(filtered)
    paginated = filtered[skip: skip + limit]
    return ProductListResponse(total=total, products=paginated)

@app.get("/api/catalog/products/{product_id}", response_model=Product, tags=["Catalog"])
async def get_product(product_id: str):
    for p in PRODUCTS_DB:
        if p.id == product_id:
            return p
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found")

@app.get("/api/catalog/search", response_model=SearchQueryResponse, tags=["Catalog"])
async def search_products(
    q: str = Query(..., min_length=1, description="Search keyword in title, description, or tags")
):
    term = q.lower().strip()
    CATALOG_SEARCH_QUERIES_TOTAL.labels(query_type="text").inc()
    
    matches = [
        p for p in PRODUCTS_DB
        if term in p.name.lower() or term in p.description.lower() or any(term in tag.lower() for tag in p.tags)
    ]
    return SearchQueryResponse(query=q, matches_count=len(matches), results=matches)

@app.get("/api/catalog/categories", response_model=List[str], tags=["Catalog"])
async def get_categories():
    categories = sorted(list(set(p.category for p in PRODUCTS_DB)))
    return categories

@app.post("/api/catalog/inventory/check", response_model=InventoryCheckResponse, tags=["Inventory"])
async def check_inventory(req: InventoryCheckRequest):
    """Bulk inventory verification called during checkout."""
    results = []
    all_available = True
    
    prod_map = {p.id: p for p in PRODUCTS_DB}
    
    for item in req.items:
        product = prod_map.get(item.product_id)
        if not product:
            results.append(InventoryCheckItemResult(
                product_id=item.product_id,
                available=False,
                requested=item.quantity,
                current_stock=0
            ))
            all_available = False
            INVENTORY_LOOKUPS_TOTAL.labels(result="not_found").inc()
        elif product.inventory >= item.quantity and product.in_stock:
            results.append(InventoryCheckItemResult(
                product_id=item.product_id,
                available=True,
                requested=item.quantity,
                current_stock=product.inventory
            ))
            INVENTORY_LOOKUPS_TOTAL.labels(result="in_stock").inc()
        else:
            results.append(InventoryCheckItemResult(
                product_id=item.product_id,
                available=False,
                requested=item.quantity,
                current_stock=product.inventory
            ))
            all_available = False
            INVENTORY_LOOKUPS_TOTAL.labels(result="insufficient_stock").inc()
            
    return InventoryCheckResponse(all_available=all_available, results=results)
