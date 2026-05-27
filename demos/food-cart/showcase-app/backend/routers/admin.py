from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from database import get_db
from schemas import MenuItemOut, CategoryOut, SettingsOut
from typing import Optional, List
import shutil, uuid, os

router = APIRouter()
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _save_photo(photo: UploadFile) -> Optional[str]:
    if not photo or not photo.filename:
        return None
    ext = photo.filename.rsplit('.', 1)[-1] if '.' in photo.filename else 'jpg'
    filename = f"{uuid.uuid4()}.{ext}"
    dest = os.path.join(UPLOAD_DIR, filename)
    with open(dest, 'wb') as f:
        shutil.copyfileobj(photo.file, f)
    return f"/uploads/{filename}"

# Menu endpoints
@router.get("/api/admin/menu", response_model=List[MenuItemOut])
def admin_get_menu():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM menu_items ORDER BY sort_order").fetchall()
        return [dict(r) | {"available": bool(r["available"])} for r in rows]
    finally:
        conn.close()

@router.post("/api/admin/menu", response_model=MenuItemOut)
def admin_create_item(
    name: str = Form(...),
    description: str = Form(''),
    price: int = Form(...),
    category_id: int = Form(...),
    sort_order: int = Form(0),
    available: str = Form('1'),
    photo: Optional[UploadFile] = File(None),
):
    photo_url = _save_photo(photo) if photo and photo.filename else None
    avail = available not in ('0', 'false', 'False')
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO menu_items (name, description, price, category_id, sort_order, available, photo_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, description, price, category_id, sort_order, int(avail), photo_url)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row) | {"available": bool(row["available"])}
    finally:
        conn.close()

@router.put("/api/admin/menu/{item_id}", response_model=MenuItemOut)
def admin_update_item(
    item_id: int,
    name: str = Form(...),
    description: str = Form(''),
    price: int = Form(...),
    category_id: int = Form(...),
    sort_order: int = Form(0),
    available: str = Form('1'),
    photo: Optional[UploadFile] = File(None),
):
    photo_url = _save_photo(photo) if photo and photo.filename else None
    avail = available not in ('0', 'false', 'False')
    conn = get_db()
    try:
        existing = conn.execute("SELECT photo_url FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")
        final_photo = photo_url if photo_url else existing["photo_url"]
        conn.execute(
            "UPDATE menu_items SET name=?, description=?, price=?, category_id=?, sort_order=?, available=?, photo_url=? WHERE id=?",
            (name, description, price, category_id, sort_order, int(avail), final_photo, item_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) | {"available": bool(row["available"])}
    finally:
        conn.close()

@router.delete("/api/admin/menu/{item_id}")
def admin_delete_item(item_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@router.patch("/api/admin/menu/{item_id}/availability")
def admin_toggle_availability(item_id: int, body: dict):
    available = body.get("available", True)
    conn = get_db()
    try:
        conn.execute("UPDATE menu_items SET available = ? WHERE id = ?", (int(available), item_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

# Category endpoints
@router.get("/api/admin/categories", response_model=List[CategoryOut])
def admin_get_categories():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@router.post("/api/admin/categories", response_model=CategoryOut)
def admin_create_category(body: dict):
    name = body.get("name", "")
    sort_order = body.get("sort_order", 0)
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, sort_order))
        conn.commit()
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()

# Settings endpoints
@router.get("/api/admin/settings", response_model=SettingsOut)
def admin_get_settings():
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row) | {"is_open": bool(row["is_open"])}
    finally:
        conn.close()

@router.put("/api/admin/settings", response_model=SettingsOut)
def admin_update_settings(body: dict):
    conn = get_db()
    try:
        conn.execute('''
            UPDATE settings SET
                cart_name = ?,
                tagline = ?,
                is_open = ?,
                estimated_wait_minutes = ?
            WHERE id = 1
        ''', (
            body.get("cart_name", "The Rolling Bite"),
            body.get("tagline", "Fresh food, made fast"),
            int(body.get("is_open", True)),
            body.get("estimated_wait_minutes", 10),
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row) | {"is_open": bool(row["is_open"])}
    finally:
        conn.close()
