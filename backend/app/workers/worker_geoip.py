from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
from app.core.dependencies import get_worker_session
from app.models.asset import Asset
from sqlalchemy import update
import logging
import asyncio

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def scan_geoip(self, scan_id: str, asset_id: str, target_ip: str):
    """
    Géolocalisation et attribution ASN de l'IP découverte.
    """
    logger.info(f"[GeoIP Worker] Recherche de {target_ip} pour l'asset {asset_id}")
    
    async def fetch():
        # ip-api.com autorise 45 requêtes par minute gratuitement sans clé
        url = f"http://ip-api.com/json/{target_ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        data = await fetch_json(url)
        return data

    try:
        geoip_data = asyncio.run(fetch())
    except Exception as e:
        logger.error(f"[GeoIP Worker] Erreur: {e}")
        return None

    if geoip_data and geoip_data.get("status") == "success":
        async def save():
            async with get_worker_session() as session:
                import uuid
                await session.execute(
                    update(Asset).where(Asset.id == uuid.UUID(asset_id)).values(
                        country=geoip_data.get("country"),
                        isp=geoip_data.get("isp"),
                        asn=str(geoip_data.get("as"))[:100] if geoip_data.get("as") else None
                    )
                )
                await session.commit()
        
        try:
            asyncio.run(save())
            logger.info(f"[GeoIP Worker] Mis à jour pour {target_ip}: {geoip_data.get('country')}")
        except Exception as e:
            logger.error(f"[GeoIP Worker] Erreur Save: {e}")
            
        return geoip_data
        
    return None
