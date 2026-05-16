from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
from app.core.dependencies import get_worker_session
from app.models.asset import Asset
from sqlalchemy import update
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def scan_geoip(self, scan_id: str, asset_id: str, target_ip: str):
    """
    Géolocalisation et attribution ASN de l'IP découverte.
    Utilise ip-api.com (45 requêtes/minute gratuitement).
    """
    logger.info(f"[GeoIP Worker] Recherche de {target_ip} pour l'asset {asset_id}")

    async def _run():
        """Une seule boucle asyncio pour fetch + save — évite les conflits d'event loop."""
        # 1. Fetch GeoIP
        url = (
            f"http://ip-api.com/json/{target_ip}"
            f"?fields=status,message,country,countryCode,region,regionName,"
            f"city,zip,lat,lon,timezone,isp,org,as,query"
        )
        geoip_data = await fetch_json(url)

        if not geoip_data or geoip_data.get("status") != "success":
            return None

        # 2. Save — même boucle, pas de deuxième asyncio.run()
        async with get_worker_session() as session:
            await session.execute(
                update(Asset).where(Asset.id == uuid.UUID(asset_id)).values(
                    country=geoip_data.get("country"),
                    isp=geoip_data.get("isp"),
                    asn=str(geoip_data.get("as"))[:100] if geoip_data.get("as") else None
                )
            )
            await session.commit()

        logger.info(f"[GeoIP Worker] Mis à jour pour {target_ip}: {geoip_data.get('country')}")
        return geoip_data

    try:
        result = asyncio.run(_run())
        return result if result else {"status": "no_data", "ip": target_ip}
    except Exception as e:
        logger.error(f"[GeoIP Worker] Erreur: {e}")
        self.retry(exc=e, countdown=30)
