from pydantic import BaseModel, Field
from typing import List, Optional

class Product(BaseModel):
    id: str = Field(..., description="Unique product identifier")
    name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    price: float = Field(..., ge=0.0, description="Price in USD")
    inventory: int = Field(..., ge=0, description="Stock count")
    description: str = Field(..., description="Product description")
    tags: List[str] = Field(default_factory=list, description="Search tags")
    in_stock: bool = Field(True, description="Availability status")

class ProductListResponse(BaseModel):
    total: int
    products: List[Product]

class InventoryItemCheck(BaseModel):
    product_id: str
    quantity: int

class InventoryCheckRequest(BaseModel):
    items: List[InventoryItemCheck]

class InventoryCheckItemResult(BaseModel):
    product_id: str
    available: bool
    requested: int
    current_stock: int

class InventoryCheckResponse(BaseModel):
    all_available: bool
    results: List[InventoryCheckItemResult]

class SearchQueryResponse(BaseModel):
    query: str
    matches_count: int
    results: List[Product]
