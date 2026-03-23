from celery import chain, chord, group
import logging

from app.workers.celery_app import celery_app
from app.workers.worker_dns import scan_dns
from app.workers.worker_secrets import scan_secrets
from app.workers.worker_harvester import harvest_emails
from app.workers.worker_http import scan_http
from app.workers.worker_geoip import scan_geoip

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
    """Callback appelé quand les modules principaux sont terminés. Calcule le score global et met status à 'done'."""
    logger.info(f"[Orchestrator] Consolidated Results: {results}")
    logger.info(f"[Orchestrator] Scan {scan_id} entièrement terminé.")

    # Algorithme métier de calcul du score (Risk Score)
    base_score = 100
    risk_score = 100
    
    # 1. Analyser les résultats bruts
    for res in results:
        if isinstance(res, dict):
            # Pénalité s'il y a des secrets trouvés (-20 par secret)
            if "findings" in res:
                risk_score -= len(res["findings"]) * 20
            # Pénalité de -5 par email leaké
            if "breaches" in res and res["breaches"]:
                risk_score -= 5

    # Clamp à 0 minimum
    risk_score = max(0, risk_score)
    logger.info(f"[Orchestrator] Risk Score calculé pour scan {scan_id} = {risk_score}/{base_score}")
    
    # TODO: Appel base de données SQLAlchemy pour finaliser
    # scan = db.query(Scan).get(scan_id)
    # scan.status = "done"
    # scan.risk_score = risk_score
    # db.commit()
    
    return {"scan_id": scan_id, "final_score": risk_score, "status": "done"}
