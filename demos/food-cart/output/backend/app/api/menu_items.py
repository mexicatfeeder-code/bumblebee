"""
FastAPI API router for Menu Items CRUD operations.

Provides endpoints for creating, reading, updating, and deleting menu items,
including photo upload handling and availability toggle functionality.
"""

import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.schemas.menu_item import (
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
)
from db.models import Category, MenuItem

# Router instance
router = APIRouter(prefix="/api/menu-items", tags=["Menu Items"])

# Photo upload configuration
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "menu_photos")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def get_db():
    """
    Database session dependency.

    Yields:
        Session: An active SQLAlchemy database session.
    """
    from app.main import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_file_extension(filename: str) -> bool:
    """
    Validate that the uploaded file has an allowed extension.

    Args:
        filename: The name of the uploaded file.

    Returns:
        bool: True if the extension is allowed, False otherwise.
    """
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def save_upload_file(file: UploadFile) -> str:
    """
    Save an uploaded file to the upload directory with a unique filename.

    Args:
        file: The uploaded file object.

    Returns:
        str: The relative path to the saved file.

    Raises:
        HTTPException: If the file is too large or has an invalid extension.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content and check size
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE / (1024 * 1024)}MB",
        )

    # Generate unique filename
    _, ext = os.path.splitext(file.filename.lower())
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Write file to disk
    with open(file_path, "wb") as f:
        f.write(content)

    # Return relative path for storage
    return f"uploads/menu_photos/{unique_filename}"


def delete_photo(photo_path: str) -> None:
    """
    Delete a photo file from the upload directory.

    Args:
        photo_path: The relative path to the photo file.
    """
    if not photo_path:
        return

    full_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        photo_path,
    )

    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except OSError:
            pass  # Log error in production


@router.get("/", response_model=List[MenuItemResponse])
def list_menu_items(
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    is_available: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[MenuItem]:
    """
    List all menu items with optional filtering.

    Args:
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return.
        category_id: Filter by category ID.
        is_available: Filter by availability status.
        search: Search by item name or description.
        db: Database session.

    Returns:
        List[MenuItem]: A list of menu items matching the criteria.
    """
    query = db.query(MenuItem)

    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)

    if is_available is not None:
        query = query.filter(MenuItem.is_available == is_available)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            MenuItem.name.ilike(search_term) | MenuItem.description.ilike(search_term)
        )

    return query.order_by(MenuItem.display_order, MenuItem.name).offset(skip).limit(limit).all()


@router.get("/{item_id}", response_model=MenuItemResponse)
def get_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> MenuItem:
    """
    Get a single menu item by ID.

    Args:
        item_id: The ID of the menu item.
        db: Database session.

    Returns:
        MenuItem: The requested menu item.

    Raises:
        HTTPException: If the menu item is not found.
    """
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    return menu_item


@router.post("/", response_model=MenuItemResponse, status_code=201)
def create_menu_item(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    category_id: int = Form(...),
    display_order: int = Form(0),
    is_available: bool = Form(True),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
) -> MenuItem:
    """
    Create a new menu item with optional photo upload.

    Args:
        name: Name of the menu item.
        description: Optional description of the item.
        price: Price of the item.
        category_id: ID of the category this item belongs to.
        display_order: Order for UI display.
        is_available: Whether the item is currently available.
        photo: Optional photo file upload.
        db: Database session.

    Returns:
        MenuItem: The newly created menu item.

    Raises:
        HTTPException: If the category doesn't exist or price is invalid.
    """
    # Validate category exists
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Validate price
    if price < 0:
        raise HTTPException(status_code=400, detail="Price cannot be negative")

    # Handle photo upload
    photo_path = None
    if photo and photo.filename:
        photo_path = save_upload_file(photo)

    # Create menu item
    menu_item = MenuItem(
        name=name,
        description=description,
        price=price,
        category_id=category_id,
        display_order=display_order,
        is_available=is_available,
        photo_path=photo_path,
    )

    db.add(menu_item)
    db.commit()
    db.refresh(menu_item)

    return menu_item


@router.put("/{item_id}", response_model=MenuItemResponse)
def update_menu_item(
    item_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    category_id: Optional[int] = Form(None),
    display_order: Optional[int] = Form(None),
    is_available: Optional[bool] = Form(None),
    photo: Optional[UploadFile] = File(None),
    remove_photo: bool = Form(False),
    db: Session = Depends(get_db),
) -> MenuItem:
    """
    Update an existing menu item with optional photo replacement.

    Args:
        item_id: The ID of the menu item to update.
        name: Updated name of the menu item.
        description: Updated description.
        price: Updated price.
        category_id: Updated category ID.
        display_order: Updated display order.
        is_available: Updated availability status.
        photo: Optional new photo file upload.
        remove_photo: Whether to remove the existing photo.
        db: Database session.

    Returns:
        MenuItem: The updated menu item.

    Raises:
        HTTPException: If the menu item or category is not found.
    """
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Validate category if changing
    if category_id is not None and category_id != menu_item.category_id:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    # Validate price if changing
    if price is not None and price < 0:
        raise HTTPException(status_code=400, detail="Price cannot be negative")

    # Handle photo updates
    if remove_photo:
        delete_photo(menu_item.photo_path)
        menu_item.photo_path = None
    elif photo and photo.filename:
        # Delete old photo before uploading new one
        if menu_item.photo_path:
            delete_photo(menu_item.photo_path)
        menu_item.photo_path = save_upload_file(photo)

    # Update fields
    if name is not None:
        menu_item.name = name
    if description is not None:
        menu_item.description = description
    if price is not None:
        menu_item.price = price
    if category_id is not None:
        menu_item.category_id = category_id
    if display_order is not None:
        menu_item.display_order = display_order
    if is_available is not None:
        menu_item.is_available = is_available

    menu_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(menu_item)

    return menu_item


@router.patch("/{item_id}/toggle-availability", response_model=MenuItemResponse)
def toggle_availability(
    item_id: int,
    db: Session = Depends(get_db),
) -> MenuItem:
    """
    Toggle the availability status of a menu item.

    Flips the is_available flag between True and False.

    Args:
        item_id: The ID of the menu item.
        db: Database session.

    Returns:
        MenuItem: The updated menu item with toggled availability.

    Raises:
        HTTPException: If the menu item is not found.
    """
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    menu_item.is_available = not menu_item.is_available
    menu_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(menu_item)

    return menu_item


@router.delete("/{item_id}", status_code=204)
def delete_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a menu item and its associated photo.

    Args:
        item_id: The ID of the menu item to delete.
        db: Database session.

    Raises:
        HTTPException: If the menu item is not found.
    """
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Delete associated photo file
    if menu_item.photo_path:
        delete_photo(menu_item.photo_path)

    db.delete(menu_item)
    db.commit()

    return None


@router.post("/{item_id}/photo", response_model=MenuItemResponse)
def upload_photo(
    item_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MenuItem:
    """
    Upload or replace a photo for an existing menu item.

    Args:
        item_id: The ID of the menu item.
        photo: The photo file to upload.
        db: Database session.

    Returns:
        MenuItem: The updated menu item with the new photo path.

    Raises:
        HTTPException: If the menu item is not found.
    """
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Delete old photo if exists
    if menu_item.photo_path:
        delete_photo(menu_item.photo_path)

    # Upload new photo
    menu_item.photo_path = save_upload_file(photo)
    menu_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(menu_item)

    return menu_item


@router.delete("/{item_id}/photo", response_model=MenuItemResponse)
def remove_photo(
    item_id: int,
    db: Session = Depends(get_db),
) -> MenuItem:
    """
    Remove the photo from a menu item.

    Args:
        item_id: The ID of the menu item.
        db: Database session.

    Returns:
        MenuItem: The updated menu item with photo path cleared.

    Raises:
        HTTPException: If the menu item is not found.
    """
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Delete photo file if exists
    if menu_item.photo_path:
        delete_photo(menu_item.photo_path)
        menu_item.photo_path = None
        menu_item.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(menu_item)

    return menu_item
