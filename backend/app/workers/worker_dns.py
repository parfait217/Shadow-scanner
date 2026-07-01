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
import re
import httpx
from typing import Set, List
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# ============================================================
# Wordlist de brute-force DNS (sous-domaines courants)
# ============================================================
SUBDOMAIN_WORDLIST = [
    "www", "mail", "ftp", "smtp", "pop", "ns1", "ns2", "webmail", "admin",
    "api", "api2", "app", "dev", "staging", "stage", "test", "beta", "demo",
    "portal", "dashboard", "panel", "manage", "management", "control",
    "vpn", "remote", "ssh", "rdp", "citrix", "pulse", "secure",
    "auth", "login", "sso", "oauth", "accounts", "id",
    "shop", "store", "pay", "payment", "checkout", "billing", "invoice",
    "blog", "news", "forum", "community", "docs", "help", "support", "kb",
    "cdn", "static", "assets", "media", "img", "images", "upload", "files",
    "cloud", "storage", "backup", "archive", "data",
    "git", "gitlab", "github", "repo", "ci", "cd", "jenkins", "jira",
    "confluence", "wiki", "intranet", "internal",
    "monitoring", "metrics", "grafana", "kibana", "elastic", "logs",
    "db", "database", "mysql", "postgres", "redis", "mongo",
    "sandbox", "uat", "qa", "preprod", "pre-prod", "production", "prod",
    "v1", "v2", "v3", "old", "legacy", "new", "next",
    "status", "healthcheck", "ping", "check",
    "smtp", "pop3", "imap", "exchange", "webdav", "caldav",
    "mobile", "m", "wap", "android", "ios",
    "download", "downloads", "update", "updates", "patch",
    "crm", "erp", "hr", "finance", "accounting",
    "proxy", "gateway", "lb", "loadbalancer", "ha", "cluster",
    "web", "web1", "web2", "server", "server1", "server2",
    "fw", "firewall", "dmz", "edge", "border",
    "video", "stream", "live", "meet", "conference", "webrtc",
    "autodiscover", "autoconfig", "outlook", "teams", "slack",
]


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
            sub = sub.strip().lower().lstrip("*.")
            if sub.endswith(domain) and sub != domain:
                subdomains.add(sub)
    logger.info(f"[DNS Worker] crt.sh: {len(subdomains)} sous-domaines trouvés")
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
            if sub.endswith(domain) and sub != domain:
                subdomains.add(sub)
    logger.info(f"[DNS Worker] HackerTarget: {len(subdomains)} sous-domaines trouvés")
    return subdomains


async def _fetch_dnsdumpster(domain: str) -> Set[str]:
    """
    Scrape DNSDumpster pour la reconnaissance passive.
    DNSDumpster agrège des données DNS historiques massives.
    """
    subdomains = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://dnsdumpster.com/",
        "Origin": "https://dnsdumpster.com",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False, headers=headers) as client:
            # 1. Obtenir le token CSRF
            r = await client.get("https://dnsdumpster.com/")
            csrf_token = ""
            match = re.search(r"csrfmiddlewaretoken.*?value=['\"]([^'\"]+)['\"]", r.text)
            if match:
                csrf_token = match.group(1)
            if not csrf_token:
                # fallback: chercher dans le cookie
                csrf_token = r.cookies.get("csrftoken", "")

            if not csrf_token:
                logger.debug("[DNS Worker] DNSDumpster: token CSRF non trouvé")
                return subdomains

            # 2. Soumettre la requête de recherche
            resp = await client.post(
                "https://dnsdumpster.com/",
                data={"csrfmiddlewaretoken": csrf_token, "targetip": domain, "user": "free"},
                cookies={"csrftoken": csrf_token},
            )

            # 3. Extraire les sous-domaines du HTML
            found = re.findall(
                rf"([\w\.\-]+\.{re.escape(domain)})", resp.text
            )
            for sub in found:
                sub = sub.strip().lower()
                if sub.endswith(domain) and sub != domain:
                    subdomains.add(sub)

    except Exception as e:
        logger.debug(f"[DNS Worker] DNSDumpster erreur: {e}")

    logger.info(f"[DNS Worker] DNSDumpster: {len(subdomains)} sous-domaines trouvés")
    return subdomains


