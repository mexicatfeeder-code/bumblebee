from fastapi import APIRouter, HTTPException
from database import get_db
from schemas import MenuItemOut, CategoryOut
from typing import List

router = APIRouter()

@router.get("/api/menu", response_model=List[MenuItemOut])
def get_menu():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM menu_items WHERE available = 1 ORDER BY sort_order"
        ).fetchall()
        return [dict(r) | {"available": bool(r["available"])} for r in rows]
    finally:
        conn.close()

@router.get("/api/menu/{item_id}", response_model=MenuItemOut)
def get_menu_item(item_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row) | {"available": bool(row["available"])}
    finally:
        conn.close()

@router.get("/api/categories", response_model=List[CategoryOut])
def get_categories():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
