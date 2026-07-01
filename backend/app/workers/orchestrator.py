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
from app.core.dependencies import get_worker_session
from app.models.scan import Scan
from sqlalchemy import update
from app.utils.redis_pub import publish_scan_update

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
    """
    Callback appelé quand les modules principaux sont terminés.
    Calcule un score de risque intelligent basé sur:
    - Les emails compromis dans des fuites (OSINT)
    - Les secrets exposés (fichiers .env, clés, etc.)
    - Le nombre de sous-domaines/actifs exposés (surface d'attaque)
    """
    logger.info(f"[Orchestrator] Scan {scan_id} terminant sa phase de collecte. Calcul du score de risque...")

    async def _compute_and_update():
        from sqlalchemy import select, func
        from app.models.asset import Asset
        from app.models.vulnerability import Vulnerability
        from app.models.employee import Employee
        from app.models.finding import Finding
        from app.models.service import Service

        async with get_worker_session() as session:
            # Récupérer les statistiques réelles du scan
            assets_count = (await session.execute(
                select(func.count()).select_from(Asset).where(Asset.scan_id == scan_id)
            )).scalar() or 0

            vulns_count = (await session.execute(
                select(func.count()).select_from(Vulnerability)
                .join(Service, Vulnerability.service_id == Service.id)
                .join(Asset, Service.asset_id == Asset.id)
                .where(Asset.scan_id == scan_id)
            )).scalar() or 0

            critical_vulns = (await session.execute(
                select(func.count()).select_from(Vulnerability)
                .join(Service, Vulnerability.service_id == Service.id)
                .join(Asset, Service.asset_id == Asset.id)
                .where(Asset.scan_id == scan_id, Vulnerability.severity.in_(["CRITICAL", "HIGH"]))
            )).scalar() or 0

            breaches_count = (await session.execute(
                select(func.count()).select_from(Employee)
                .where(Employee.scan_id == scan_id, Employee.breach_count > 0)
            )).scalar() or 0

            secrets_count = (await session.execute(
                select(func.count()).select_from(Finding)
                .join(Asset, Finding.asset_id == Asset.id)
                .where(Asset.scan_id == scan_id, Finding.type == "critical")
            )).scalar() or 0

            # =========================================================
            # Score de risque intelligent (100 = parfait, 0 = critique)
            # =========================================================
            risk_score = 100

            # Pénalité pour surface d'attaque large
            if assets_count > 50:
                risk_score -= 15
            elif assets_count > 20:
                risk_score -= 8
            elif assets_count > 5:
                risk_score -= 3

            # Pénalité pour vulnérabilités critiques/hautes
            risk_score -= min(40, critical_vulns * 8)

            # Pénalité pour vulnérabilités totales
            risk_score -= min(20, (vulns_count - critical_vulns) * 2)

            # Pénalité lourde pour secrets exposés (clés, .env, etc.)
            risk_score -= min(30, secrets_count * 15)

            # Pénalité pour employés compromis dans des fuites
            risk_score -= min(20, breaches_count * 5)

            risk_score = max(0, min(100, risk_score))

            logger.info(
                f"[Orchestrator] Score de risque: {risk_score}/100 "
                f"(assets={assets_count}, vulns={vulns_count}, critical={critical_vulns}, "
                f"breaches={breaches_count}, secrets={secrets_count})"
            )

            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(
                    status="completed",
                    risk_score=risk_score,
                    assets_count=assets_count,
                    vulns_count=vulns_count,
                    finished_at=datetime.now(timezone.utc)
                )
            )
            await session.commit()

            # Notifier le frontend que le scan est fini
            await publish_scan_update(scan_id, "REFRESH", {
                "type": "status",
                "status": "completed",
                "risk_score": risk_score,
                "stats": {
                    "assets": assets_count,
                    "vulns": vulns_count,
                    "critical_vulns": critical_vulns,
                    "breaches": breaches_count,
                    "secrets": secrets_count,
                }
            })

            return risk_score

    try:
        risk_score = asyncio.run(_compute_and_update())
        logger.info(f"[Orchestrator] Scan {scan_id} finalisé avec score {risk_score}.")
    except Exception as e:
        logger.error(f"[Orchestrator] Erreur de finalisation DB: {e}")
        risk_score = 50

    return {"scan_id": scan_id, "final_score": risk_score, "status": "completed"}
