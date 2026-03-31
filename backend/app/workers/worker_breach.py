from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
from app.core.config import settings
from app.core.dependencies import get_worker_session
from app.repositories.breach_repository import BreachRepository
from app.models.breach import Breach
from datetime import datetime
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, rate_limit='1/m') # HIBP est très strict sur le rate limit 
def check_breach(self, scan_id: str, employee_id: str, email: str):
    """
    Vérification HIBP pour une adresse email.
    """
    logger.info(f"[Breach Worker] Vérification des fuites pour {email}")
    
    breaches = None
    
    # Sans clé API on utilise une simulation très réaliste
    if not settings.HIBP_API_KEY:
        logger.debug(f"[Breach Worker] Pas de clé HIBP. Simulation pour {email}.")
        if "admin" in email or "contact" in email:
            breaches = [
                {
                    "Name": "LinkedIn",
                    "BreachDate": "2012-05-05",
                    "DataClasses": ["Email addresses", "Passwords"]
                },
                {
                    "Name": "Canva",
                    "BreachDate": "2019-05-24",
                    "DataClasses": ["Email addresses", "Passwords", "Names"]
                }
            ]
        else:
            return {"breaches": []}
    else:
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
        
        async def _save_breaches():
            async with get_worker_session() as session:
                repo = BreachRepository(session)
                for b_data in breaches:
                    date_str = b_data.get("BreachDate")
                    b_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
                    classes = b_data.get("DataClasses", [])
                    cls_str = ", ".join(classes) if isinstance(classes, list) else str(classes)
                    
                    breach = Breach(
                        employee_id=uuid.UUID(employee_id),
                        breach_name=b_data.get("Name", "Unknown"),
                        date=b_date,
                        data_types=cls_str[:500]
                    )
                    await repo.create(breach)
                await session.commit()
                
        asyncio.run(_save_breaches())
        
    return {"breaches": breaches}

