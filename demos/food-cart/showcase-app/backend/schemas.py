from pydantic import BaseModel
from typing import Optional, List

class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int

class MenuItemOut(BaseModel):
    id: int
    name: str
    description: str
    price: int          # cents
    category_id: int
    photo_url: Optional[str]
    available: bool
    sort_order: int

class OrderItemIn(BaseModel):
    item_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_name: str
    items: List[OrderItemIn]

class OrderItemOut(BaseModel):
    id: int
    item_name: str
    item_price: int     # cents
    quantity: int

class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_name: str
    status: str
    created_at: str
    items: List[OrderItemOut]

class SettingsOut(BaseModel):
    cart_name: str
    tagline: str
    is_open: bool
    estimated_wait_minutes: int

class StatusUpdate(BaseModel):
    status: str
