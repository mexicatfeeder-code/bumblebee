from fastapi import APIRouter
from database import get_db
from schemas import SettingsOut

router = APIRouter()

@router.get("/api/settings", response_model=SettingsOut)
def get_settings():
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if not row:
            return {"cart_name": "The Rolling Bite", "tagline": "Fresh food, made fast",
                    "is_open": True, "estimated_wait_minutes": 10}
        return dict(row) | {"is_open": bool(row["is_open"])}
    finally:
        conn.close()
