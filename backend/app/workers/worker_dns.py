from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json, fetch_text
from app.workers.worker_http import scan_http
# from app.workers.worker_geoip import scan_geoip  # À utiliser plus tard
from app.core.dependencies import AsyncSessionLocal
from app.models.asset import Asset
from app.models.scan import Scan

import asyncio
import dns.asyncresolver
import logging
import uuid
from typing import Set, List
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

async def _fetch_crt_sh(domain: str) -> Set[str]:
    """Interroge crt.sh pour trouver des sous-domaines dans les certificats (Gratuit)."""
    subdomains = set()
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    data = await fetch_json(url)
    if not data:
        return subdomains
        
    for entry in data:
        name_value = entry.get("name_value", "")
        # Gère les certificats "multidomaines" séparés par des retours chariot
        for sub in name_value.split("\n"):
            sub = sub.strip().lower()
            if sub.endswith(domain) and not sub.startswith("*"):
                subdomains.add(sub)
    return subdomains

async def _fetch_hackertarget(domain: str) -> Set[str]:
    """Interroge HackerTarget hostsearch (Gratuit, limité mais utile)."""
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
    Découverte de sous-domaines, résolution IP et persistence PostgreSQL.
    """
    logger.info(f"[DNS Worker] Scan {scan_id} pour {target_domain}")
    
    async def _run_scan():
        # 1. Énumération passive
        results = await asyncio.gather(
            _fetch_crt_sh(target_domain),
            _fetch_hackertarget(target_domain)
        )
        found_subdomains = set().union(*results)
        found_subdomains.add(target_domain)
        
        logger.info(f"[DNS Worker] {len(found_subdomains)} sous-domaines identifiés.")

        # 2. Résolution IP et Persistence
        async with AsyncSessionLocal() as session:
            # On passe le scan en statut "running"
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(status="running")
            )
            await session.commit()
            
            current_count = 0
            tasks = []
            
            for sub in found_subdomains:
                ip = await _resolve_dns(sub)
                asset = Asset(
                    id=uuid.uuid4(),
                    scan_id=scan_id,
                    type="subdomain",
                    value=sub,
                    ip=ip,
                    is_alive=True if ip else False
                )
                session.add(asset)
                current_count += 1
                
                # Commit par lots de 10 pour voir la progression
                if current_count % 10 == 0:
                    await session.execute(
                        update(Scan).where(Scan.id == scan_id).values(assets_count=current_count)
                    )
                    await session.commit()
                
                if asset.is_alive:
                    tasks.append(scan_http.s(scan_id, str(asset.id), asset.value))
            
            # Final commit pour le reste
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(assets_count=current_count)
            )
            await session.commit()
            
            # 3. Lancer les scans suivants (HTTP)
            if tasks:
                from celery import group
                group(tasks).apply_async()
            
        return len(found_subdomains)

    try:
        count = asyncio.run(_run_scan())
        return {"status": "success", "subdomains_found": count}
    except Exception as e:
        logger.error(f"[DNS Worker] Échec critique : {e}")
        self.retry(exc=e, countdown=60)
