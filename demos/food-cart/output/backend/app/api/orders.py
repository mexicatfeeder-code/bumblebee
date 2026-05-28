"""
FastAPI API endpoints for order management in the Food Cart application.

Provides endpoints for submitting new orders, listing orders with timestamps,
updating order status, and retrieving daily sales summaries.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import MenuItem, Order, OrderItem

# Create router for orders endpoints
router = APIRouter(prefix="/api/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class OrderItemCreate(BaseModel):
    """Schema for creating an order item."""

    menu_item_id: int = Field(..., description="ID of the menu item")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    special_instructions: Optional[str] = Field(
        None, max_length=500, description="Special instructions for this item"
    )


class OrderCreate(BaseModel):
    """Schema for submitting a new order."""

    customer_name: Optional[str] = Field(
        None, max_length=100, description="Customer name"
    )
    customer_phone: Optional[str] = Field(
        None, max_length=20, description="Customer phone number"
    )
    items: List[OrderItemCreate] = Field(
        ..., min_length=1, description="List of items to order"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Additional order notes"
    )


class OrderItemResponse(BaseModel):
    """Schema for an order item in responses."""

    id: int
    menu_item_id: int
    quantity: int
    unit_price: float
    special_instructions: Optional[str]
    total_price: float

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """Schema for an order in responses."""

    id: int
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: str
    total_amount: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    """Schema for updating order status."""

    status: str = Field(
        ...,
        description="New order status",
    )


class DailySalesSummary(BaseModel):
    """Schema for daily sales summary response."""

    date: str
    total_orders: int
    total_revenue: float
    average_order_value: float
    items_sold: int


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def validate_order_items(
    items: List[OrderItemCreate], db: Session
) -> List[MenuItem]:
    """
    Validate that all menu items exist and are available.

    Args:
        items: List of order items to validate.
        db: Database session.

    Returns:
        List of validated MenuItem objects.

    Raises:
        HTTPException: If a menu item is not found or unavailable.
    """
    validated_items = []
    for item in items:
        menu_item = db.query(MenuItem).filter(MenuItem.id == item.menu_item_id).first()
        if not menu_item:
            raise HTTPException(
                status_code=404,
                detail=f"Menu item with ID {item.menu_item_id} not found",
            )
        if not menu_item.is_available:
            raise HTTPException(
                status_code=400,
                detail=f"Menu item '{menu_item.name}' is not available",
            )
        validated_items.append(menu_item)
    return validated_items


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=OrderResponse, status_code=201)
def submit_order(order_data: OrderCreate, db: Session = Depends(lambda: None)):
    """
    Submit a new order.

    Creates a new order with the specified items. Validates that all menu items
    exist and are available. Calculates the total amount based on menu item prices.

    Args:
        order_data: The order creation data.
        db: Database session (injected dependency).

    Returns:
        OrderResponse: The created order with all items.

    Raises:
        HTTPException: If validation fails or an error occurs.
    """
    # Validate menu items exist and are available
    menu_items = validate_order_items(order_data.items, db)

    # Calculate total amount
    total_amount = 0.0
    order_items = []
    for i, item_data in enumerate(order_data.items):
        menu_item = menu_items[i]
        item_total = menu_item.price * item_data.quantity
        total_amount += item_total
        order_items.append(
            OrderItem(
                menu_item_id=menu_item.id,
                quantity=item_data.quantity,
                unit_price=menu_item.price,
                special_instructions=item_data.special_instructions,
                total_price=item_total,
            )
        )

    # Create the order
    order = Order(
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        status="pending",
        total_amount=total_amount,
        notes=order_data.notes,
        items=order_items,
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return order


@router.get("/", response_model=List[OrderResponse])
def list_orders(
    status: Optional[str] = Query(
        None, description="Filter orders by status"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    db: Session = Depends(lambda: None),
):
    """
    List orders with timestamps.

    Retrieves a paginated list of orders, optionally filtered by status.
    Orders are returned sorted by creation time (newest first).

    Args:
        status: Optional status filter (e.g., 'pending', 'preparing', 'ready', 'completed', 'cancelled').
        limit: Maximum number of orders to return (default: 100).
        offset: Number of orders to skip for pagination (default: 0).
        db: Database session (injected dependency).

    Returns:
        List[OrderResponse]: List of orders matching the criteria.
    """
    query = db.query(Order)

    # Filter by status if provided
    if status:
        query = query.filter(Order.status == status)

    # Sort by creation time (newest first)
    query = query.order_by(Order.created_at.desc())

    # Apply pagination
    orders = query.offset(offset).limit(limit).all()

    return orders


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(lambda: None)):
    """
    Get a single order by ID.

    Args:
        order_id: The ID of the order to retrieve.
        db: Database session (injected dependency).

    Returns:
        OrderResponse: The requested order.

    Raises:
        HTTPException: If the order is not found.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(lambda: None),
):
    """
    Update the status of an order.

    Updates the order status and records the timestamp of the change.
    Validates that the new status is a valid transition.

    Valid statuses: pending, preparing, ready, completed, cancelled

    Args:
        order_id: The ID of the order to update.
        status_update: The new status for the order.
        db: Database session (injected dependency).

    Returns:
        OrderResponse: The updated order.

    Raises:
        HTTPException: If the order is not found or the status transition is invalid.
    """
    valid_statuses = {"pending", "preparing", "ready", "completed", "cancelled"}
    if status_update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Validate status transitions
    current_status = order.status
    valid_transitions = {
        "pending": {"preparing", "cancelled"},
        "preparing": {"ready", "cancelled"},
        "ready": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }

    allowed_next = valid_transitions.get(current_status, set())
    if status_update.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{status_update.status}'. "
            f"Allowed transitions: {', '.join(sorted(allowed_next)) if allowed_next else 'none (terminal state)'}",
        )

    # Update the order status
    order.status = status_update.status
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return order


@router.get("/summary/daily", response_model=List[DailySalesSummary])
def get_daily_sales_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to include in summary"),
    db: Session = Depends(lambda: None),
):
    """
    Get daily sales summary for the specified number of days.

    Calculates total orders, total revenue, average order value, and items sold
    for each day in the specified range.

    Args:
        days: Number of days to include in the summary (default: 7, max: 90).
        db: Database session (injected dependency).

    Returns:
        List[DailySalesSummary]: Daily sales summaries ordered by date (newest first).
    """
    # Calculate the date range
    end_date = date.today()
    start_date = end_date - __import__("datetime").timedelta(days=days - 1)

    summaries = []
    current_date = start_date

    while current_date <= end_date:
        next_date = current_date + __import__("datetime").timedelta(days=1)

        # Query orders for this day
        day_orders = (
            db.query(Order)
            .filter(
                Order.created_at >= current_date,
                Order.created_at < next_date,
                Order.status != "cancelled",
            )
            .all()
        )

        total_orders = len(day_orders)
        total_revenue = sum(order.total_amount for order in day_orders)
        average_order_value = total_revenue / total_orders if total_orders > 0 else 0.0

        # Count total items sold
        items_sold = 0
        for order in day_orders:
            for item in order.items:
                items_sold += item.quantity

        summaries.append(
            DailySalesSummary(
                date=current_date.isoformat(),
                total_orders=total_orders,
                total_revenue=round(total_revenue, 2),
                average_order_value=round(average_order_value, 2),
                items_sold=items_sold,
            )
        )

        current_date = next_date

    # Return newest first
    summaries.reverse()
    return summaries