async def _brute_force_subdomains(domain: str) -> Set[str]:
    """
    Brute-force DNS intelligent avec une wordlist de 100+ termes courants.
    Résout chaque candidat en parallèle (semaphore de 50 résolutions simultanées).
    """
    found = set()
    sem = asyncio.Semaphore(50)

    async def _check(word: str):
        candidate = f"{word}.{domain}"
        async with sem:
            try:
                resolver = dns.asyncresolver.Resolver()
                resolver.timeout = 1.5
                resolver.lifetime = 1.5
                await resolver.resolve(candidate, "A")
                found.add(candidate)
                logger.debug(f"[DNS Brute] ✓ {candidate}")
            except Exception:
                pass

    await asyncio.gather(*[_check(w) for w in SUBDOMAIN_WORDLIST], return_exceptions=True)
    logger.info(f"[DNS Worker] Brute-force: {len(found)} sous-domaines confirmés")
    return found


async def _fetch_shodan_internetdb(ip: str) -> dict:
    """
    Interroge Shodan InternetDB (GRATUIT, sans clé API).
    Retourne les ports ouverts, les CVEs et les tags de sécurité déjà scannés par Shodan.
    """
    try:
        data = await fetch_json(f"https://internetdb.shodan.io/{ip}")
        if data and not data.get("detail"):
            return data
    except Exception as e:
        logger.debug(f"[DNS Worker] Shodan InternetDB erreur pour {ip}: {e}")
    return {}


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
    Découverte de sous-domaines TURBOBOOSTÉE via :
    - crt.sh (certificats SSL)
    - HackerTarget
    - DNSDumpster (historique DNS massif)
    - Brute-force intelligent (100+ mots-clés)
    + Enrichissement Shodan InternetDB pour chaque IP trouvée.
    """
    logger.info(f"[DNS Worker] Scan {scan_id} pour {target_domain}")

    async def _run():
        # 1. Énumération passive en parallèle (4 sources simultanées)
        results = await asyncio.gather(
            _fetch_crt_sh(target_domain),
            _fetch_hackertarget(target_domain),
            _fetch_dnsdumpster(target_domain),
            _brute_force_subdomains(target_domain),
            return_exceptions=True
        )
        found_subdomains = set()
        for r in results:
            if isinstance(r, set):
                found_subdomains.update(r)
        found_subdomains.add(target_domain)

        logger.info(f"[DNS Worker] TOTAL: {len(found_subdomains)} sous-domaines identifiés pour {target_domain}.")

        # 2. Résolution IP + Persistence — même boucle asyncio
        async with get_worker_session() as session:
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(status="running")
            )
            await session.commit()

            http_tasks = []
            current_count = 0

            for sub in found_subdomains:
                ip = await _resolve_dns(sub)

                # Enrichissement Shodan InternetDB si l'IP est connue
                shodan_data = {}
                if ip:
                    shodan_data = await _fetch_shodan_internetdb(ip)

                asset = Asset(
                    id=uuid.uuid4(),
                    scan_id=scan_id,
                    type="subdomain",
                    value=sub,
                    ip=ip,
                    is_alive=bool(ip),
                    # Stocker les ports Shodan dans le champ ASN pour info (temporaire)
                    asn=f"Shodan ports: {shodan_data.get('ports', [])}" if shodan_data.get('ports') else None
                )
                session.add(asset)
                current_count += 1

                # Commit intermédiaire par lot de 10 pour voir la progression
                if current_count % 10 == 0:
                    await session.execute(
                        update(Scan).where(Scan.id == scan_id).values(assets_count=current_count)
                    )
                    await session.commit()
                    await publish_scan_update(scan_id, "REFRESH", {"type": "assets", "count": current_count})

                if ip:
                    http_tasks.append(scan_http.s(scan_id, str(asset.id), sub, ip, shodan_data))

            # Commit final
            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(assets_count=current_count)
            )
            await session.commit()

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
