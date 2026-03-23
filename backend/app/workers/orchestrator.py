from celery import chain, chord, group
import logging
import asyncio
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.workers.worker_dns import scan_dns
from app.workers.worker_secrets import scan_secrets
from app.workers.worker_harvester import harvest_emails
from app.workers.worker_http import scan_http
from app.workers.worker_geoip import scan_geoip
from app.core.dependencies import AsyncSessionLocal
from app.models.scan import Scan
from sqlalchemy import update

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def run_project_scan(self, scan_id: str, project_id: str, root_domain: str):
    """
    Lance le pipeline de scan complet pour un projet.
    C'est la porte d'entrée asynchrone absolue.
    """
    logger.info(f"[Orchestrator] Démarrage du scan {scan_id} pour le domaine {root_domain}")

    # ===== ETAPE 1 : Découverte (Sous-domaines, OSINT global, Secrets GitHub) ===== #
    # Ces tâches peuvent être lancées en parallèle car elles ne dépendent pas l'une de l'autre
    discovery_group = group(
        scan_dns.s(scan_id, root_domain),
        harvest_emails.s(scan_id, root_domain),
        scan_secrets.s(scan_id, root_domain)
    )

    # L'exécution chord() garantit que finalize_scan est appelé
    # une fois que la découverte (DNS, Mails, Secrets) est terminée.
    # Note: comme DNS lance d'autres tâches (HTTP, GeoIP), la véritable
    # consolidation demanderait un workflow Celery plus avancé (canvas complexe),
    # mais pour cette Phase 2 le chord principal suffit comme garantie de base.
    chord(discovery_group)(finalize_scan.s(scan_id))
    
    return f"Scan {scan_id} Pipeline Started"


@celery_app.task(bind=True)
def finalize_scan(self, results, scan_id: str):
    """Callback appelé quand les modules principaux sont terminés."""
    logger.info(f"[Orchestrator] Scan {scan_id} terminant sa phase de collecte.")

    # Calcul simple du score
    risk_score = 100
    for res in results:
        if isinstance(res, dict):
            if "findings_count" in res:
                risk_score -= res["findings_count"] * 10
            if "breaches_count" in res:
                risk_score -= res["breaches_count"] * 5
    
    risk_score = max(0, risk_score)

    async def _update_db():
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(
                    status="completed",
                    risk_score=risk_score,
                    finished_at=datetime.now(timezone.utc)
                )
            )
            await session.commit()
    
    try:
        asyncio.run(_update_db())
        logger.info(f"[Orchestrator] Scan {scan_id} finalisé avec score {risk_score}.")
    except Exception as e:
        logger.error(f"[Orchestrator] Erreur de finalisation DB: {e}")

    return {"scan_id": scan_id, "final_score": risk_score, "status": "completed"}
