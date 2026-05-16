from app.workers.celery_app import celery_app
from app.core.dependencies import get_worker_session
from app.repositories.breach_repository import BreachRepository
from app.models.breach import Breach
from app.models.employee import Employee
from app.core.config import settings
from app.utils.redis_pub import publish_scan_update
from datetime import datetime
import httpx
import logging
import asyncio
import uuid
from typing import List, Dict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ShadowScanner/1.0; Security Research Tool)"
}


async def _check_leakcheck(email: str) -> List[Dict]:
    """API publique LeakCheck.io — sans clé."""
    breaches = []
    url = f"https://leakcheck.io/api/public?check={email}"
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("found", 0) > 0:
                    for source in data.get("sources", []):
                        breaches.append({
                            "breach_name": source.get("name", "Unknown Source"),
                            "date": source.get("date"),
                            "data_types": source.get("fields", "Email, Password"),
                        })
                    logger.info(f"[Breach] LeakCheck: {len(breaches)} fuites pour {email}")
    except Exception as e:
        logger.warning(f"[Breach] LeakCheck erreur: {e}")
    return breaches


async def _check_proxynova_comb(email: str) -> List[Dict]:
    """API ProxyNova COMB — base de 3.2Mrd credentials, sans clé."""
    breaches = []
    url = f"https://api.proxynova.com/comb?email={email}"
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                count = data.get("count", 0)
                if count > 0:
                    breaches.append({
                        "breach_name": f"COMB (Collection of Many Breaches) — {count} entrée(s)",
                        "date": "2021-02-01",
                        "data_types": "Email, Password Hash",
                    })
                    logger.info(f"[Breach] ProxyNova COMB: {count} entrées pour {email}")
    except Exception as e:
        logger.warning(f"[Breach] ProxyNova COMB erreur: {e}")
    return breaches


async def _check_hibp(email: str, api_key: str) -> List[Dict]:
    """Have I Been Pwned — nécessite une clé API payante."""
    breaches = []
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"
    headers = {**HEADERS, "hibp-api-key": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                for b in resp.json():
                    classes = b.get("DataClasses", [])
                    breaches.append({
                        "breach_name": b.get("Name", "Unknown"),
                        "date": b.get("BreachDate"),
                        "data_types": ", ".join(classes) if isinstance(classes, list) else str(classes),
                    })
                logger.info(f"[Breach] HIBP: {len(breaches)} fuites pour {email}")
    except Exception as e:
        logger.warning(f"[Breach] HIBP erreur: {e}")
    return breaches


@celery_app.task(bind=True, max_retries=1, rate_limit='10/m')
def check_breach(self, scan_id: str, employee_id: str, email: str):
    """
    Vérifie les fuites de données pour un email via :
    1. HIBP si clé disponible
    2. LeakCheck.io (public, gratuit)
    3. ProxyNova COMB (gratuit, 3.2Mrd credentials)
    """
    logger.info(f"[Breach Worker] Vérification des fuites pour {email}")

    async def _run():
        # Collecte des fuites
        all_breaches = []
        if settings.HIBP_API_KEY:
            all_breaches = await _check_hibp(email, settings.HIBP_API_KEY)
        else:
            results = await asyncio.gather(
                _check_leakcheck(email),
                _check_proxynova_comb(email),
                return_exceptions=True
            )
            for r in results:
                if isinstance(r, list):
                    all_breaches.extend(r)

        if not all_breaches:
            logger.info(f"[Breach Worker] Aucune fuite pour {email}.")
            return {"email": email, "breaches_count": 0}

        # Persistance — même boucle asyncio
        emp_uuid = uuid.UUID(employee_id)
        async with get_worker_session() as session:
            repo = BreachRepository(session)
            for b_data in all_breaches:
                date_str = b_data.get("date")
                b_date = None
                if date_str:
                    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
                        try:
                            b_date = datetime.strptime(str(date_str)[:10], fmt)
                            break
                        except ValueError:
                            continue

                breach = Breach(
                    id=uuid.uuid4(),
                    employee_id=emp_uuid,
                    breach_name=b_data.get("breach_name", "Unknown"),
                    date=b_date,
                    data_types=str(b_data.get("data_types", ""))[:500]
                )
                await repo.create(breach)

            # Mettre à jour le compteur sur l'employé
            from sqlalchemy import update
            await session.execute(
                update(Employee)
                .where(Employee.id == emp_uuid)
                .values(breach_count=len(all_breaches))
            )
            await session.commit()
            
            # Notifier le frontend
            await publish_scan_update(scan_id, "REFRESH", {"type": "breaches", "count": len(all_breaches)})

        logger.info(f"[Breach Worker] {len(all_breaches)} fuite(s) persistée(s) pour {email}.")
        return {"email": email, "breaches_count": len(all_breaches)}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[Breach Worker] Erreur critique: {e}")
        return {"breaches": [], "error": str(e)}
