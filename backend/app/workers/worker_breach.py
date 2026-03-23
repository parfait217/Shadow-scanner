from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, rate_limit='1/m') # HIBP est très strict sur le rate limit 
def check_breach(self, scan_id: str, employee_id: str, email: str):
    """
    Vérification HIBP pour une adresse email.
    """
    logger.info(f"[Breach Worker] Vérification des fuites pour {email}")
    
    # Sans clé API on utilise une simulation
    if not settings.HIBP_API_KEY:
        logger.debug(f"[Breach Worker] Pas de clé HIBP. Skip pour {email}.")
        return None
        
    async def fetch():
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        headers = {
            "hibp-api-key": settings.HIBP_API_KEY,
            "user-agent": "Shadow-Scanner-OSINT"
        }
        return await fetch_json(url, headers=headers)
        
    try:
        breaches = asyncio.run(fetch())
    except Exception as e:
        logger.error(f"[Breach Worker] Erreur API: {e}")
        return None
        
    if breaches:
        logger.info(f"[Breach Worker] {len(breaches)} fuites trouvées pour {email}.")
        # TODO: Sauvegarder dans BreachRepository
        
    return {"breaches": breaches}
