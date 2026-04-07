from app.workers.celery_app import celery_app
from app.workers.worker_breach import check_breach
from app.core.dependencies import get_worker_session
from app.repositories.employee_repository import EmployeeRepository
from app.models.employee import Employee
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def harvest_emails(self, scan_id: str, root_domain: str):
    """
    Recherche d'employés et adresses emails liés au domaine.
    Dans un vrai scénario, on appellerait Hunter.io ou TheHarvester.
    """
    logger.info(f"[Harvester Worker] Recherche OSINT pour {root_domain}")
    
    # Sans API tierce (ex: Hunter.io), la découverte purement OSINT des emails
    # demande des scrapers complexes (TheHarvester). 
    # Pour l'instant, on s'en tient à des résultats 100% réels : liste vide s'il n'y a pas d'intégration.
    found_emails = []
    
    logger.info(f"[Harvester Worker] {len(found_emails)} emails trouvés.")

    async def _save_and_launch():
        scan_uuid = uuid.UUID(scan_id)
        async with get_worker_session() as session:
            repo = EmployeeRepository(session)
            
            for email in found_emails:
                existing = await repo.get_by_email_and_scan(email, scan_uuid)
                employee_id = str(existing.id) if existing else str(uuid.uuid4())
                
                if not existing:
                    emp = Employee(id=uuid.UUID(employee_id), scan_id=scan_uuid, email=email)
                    await repo.create(emp)
                    
                check_breach.delay(scan_id, employee_id, email)
                
            await session.commit()

    asyncio.run(_save_and_launch())
        
    return {"emails": found_emails}

