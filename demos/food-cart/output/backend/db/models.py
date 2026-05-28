"""
SQLAlchemy ORM models for the Food Cart application.

Defines database schema for categories, menu items, orders, and settings
with proper relationships and constraints.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Category(Base):
    """
    Represents a food category (e.g., Burgers, Drinks, Desserts).

    Attributes:
        id: Primary key
        name: Category name (unique)
        description: Optional description
        display_order: Order for UI display
        is_active: Whether the category is currently visible
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    items: Mapped[List["MenuItem"]] = relationship(
        "MenuItem", back_populates="category", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("display_order >= 0", name="chk_categories_display_order_positive"),
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"


class MenuItem(Base):
    """
    Represents a single menu item belonging to a category.

    Attributes:
        id: Primary key
        category_id: Foreign key to categories
        name: Item name
        description: Item description
        price: Price in dollars (must be non-negative)
        is_available: Whether the item is currently available
        is_featured: Whether the item is featured/promoted
        image_url: Optional URL to item image
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """

    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="items")
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="menu_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="chk_menu_items_price_non_negative"),
        UniqueConstraint("category_id", "name", name="uq_menu_items_category_name"),
    )

    def __repr__(self) -> str:
        return f"<MenuItem(id={self.id}, name='{self.name}', price={self.price})>"


class Order(Base):
    """
    Represents a customer order.

    Attributes:
        id: Primary key
        customer_name: Optional customer name
        customer_phone: Optional customer phone number
        status: Order status (pending, preparing, ready, completed, cancelled)
        total_amount: Calculated total for the order
        notes: Optional customer notes
        created_at: Timestamp of order creation
        updated_at: Timestamp of last update
        completed_at: Timestamp when order was completed
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'preparing', 'ready', 'completed', 'cancelled')",
            name="chk_orders_status_valid",
        ),
        CheckConstraint("total_amount >= 0", name="chk_orders_total_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status='{self.status}', total={self.total_amount})>"


class OrderItem(Base):
    """
    Represents a single line item within an order.

    Attributes:
        id: Primary key
        order_id: Foreign key to orders
        menu_item_id: Foreign key to menu_items
        quantity: Number of items ordered (must be positive)
        unit_price: Price at time of order (snapshot)
        subtotal: quantity * unit_price
    """

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    menu_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="order_items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_order_items_unit_price_non_negative"),
        CheckConstraint("subtotal >= 0", name="chk_order_items_subtotal_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, qty={self.quantity}, subtotal={self.subtotal})>"


class Settings(Base):
    """
    Represents application settings stored as key-value pairs.

    Attributes:
        id: Primary key
        key: Setting key (unique)
        value: Setting value (stored as text)
        description: Optional description of the setting
        updated_at: Timestamp of last update
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("key", name="uq_settings_key"),
    )

    def __repr__(self) -> str:
        return f"<Settings(id={self.id}, key='{self.key}')>"
