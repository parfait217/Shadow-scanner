from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json, fetch_text
from app.workers.worker_http import scan_http
from app.core.dependencies import get_worker_session
from app.models.asset import Asset
from app.models.scan import Scan
from app.utils.redis_pub import publish_scan_update

import asyncio
import dns.asyncresolver
import logging
import uuid
from typing import Set, List
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


async def _fetch_crt_sh(domain: str) -> Set[str]:
    """Interroge crt.sh pour trouver des sous-domaines dans les certificats SSL (Gratuit)."""
    subdomains = set()
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    data = await fetch_json(url)
    if not data:
        return subdomains
    for entry in data:
        name_value = entry.get("name_value", "")
        for sub in name_value.split("\n"):
            sub = sub.strip().lower()
            if sub.endswith(domain) and not sub.startswith("*"):
                subdomains.add(sub)
    return subdomains


async def _fetch_hackertarget(domain: str) -> Set[str]:
    """Interroge HackerTarget hostsearch (Gratuit, limité)."""
    subdomains = set()
    url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
    text = await fetch_text(url)
    if not text or "error" in text.lower():
        return subdomains
    for line in text.split("\n"):
        if "," in line:
            sub = line.split(",")[0].strip().lower()
            if sub.endswith(domain):
                subdomains.add(sub)
    return subdomains


async def _resolve_dns(domain: str) -> str:
    """Résout une adresse IPv4 pour un domaine donné."""
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = 2
        resolver.lifetime = 2
        answers = await resolver.resolve(domain, "A")
        if answers:
            return str(answers[0])
    except Exception:
        pass
    return None


@celery_app.task(bind=True, max_retries=3)
def scan_dns(self, scan_id: str, target_domain: str):
    """
    Découverte de sous-domaines via crt.sh + HackerTarget,
    résolution IP, et persistence dans PostgreSQL.
    Corrigé : une seule boucle asyncio pour tous les I/O.
    """
    logger.info(f"[DNS Worker] Scan {scan_id} pour {target_domain}")

    async def _run():
        # 1. Énumération passive (parallèle)
        results = await asyncio.gather(
            _fetch_crt_sh(target_domain),
            _fetch_hackertarget(target_domain),
            return_exceptions=True
        )
        found_subdomains = set()
        for r in results:
            if isinstance(r, set):
                found_subdomains.update(r)
        found_subdomains.add(target_domain)

        logger.info(f"[DNS Worker] {len(found_subdomains)} sous-domaines identifiés pour {target_domain}.")

        # 2. Résolution IP + Persistence — même boucle asyncio
        async with get_worker_session() as session:
            # Passer le scan en statut "running"
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(status="running")
            )
            await session.commit()

            http_tasks = []
            current_count = 0

            for sub in found_subdomains:
                ip = await _resolve_dns(sub)
                asset = Asset(
                    id=uuid.uuid4(),
                    scan_id=scan_id,
                    type="subdomain",
                    value=sub,
                    ip=ip,
                    is_alive=bool(ip)
                )
                session.add(asset)
                current_count += 1

                # Commit intermédiaire par lot de 10 pour voir la progression
                if current_count % 10 == 0:
                    await session.execute(
                        update(Scan).where(Scan.id == scan_id).values(assets_count=current_count)
                    )
                    await session.commit()

                if asset.is_alive:
                    http_tasks.append(scan_http.s(scan_id, str(asset.id), asset.value))

            # Commit final
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(assets_count=current_count)
            )
            await session.commit()
            
            # Notifier le frontend que de nouveaux actifs ont été découverts
            await publish_scan_update(scan_id, "REFRESH", {"type": "assets", "count": current_count})

            # 3. Lancer les scans HTTP en parallèle (tâches Celery séparées)
            if http_tasks:
                from celery import group
                group(http_tasks).apply_async()

        return len(found_subdomains)

    try:
        count = asyncio.run(_run())
        logger.info(f"[DNS Worker] Scan DNS terminé : {count} sous-domaines traités.")
        return {"status": "success", "subdomains_found": count}
    except Exception as e:
        logger.error(f"[DNS Worker] Échec critique: {e}")
        self.retry(exc=e, countdown=60)
