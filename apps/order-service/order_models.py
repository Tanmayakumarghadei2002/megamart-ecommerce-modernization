from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    FAILED = "FAILED"

class CartItem(BaseModel):
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product name")
    unit_price: float = Field(..., ge=0.0, description="Unit price in USD")
    quantity: int = Field(..., ge=1, description="Quantity ordered")

class ShippingAddress(BaseModel):
    street: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=2)
    zip_code: str = Field(..., min_length=3)
    country: str = Field(default="USA")

class CheckoutRequest(BaseModel):
    user_id: str = Field(..., description="Customer ID")
    customer_email: str = Field(..., min_length=5, description="Receipt email")
    items: List[CartItem] = Field(..., min_length=1, description="Ordered cart items")
    shipping_address: ShippingAddress
    payment_method: str = Field(default="CREDIT_CARD")

class CheckoutResponse(BaseModel):
    order_id: str
    user_id: str
    status: OrderStatus
    total_amount: float
    item_count: int
    receipt_url: Optional[str]
    created_at: str
    message: str

class OrderRecord(BaseModel):
    order_id: str
    user_id: str
    customer_email: str
    status: OrderStatus
    items: List[CartItem]
    shipping_address: ShippingAddress
    total_amount: float
    receipt_s3_key: Optional[str]
    created_at: str
    updated_at: str
