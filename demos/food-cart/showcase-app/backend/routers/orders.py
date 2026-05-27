from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from database import get_db
from schemas import OrderCreate, OrderOut, StatusUpdate
from websocket_manager import manager
from typing import List
import asyncio

router = APIRouter()

def _build_order_dict(conn, order_row) -> dict:
    order = dict(order_row)
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order['id'],)
    ).fetchall()
    order['items'] = [dict(i) for i in items]
    return order

@router.post("/api/orders", response_model=OrderOut)
async def create_order(body: OrderCreate):
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        order_number = f"#{count + 1:03d}"
        cur = conn.execute(
            "INSERT INTO orders (order_number, customer_name, status) VALUES (?, ?, 'received')",
            (order_number, body.customer_name)
        )
        order_id = cur.lastrowid
        for oi in body.items:
            item = conn.execute("SELECT * FROM menu_items WHERE id = ?", (oi.item_id,)).fetchone()
            if item:
                conn.execute(
                    "INSERT INTO order_items (order_id, item_id, item_name, item_price, quantity) VALUES (?, ?, ?, ?, ?)",
                    (order_id, oi.item_id, item['name'], item['price'], oi.quantity)
                )
        conn.commit()
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        result = _build_order_dict(conn, order)
        asyncio.create_task(manager.broadcast("admin", {"type": "new_order", "order": result}))
        return result
    finally:
        conn.close()

@router.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int):
    conn = get_db()
    try:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Order not found")
        return _build_order_dict(conn, order)
    finally:
        conn.close()

@router.get("/api/admin/orders", response_model=List[OrderOut])
def get_admin_orders():
    conn = get_db()
    try:
        orders = conn.execute(
            "SELECT * FROM orders WHERE status != 'complete' ORDER BY id DESC"
        ).fetchall()
        return [_build_order_dict(conn, o) for o in orders]
    finally:
        conn.close()

@router.patch("/api/admin/orders/{order_id}/status", response_model=OrderOut)
async def update_order_status(order_id: int, body: StatusUpdate):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (body.status, order_id)
        )
        conn.commit()
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        result = _build_order_dict(conn, order)
        asyncio.create_task(manager.broadcast(
            f"order:{order_id}", {"type": "status_update", "status": body.status}
        ))
        asyncio.create_task(manager.broadcast(
            "admin", {"type": "order_updated", "order_id": order_id, "status": body.status}
        ))
        return result
    finally:
        conn.close()

@router.websocket("/ws/order/{order_id}")
async def order_websocket(ws: WebSocket, order_id: int):
    await manager.connect(ws, f"order:{order_id}")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, f"order:{order_id}")

@router.websocket("/ws/admin")
async def admin_websocket(ws: WebSocket):
    await manager.connect(ws, "admin")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, "admin")
