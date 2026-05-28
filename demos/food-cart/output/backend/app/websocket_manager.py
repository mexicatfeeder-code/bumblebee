"""
WebSocket manager for the Food Cart backend.

Handles multiple WebSocket clients, message broadcasting,
and reconnection logic for real-time order updates.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketConnection:
    """Represents a single WebSocket client connection."""

    def __init__(self, websocket: WebSocket, client_id: str, channel: str = "default"):
        """
        Initialize a WebSocket connection.

        Args:
            websocket: The FastAPI WebSocket instance.
            client_id: Unique identifier for this client.
            channel: The channel/topic this client is subscribed to.
        """
        self.websocket = websocket
        self.client_id = client_id
        self.channel = channel
        self.is_connected = True
        self.last_heartbeat: Optional[float] = None

    async def send_json(self, data: Dict[str, Any]) -> None:
        """
        Send JSON data to this client.

        Args:
            data: Dictionary to serialize and send.
        """
        try:
            if self.is_connected:
                await self.websocket.send_json(data)
        except WebSocketDisconnect:
            self.is_connected = False
            logger.info(f"Client {self.client_id} disconnected during send.")
        except Exception as e:
            self.is_connected = False
            logger.error(f"Error sending to client {self.client_id}: {e}")

    async def send_text(self, text: str) -> None:
        """
        Send raw text to this client.

        Args:
            text: String to send.
        """
        try:
            if self.is_connected:
                await self.websocket.send_text(text)
        except WebSocketDisconnect:
            self.is_connected = False
            logger.info(f"Client {self.client_id} disconnected during send.")
        except Exception as e:
            self.is_connected = False
            logger.error(f"Error sending to client {self.client_id}: {e}")


class WebSocketManager:
    """
    Manages WebSocket connections for the Food Cart application.

    Supports multiple clients, channel-based subscriptions,
    message broadcasting, and reconnection handling.
    """

    def __init__(self):
        """Initialize the WebSocket manager with empty connection stores."""
        # Map of client_id -> WebSocketConnection
        self.active_connections: Dict[str, WebSocketConnection] = {}
        # Map of channel -> set of client_ids subscribed to that channel
        self.channels: Dict[str, Set[str]] = {}
        # Track reconnection attempts per client
        self.reconnection_tokens: Dict[str, str] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "default") -> str:
        """
        Accept a new WebSocket connection and register the client.

        Args:
            websocket: The FastAPI WebSocket instance to accept.
            channel: The channel to subscribe the client to.

        Returns:
            str: The unique client_id assigned to this connection.
        """
        await websocket.accept()
        client_id = str(uuid.uuid4())

        # Check if this client has a reconnection token
        reconnection_token = None
        for token, cid in list(self.reconnection_tokens.items()):
            if cid == client_id:
                reconnection_token = token
                break

        connection = WebSocketConnection(websocket, client_id, channel)
        self.active_connections[client_id] = connection

        # Subscribe to channel
        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(client_id)

        # Store reconnection token
        if reconnection_token is None:
            reconnection_token = str(uuid.uuid4())
        self.reconnection_tokens[reconnection_token] = client_id

        # Send connection confirmation
        await connection.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "channel": channel,
            "reconnection_token": reconnection_token,
        })

        logger.info(
            f"Client {client_id} connected on channel '{channel}'. "
            f"Total active: {len(self.active_connections)}"
        )

        return client_id

    async def disconnect(self, client_id: str) -> None:
        """
        Handle client disconnection and cleanup.

        Removes the client from active connections and all channels.
        Preserves the reconnection token for potential reconnection.

        Args:
            client_id: The unique identifier of the disconnecting client.
        """
        async with self._lock:
            connection = self.active_connections.pop(client_id, None)
            if connection:
                connection.is_connected = False

                # Remove from all channels
                for channel, clients in self.channels.items():
                    clients.discard(client_id)
                    # Clean up empty channels
                    if not clients:
                        del self.channels[channel]

                logger.info(
                    f"Client {client_id} disconnected. "
                    f"Total active: {len(self.active_connections)}"
                )

    async def broadcast(
        self,
        message: Dict[str, Any],
        channel: Optional[str] = None,
        exclude_client: Optional[str] = None,
    ) -> int:
        """
        Broadcast a message to all clients on a channel (or all channels).

        Args:
            message: The message dictionary to broadcast.
            channel: If provided, only send to clients on this channel.
                     If None, send to all clients on all channels.
            exclude_client: Client ID to exclude from the broadcast.

        Returns:
            int: Number of clients the message was sent to.
        """
        sent_count = 0
        target_clients: Set[str] = set()

        if channel:
            target_clients = self.channels.get(channel, set()).copy()
        else:
            target_clients = set(self.active_connections.keys())

        if exclude_client:
            target_clients.discard(exclude_client)

        # Send to all target clients concurrently
        send_tasks = []
        for client_id in target_clients:
            connection = self.active_connections.get(client_id)
            if connection and connection.is_connected:
                send_tasks.append(connection.send_json(message))

        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            sent_count = sum(1 for r in results if not isinstance(r, Exception))

        logger.debug(
            f"Broadcast on channel '{channel or 'all'}': "
            f"sent to {sent_count}/{len(target_clients)} clients"
        )

        return sent_count

    async def send_to_client(
        self, client_id: str, message: Dict[str, Any]
    ) -> bool:
        """
        Send a message to a specific client.

        Args:
            client_id: The target client's unique identifier.
            message: The message dictionary to send.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        connection = self.active_connections.get(client_id)
        if connection and connection.is_connected:
            await connection.send_json(message)
            return True
        return False

    async def subscribe_to_channel(
        self, client_id: str, channel: str
    ) -> bool:
        """
        Subscribe a client to an additional channel.

        Args:
            client_id: The client to subscribe.
            channel: The channel to subscribe to.

        Returns:
            bool: True if subscription was successful.
        """
        connection = self.active_connections.get(client_id)
        if not connection:
            return False

        if channel not in self.channels:
            self.channels[channel] = set()

        # Remove from old channel and add to new
        old_channel = connection.channel
        if old_channel in self.channels:
            self.channels[old_channel].discard(client_id)
            if not self.channels[old_channel]:
                del self.channels[old_channel]

        connection.channel = channel
        self.channels[channel].add(client_id)

        await connection.send_json({
            "type": "channel_subscribed",
            "channel": channel,
        })

        logger.info(f"Client {client_id} subscribed to channel '{channel}'")
        return True

    async def handle_reconnection(
        self, websocket: WebSocket, reconnection_token: str, channel: str = "default"
    ) -> Optional[str]:
        """
        Handle a client reconnection using a stored token.

        Validates the reconnection token and establishes a new connection
        for the client, preserving their identity.

        Args:
            websocket: The FastAPI WebSocket instance.
            reconnection_token: The token issued during the original connection.
            channel: The channel to reconnect on.

        Returns:
            str: The client_id if reconnection was successful, None otherwise.
        """
        # Validate reconnection token
        if reconnection_token not in self.reconnection_tokens:
            await websocket.accept()
            await websocket.send_json({
                "type": "reconnection_failed",
                "reason": "Invalid or expired reconnection token",
            })
            await websocket.close()
            return None

        # Clean up old connection if it still exists
        old_client_id = self.reconnection_tokens[reconnection_token]
        if old_client_id in self.active_connections:
            await self.disconnect(old_client_id)

        # Establish new connection
        client_id = await self.connect(websocket, channel)

        # Update reconnection token mapping
        self.reconnection_tokens[reconnection_token] = client_id

        # Notify about reconnection
        await self.broadcast({
            "type": "client_reconnected",
            "client_id": client_id,
            "channel": channel,
        })

        logger.info(f"Client {client_id} reconnected with token {reconnection_token}")
        return client_id

    async def send_order_update(
        self,
        order_id: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Broadcast an order status update to all connected clients.

        Args:
            order_id: The ID of the order being updated.
            status: The new status of the order.
            details: Optional additional details about the update.

        Returns:
            int: Number of clients that received the update.
        """
        message: Dict[str, Any] = {
            "type": "order_update",
            "order_id": order_id,
            "status": status,
            "timestamp": asyncio.get_event_loop().time(),
        }
        if details:
            message["details"] = details

        return await self.broadcast(message)

    async def send_new_order_notification(
        self, order_data: Dict[str, Any]
    ) -> int:
        """
        Broadcast a new order notification to all connected clients.

        Args:
            order_data: The complete order data to broadcast.

        Returns:
            int: Number of clients that received the notification.
        """
        message: Dict[str, Any] = {
            "type": "new_order",
            "order": order_data,
            "timestamp": asyncio.get_event_loop().time(),
        }
        return await self.broadcast(message)

    def get_active_count(self) -> int:
        """
        Get the number of currently active connections.

        Returns:
            int: Number of active WebSocket connections.
        """
        return len(self.active_connections)

    def get_channel_clients(self, channel: str) -> Set[str]:
        """
        Get the set of client IDs subscribed to a channel.

        Args:
            channel: The channel name.

        Returns:
            Set[str]: Set of client IDs on the channel.
        """
        return self.channels.get(channel, set()).copy()

    async def cleanup_disconnected(self) -> int:
        """
        Remove all disconnected clients from the manager.

        Returns:
            int: Number of clients removed.
        """
        disconnected = [
            cid
            for cid, conn in self.active_connections.items()
            if not conn.is_connected
        ]
        for client_id in disconnected:
            await self.disconnect(client_id)
        logger.info(f"Cleaned up {len(disconnected)} disconnected clients")
        return len(disconnected)


# Singleton instance for the application
manager = WebSocketManager()
