import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def publish_scan_update(scan_id: str, event_type: str, data: dict = None):
    """
    Publie un événement sur Redis Pub/Sub pour informer les clients WebSocket via FastAPI.
    Utilise le scan_id pour trouver le project_id associé en base de données.
    """
    try:
        from app.core.dependencies import get_worker_session
        from app.models.scan import Scan
        import uuid
        import redis.asyncio as aioredis
        from sqlalchemy import select

        # Récupérer le project_id depuis la DB
        async with get_worker_session() as session:
            result = await session.execute(select(Scan.project_id).where(Scan.id == uuid.UUID(scan_id)))
            project_id_uuid = result.scalar()
            if not project_id_uuid:
                logger.error(f"Scan {scan_id} introuvable pour la publication Redis.")
                return
            project_id = str(project_id_uuid)

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        channel = f"scan_updates:{project_id}"
        message = {
            "event": event_type,
            "data": data or {},
            "scan_id": scan_id
        }
        await client.publish(channel, json.dumps(message))
        await client.close()
        logger.info(f"Événement {event_type} publié sur le canal {channel}")
    except Exception as e:
        logger.error(f"Erreur lors de la publication Redis: {e}")
