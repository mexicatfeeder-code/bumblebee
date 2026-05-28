"""
FastAPI API endpoints for app settings management.

Provides endpoints to get and update cart name, operating hours,
and admin PIN for the Food Cart application.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models import Settings
from db.session import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ─── Pydantic Schemas ────────────────────────────────────────────────


class CartNameUpdate(BaseModel):
    """Schema for updating the cart name."""

    cart_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the food cart",
        examples=["Tony's Tacos", "Burger Barn"],
    )


class OperatingHoursUpdate(BaseModel):
    """Schema for updating operating hours."""

    open_time: str = Field(
        ...,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Opening time in HH:MM 24-hour format",
        examples=["08:00", "10:30"],
    )
    close_time: str = Field(
        ...,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Closing time in HH:MM 24-hour format",
        examples=["18:00", "22:00"],
    )
    is_open: bool = Field(
        default=True,
        description="Whether the cart is currently open for orders",
    )


class AdminPINUpdate(BaseModel):
    """Schema for updating the admin PIN."""

    current_pin: str = Field(
        ...,
        min_length=4,
        max_length=20,
        description="Current admin PIN for verification",
    )
    new_pin: str = Field(
        ...,
        min_length=4,
        max_length=20,
        description="New admin PIN to set",
    )


class SettingsResponse(BaseModel):
    """Schema for the full settings response."""

    cart_name: str
    open_time: str
    close_time: str
    is_open: bool
    has_admin_pin: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CartNameResponse(BaseModel):
    """Schema for cart name response."""

    cart_name: str
    updated_at: Optional[datetime] = None


class OperatingHoursResponse(BaseModel):
    """Schema for operating hours response."""

    open_time: str
    close_time: str
    is_open: bool
    updated_at: Optional[datetime] = None


class AdminPINStatusResponse(BaseModel):
    """Schema for admin PIN status response."""

    has_admin_pin: bool
    pin_length: int
    updated_at: Optional[datetime] = None


# ─── Helper Functions ────────────────────────────────────────────────


def get_or_create_settings(db: Session) -> Settings:
    """
    Retrieve existing settings or create a new default settings record.

    Args:
        db: Active database session.

    Returns:
        Settings: The settings record (existing or newly created).
    """
    settings = db.query(Settings).first()
    if settings is None:
        settings = Settings(
            cart_name="My Food Cart",
            open_time="08:00",
            close_time="18:00",
            is_open=True,
            admin_pin_hash=None,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def verify_admin_pin(settings: Settings, current_pin: str) -> bool:
    """
    Verify the provided PIN against the stored admin PIN.

    Args:
        settings: The settings record containing the stored PIN.
        current_pin: The PIN to verify.

    Returns:
        bool: True if the PIN matches, False otherwise.
    """
    if settings.admin_pin_hash is None:
        return False
    return settings.admin_pin_hash == current_pin


# ─── API Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=SettingsResponse, summary="Get all settings")
def get_all_settings(db: Session = Depends(get_db)):
    """
    Retrieve all application settings.

    Returns the cart name, operating hours, open status, and
    whether an admin PIN is configured.

    Returns:
        SettingsResponse: Complete settings object.

    Raises:
        HTTPException: If settings cannot be retrieved.
    """
    try:
        settings = get_or_create_settings(db)
        return SettingsResponse(
            cart_name=settings.cart_name,
            open_time=settings.open_time,
            close_time=settings.close_time,
            is_open=settings.is_open,
            has_admin_pin=settings.admin_pin_hash is not None,
            updated_at=settings.updated_at,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve settings: {str(e)}",
        )


# ─── Cart Name Endpoints ─────────────────────────────────────────────


@router.get(
    "/cart-name",
    response_model=CartNameResponse,
    summary="Get cart name",
)
def get_cart_name(db: Session = Depends(get_db)):
    """
    Retrieve the current cart name.

    Returns:
        CartNameResponse: The cart name and last update timestamp.
    """
    settings = get_or_create_settings(db)
    return CartNameResponse(
        cart_name=settings.cart_name,
        updated_at=settings.updated_at,
    )


@router.put(
    "/cart-name",
    response_model=CartNameResponse,
    summary="Update cart name",
)
def update_cart_name(
    payload: CartNameUpdate,
    db: Session = Depends(get_db),
):
    """
    Update the food cart name.

    Args:
        payload: The new cart name.
        db: Active database session.

    Returns:
        CartNameResponse: Updated cart name and timestamp.

    Raises:
        HTTPException: If the update fails.
    """
    try:
        settings = get_or_create_settings(db)
        settings.cart_name = payload.cart_name
        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)
        return CartNameResponse(
            cart_name=settings.cart_name,
            updated_at=settings.updated_at,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update cart name: {str(e)}",
        )


# ─── Operating Hours Endpoints ───────────────────────────────────────


@router.get(
    "/operating-hours",
    response_model=OperatingHoursResponse,
    summary="Get operating hours",
)
def get_operating_hours(db: Session = Depends(get_db)):
    """
    Retrieve the current operating hours and open status.

    Returns:
        OperatingHoursResponse: Operating hours and open status.
    """
    settings = get_or_create_settings(db)
    return OperatingHoursResponse(
        open_time=settings.open_time,
        close_time=settings.close_time,
        is_open=settings.is_open,
        updated_at=settings.updated_at,
    )


@router.put(
    "/operating-hours",
    response_model=OperatingHoursResponse,
    summary="Update operating hours",
)
def update_operating_hours(
    payload: OperatingHoursUpdate,
    db: Session = Depends(get_db),
):
    """
    Update the food cart operating hours and open status.

    Validates that close_time is after open_time.

    Args:
        payload: New operating hours and open status.
        db: Active database session.

    Returns:
        OperatingHoursResponse: Updated operating hours.

    Raises:
        HTTPException: If validation fails or update fails.
    """
    # Validate that close time is after open time
    if payload.close_time <= payload.open_time:
        raise HTTPException(
            status_code=400,
            detail="Close time must be after open time.",
        )

    try:
        settings = get_or_create_settings(db)
        settings.open_time = payload.open_time
        settings.close_time = payload.close_time
        settings.is_open = payload.is_open
        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)
        return OperatingHoursResponse(
            open_time=settings.open_time,
            close_time=settings.close_time,
            is_open=settings.is_open,
            updated_at=settings.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update operating hours: {str(e)}",
        )


# ─── Admin PIN Endpoints ─────────────────────────────────────────────


@router.get(
    "/admin-pin/status",
    response_model=AdminPINStatusResponse,
    summary="Get admin PIN status",
)
def get_admin_pin_status(db: Session = Depends(get_db)):
    """
    Check if an admin PIN is configured.

    Does not return the actual PIN for security reasons.

    Returns:
        AdminPINStatusResponse: PIN configuration status.
    """
    settings = get_or_create_settings(db)
    pin_length = len(settings.admin_pin_hash) if settings.admin_pin_hash else 0
    return AdminPINStatusResponse(
        has_admin_pin=settings.admin_pin_hash is not None,
        pin_length=pin_length,
        updated_at=settings.updated_at,
    )


@router.put(
    "/admin-pin",
    response_model=AdminPINStatusResponse,
    summary="Update admin PIN",
)
def update_admin_pin(
    payload: AdminPINUpdate,
    db: Session = Depends(get_db),
):
    """
    Update the admin PIN.

    Requires the current PIN for verification (unless no PIN is set yet).

    Args:
        payload: Current PIN and new PIN.
        db: Active database session.

    Returns:
        AdminPINStatusResponse: Updated PIN status.

    Raises:
        HTTPException: If current PIN is incorrect or update fails.
    """
    try:
        settings = get_or_create_settings(db)

        # If a PIN is already set, verify the current PIN
        if settings.admin_pin_hash is not None:
            if not verify_admin_pin(settings, payload.current_pin):
                raise HTTPException(
                    status_code=401,
                    detail="Current PIN is incorrect.",
                )

        # Set the new PIN
        settings.admin_pin_hash = payload.new_pin
        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)

        return AdminPINStatusResponse(
            has_admin_pin=settings.admin_pin_hash is not None,
            pin_length=len(settings.admin_pin_hash),
            updated_at=settings.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update admin PIN: {str(e)}",
        )


@router.delete(
    "/admin-pin",
    response_model=AdminPINStatusResponse,
    summary="Remove admin PIN",
)
def remove_admin_pin(
    current_pin: str,
    db: Session = Depends(get_db),
):
    """
    Remove the admin PIN protection.

    Requires the current PIN for verification.

    Args:
        current_pin: Current PIN for verification.
        db: Active database session.

    Returns:
        AdminPINStatusResponse: Updated PIN status (has_admin_pin=False).

    Raises:
        HTTPException: If current PIN is incorrect or no PIN is set.
    """
    try:
        settings = get_or_create_settings(db)

        if settings.admin_pin_hash is None:
            raise HTTPException(
                status_code=400,
                detail="No admin PIN is currently set.",
            )

        if not verify_admin_pin(settings, current_pin):
            raise HTTPException(
                status_code=401,
                detail="Current PIN is incorrect.",
            )

        settings.admin_pin_hash = None
        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)

        return AdminPINStatusResponse(
            has_admin_pin=False,
            pin_length=0,
            updated_at=settings.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove admin PIN: {str(e)}",
        )
