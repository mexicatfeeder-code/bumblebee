from pydantic import BaseModel
from typing import List, Optional

class Category(BaseModel):
    id: int
    name: str
    sort_order: int

class CategoryIn(BaseModel):
    name: str
    sort_order: int = 0

class MenuItem(BaseModel):
    id: int
    name: str
    description: str
    price: int
    category_id: int
    category: str
    photo_url: str
    available: bool
    sort_order: int

class MenuItemIn(BaseModel):
    name: str
    description: str
    price: int
    category_id: int
    photo_url: str = ''
    available: bool = True
    sort_order: int = 0

class OrderItem(BaseModel):
    id: int
    order_id: int
    item_id: int
    item_name: str
    item_price: int
    quantity: int

class Order(BaseModel):
    id: int
    order_number: str
    customer_name: str
    status: str
    created_at: str
    updated_at: str
    items: List[OrderItem]

class CreateOrderItem(BaseModel):
    item_id: int
    quantity: int

class CreateOrder(BaseModel):
    customer_name: str
    items: List[CreateOrderItem]

class StatusUpdate(BaseModel):
    status: str

class Settings(BaseModel):
    cart_name: str
    tagline: str
    is_open: bool
    estimated_wait_minutes: int
    admin_pin: str

class PinCheck(BaseModel):
    pin: str
