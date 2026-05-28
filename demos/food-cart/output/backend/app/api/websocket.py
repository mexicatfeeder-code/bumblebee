"""
WebSocket API endpoints for the Food Cart backend.

Provides real-time communication channels for:
- Order status updates (customer-facing)
- New order notifications (admin-facing)
"""

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton WebSocket manager instance
ws_manager = WebSocketManager()


@router.websocket("/ws/orders/{order_id}")
async def websocket_order_updates(websocket: WebSocket, order_id: str) -> None:
    """
    WebSocket endpoint for real-time order status updates.

    Customers connect to this endpoint to receive live updates
    about their specific order (e.g., preparing, ready, delivered).

    Args:
        websocket: The FastAPI WebSocket connection.
        order_id: The unique order identifier to subscribe to.
    """
    client_id = str(uuid.uuid4())
    channel = f"order:{order_id}"

    await ws_manager.connect(websocket, client_id, channel)

    try:
        # Send initial connection confirmation
        await ws_manager.send_to_client(
            client_id,
            {
                "type": "connection_established",
                "client_id": client_id,
                "channel": channel,
                "message": f"Subscribed to updates for order {order_id}",
            },
        )

        while True:
            # Receive messages from client (e.g., ping/heartbeat)
            data = await websocket.receive_text()

            # Handle client heartbeat/ping
            if data.strip().lower() == "ping":
                await ws_manager.send_to_client(
                    client_id,
                    {"type": "pong", "timestamp": "ok"},
                )
            else:
                logger.info(f"Received message from client {client_id}: {data}")
    except WebSocketDisconnect:
        logger.info(f"Order update client {client_id} disconnected from {channel}")
    except Exception as e:
        logger.error(f"Error in order updates WebSocket for client {client_id}: {e}")
    finally:
        await ws_manager.disconnect(client_id)


@router.websocket("/ws/admin/orders")
async def websocket_admin_orders(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for admin new order notifications.

    Restaurant staff/admins connect to this endpoint to receive
    real-time notifications when new orders are placed.

    Args:
        websocket: The FastAPI WebSocket connection.
    """
    client_id = str(uuid.uuid4())
    channel = "admin:orders"

    await ws_manager.connect(websocket, client_id, channel)

    try:
        # Send initial connection confirmation
        await ws_manager.send_to_client(
            client_id,
            {
                "type": "connection_established",
                "client_id": client_id,
                "channel": channel,
                "message": "Subscribed to admin order notifications",
            },
        )

        while True:
            # Receive messages from client (e.g., ping/heartbeat)
            data = await websocket.receive_text()

            # Handle client heartbeat/ping
            if data.strip().lower() == "ping":
                await ws_manager.send_to_client(
                    client_id,
                    {"type": "pong", "timestamp": "ok"},
                )
            else:
                logger.info(f"Received message from admin client {client_id}: {data}")
    except WebSocketDisconnect:
        logger.info(f"Admin client {client_id} disconnected from {channel}")
    except Exception as e:
        logger.error(f"Error in admin orders WebSocket for client {client_id}: {e}")
    finally:
        await ws_manager.disconnect(client_id)


@router.websocket("/ws/admin/all")
async def websocket_admin_all_updates(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for comprehensive admin updates.

    Admins connect to this endpoint to receive all real-time updates
    including new orders, order status changes, and system events.

    Args:
        websocket: The FastAPI WebSocket connection.
    """
    client_id = str(uuid.uuid4())
    channel = "admin:all"

    await ws_manager.connect(websocket, client_id, channel)

    try:
        # Send initial connection confirmation
        await ws_manager.send_to_client(
            client_id,
            {
                "type": "connection_established",
                "client_id": client_id,
                "channel": channel,
                "message": "Subscribed to all admin updates",
            },
        )

        while True:
            # Receive messages from client (e.g., ping/heartbeat)
            data = await websocket.receive_text()

            # Handle client heartbeat/ping
            if data.strip().lower() == "ping":
                await ws_manager.send_to_client(
                    client_id,
                    {"type": "pong", "timestamp": "ok"},
                )
            else:
                logger.info(f"Received message from admin client {client_id}: {data}")
    except WebSocketDisconnect:
        logger.info(f"Admin all-updates client {client_id} disconnected from {channel}")
    except Exception as e:
        logger.error(f"Error in admin all-updates WebSocket for client {client_id}: {e}")
    finally:
        await ws_manager.disconnect(client_id)


def broadcast_order_status_update(order_id: str, status: str, data: Dict[str, Any]) -> None:
    """
    Broadcast an order status update to all clients subscribed to that order.

    This function is called by order processing logic to push real-time
    updates to connected clients.

    Args:
        order_id: The unique order identifier.
        status: The new order status (e.g., 'preparing', 'ready', 'delivered').
        data: Additional order data to include in the update.
    """
    channel = f"order:{order_id}"
    message: Dict[str, Any] = {
        "type": "order_status_update",
        "order_id": order_id,
        "status": status,
        "data": data,
    }
    ws_manager.broadcast_to_channel(channel, message)
    logger.info(f"Broadcasted order status update: order={order_id}, status={status}")


def broadcast_new_order(order_data: Dict[str, Any]) -> None:
    """
    Broadcast a new order notification to all admin clients.

    This function is called when a new order is placed to notify
    restaurant staff in real-time.

    Args:
        order_data: The complete order data including items, total, etc.
    """
    message: Dict[str, Any] = {
        "type": "new_order",
        "data": order_data,
    }
    # Notify admin:orders channel
    ws_manager.broadcast_to_channel("admin:orders", message)
    # Also notify admin:all channel
    ws_manager.broadcast_to_channel("admin:all", message)
    logger.info(f"Broadcasted new order notification: order_id={order_data.get('id')}")


def broadcast_order_update(order_id: str, update_type: str, data: Dict[str, Any]) -> None:
    """
    Broadcast a general order update to admin channels.

    Used for any order-related updates that admins should be notified about,
    such as cancellations, modifications, or delivery confirmations.

    Args:
        order_id: The unique order identifier.
        update_type: The type of update (e.g., 'cancelled', 'modified', 'delivered').
        data: Additional update data.
    """
    message: Dict[str, Any] = {
        "type": f"order_{update_type}",
        "order_id": order_id,
        "data": data,
    }
    # Notify admin:all channel
    ws_manager.broadcast_to_channel("admin:all", message)
    logger.info(f"Broadcasted order update: order={order_id}, type={update_type}")
