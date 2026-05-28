"""
FastAPI API endpoints for Category CRUD operations.

Provides routes for listing, creating, updating, deleting,
and reordering food categories in the Food Cart application.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import Category

router = APIRouter(prefix="/categories", tags=["categories"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    """Schema for creating a new category."""

    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: str | None = Field(None, description="Optional description")
    display_order: int = Field(0, ge=0, description="Display order position")
    is_active: bool = Field(True, description="Whether the category is visible")


class CategoryUpdate(BaseModel):
    """Schema for updating an existing category."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = Field(None)


class CategoryResponse(BaseModel):
    """Schema for a category response."""

    id: int
    name: str
    description: str | None
    display_order: int
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ReorderItem(BaseModel):
    """Single item in a reorder request."""

    id: int
    display_order: int = Field(..., ge=0)


class ReorderRequest(BaseModel):
    """Schema for reordering categories."""

    categories: List[ReorderItem]


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def get_db():
    """
    Database session dependency.

    Importing from main to reuse the existing session factory.
    """
    from app.main import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[CategoryResponse])
def list_categories(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of records to return"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
) -> List[Category]:
    """
    List all categories with optional filtering and pagination.

    Args:
        skip: Number of records to skip (pagination offset).
        limit: Maximum number of records to return.
        is_active: Optional filter for active/inactive categories.
        db: Database session.

    Returns:
        List of category objects sorted by display_order.
    """
    query = db.query(Category)

    if is_active is not None:
        query = query.filter(Category.is_active == is_active)

    query = query.order_by(Category.display_order.asc())
    categories = query.offset(skip).limit(limit).all()
    return categories


@router.post("/", response_model=CategoryResponse, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
) -> Category:
    """
    Create a new category.

    Args:
        payload: Category creation data.
        db: Database session.

    Returns:
        The newly created category.

    Raises:
        HTTPException: If a category with the same name already exists.
    """
    # Check for duplicate name
    existing = (
        db.query(Category)
        .filter(Category.name.ilike(payload.name))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Category with name '{payload.name}' already exists",
        )

    category = Category(
        name=payload.name,
        description=payload.description,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> Category:
    """
    Get a single category by ID.

    Args:
        category_id: The category primary key.
        db: Database session.

    Returns:
        The category object.

    Raises:
        HTTPException: If the category is not found.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
) -> Category:
    """
    Update an existing category.

    Only the fields provided in the payload will be updated.

    Args:
        category_id: The category primary key.
        payload: Fields to update.
        db: Database session.

    Returns:
        The updated category.

    Raises:
        HTTPException: If the category is not found or name conflicts.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Check for duplicate name if name is being changed
    if "name" in update_data and update_data["name"] != category.name:
        existing = (
            db.query(Category)
            .filter(
                Category.name.ilike(update_data["name"]),
                Category.id != category_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Category with name '{update_data['name']}' already exists",
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a category and all its associated menu items.

    Args:
        category_id: The category primary key.
        db: Database session.

    Raises:
        HTTPException: If the category is not found.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()
    return None


@router.patch("/reorder", status_code=204)
def reorder_categories(
    payload: ReorderRequest,
    db: Session = Depends(get_db),
) -> None:
    """
    Reorder categories by updating their display_order values.

    Accepts a list of category IDs with their new display_order positions
    and updates them in a single transaction.

    Args:
        payload: List of category reorder items.
        db: Database session.

    Raises:
        HTTPException: If any category ID is not found.
    """
    # Validate all category IDs exist before making any changes
    category_ids = {item.id for item in payload.categories}
    existing_ids = {
        cat.id
        for cat in db.query(Category.id).filter(Category.id.in_(category_ids)).all()
    }

    missing = category_ids - existing_ids
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Categories not found: {sorted(missing)}",
        )

    # Apply reorder updates
    for item in payload.categories:
        category = db.query(Category).filter(Category.id == item.id).first()
        if category:
            category.display_order = item.display_order

    db.commit()
    return None
