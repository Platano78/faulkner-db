import asyncio
import json
import websockets
import logging
from typing import Dict, Any, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        
    async def register_client(self, websocket):
        self.connected_clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.connected_clients)}")
        try:
            await websocket.wait_closed()
        finally:
            self.connected_clients.remove(websocket)
            logger.info(f"Client disconnected. Total clients: {len(self.connected_clients)}")

    async def broadcast_message(self, message: str):
        if not self.connected_clients:
            return
        await asyncio.gather(
            *[client.send(message) for client in self.connected_clients],
            return_exceptions=True
        )

    async def broadcast_update(self, update_type: str, data: Dict[Any, Any]):
        message = json.dumps({"type": update_type, "data": data})
        await self.broadcast_message(message)

ws_manager = WebSocketManager()

async def handle_connection(websocket, path):
    if path == "/ws":
        await ws_manager.register_client(websocket)
    else:
        await websocket.close()

def notify_decision_added(decision_data):
    asyncio.create_task(ws_manager.broadcast_update("decision_added", decision_data))

def notify_decision_updated(update_data):
    asyncio.create_task(ws_manager.broadcast_update("decision_updated", update_data))

def notify_gap_detected(gap_data):
    asyncio.create_task(ws_manager.broadcast_update("gap_detected", gap_data))
