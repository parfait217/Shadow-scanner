from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio
import json
from app.core.config import settings
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.redis_client = None

    async def get_redis(self):
        if self.redis_client is None:
            self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self.redis_client

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
            # Démarrer un listener Redis en arrière-plan pour ce projet
            asyncio.create_task(self.listen_to_redis(project_id))
        self.active_connections[project_id].append(websocket)
        logger.info(f"Client connecté au WebSocket du projet {project_id}")

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        logger.info(f"Client déconnecté du WebSocket du projet {project_id}")

    async def broadcast_to_project(self, project_id: str, message: dict):
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Erreur d'envoi WebSocket: {e}")
                    self.disconnect(connection, project_id)

    async def listen_to_redis(self, project_id: str):
        """Écoute les messages Redis Pub/Sub pour un projet spécifique et les retransmet."""
        redis = await self.get_redis()
        pubsub = redis.pubsub()
        channel_name = f"scan_updates:{project_id}"
        await pubsub.subscribe(channel_name)
        
        logger.info(f"Abonnement Redis Pub/Sub démarré pour {channel_name}")
        
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        await self.broadcast_to_project(project_id, data)
                    except json.JSONDecodeError:
                        pass
                
                # Si plus de clients, on arrête de l'écouter pour économiser les ressources
                if project_id not in self.active_connections:
                    await pubsub.unsubscribe(channel_name)
                    break
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel_name)

manager = ConnectionManager()

@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await manager.connect(websocket, project_id)
    try:
        while True:
            # Maintenir la connexion ouverte (on peut recevoir des pings du client)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
