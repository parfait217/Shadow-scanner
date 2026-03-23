from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json, client
from app.workers.worker_cve import scan_cve
from app.workers.worker_geoip import scan_geoip
from app.core.config import settings

import asyncio
import logging
import socket

logger = logging.getLogger(__name__)

async def _resolve_ip(hostname: str) -> str:
    """Résolution DNS locale asynchrone pour obtenir l'IP (A record) basique."""
    loop = asyncio.get_event_loop()
    try:
        # Utiliser gethostbyname de manière non bloquante dans un thread
        ip = await loop.run_in_executor(None, socket.gethostbyname, hostname)
        return ip
    except Exception:
        return None

async def _shodan_fallback_scan(ip: str):
    """
    Tente d'utiliser la clé Shodan, sinon renvoie un dict vide.
    Permet la découverte tierce des ports, vulns et technos attachées.
    """
    if not settings.SHODAN_API_KEY:
        logger.debug(f"[Shodan] Clé API absente. Skip pour {ip}.")
        return None
        
    url = f"https://api.shodan.io/shodan/host/{ip}?key={settings.SHODAN_API_KEY}"
    data = await fetch_json(url)
    return data

@celery_app.task(bind=True, max_retries=3)
def scan_http(self, scan_id: str, asset_id: str, target: str):
    """
    Détection HTTP(s) et bannières, et orchestration de GeoIP et CVE si découverte.
    `target` = nom de domaine (ex: dev.example.com).
    """
    logger.info(f"[HTTP Worker] Scan de {target} (Asset: {asset_id})")
    
    async def logic():
        # 1. Résolution de base
        ip = await _resolve_ip(target)
        if not ip:
            logger.info(f"[HTTP Worker] Résolution impossible pour {target}.")
            return {"alive": False}
            
        logger.info(f"[HTTP Worker] {target} -> {ip}")
        
        # 1.5 Lancement asynchrone immédiat du GeoIP sachant l'IP
        scan_geoip.delay(scan_id, asset_id, ip)
        
        # 2. Shodan (Richesses) si présent
        shodan_data = await _shodan_fallback_scan(ip)
        if shodan_data:
            ports = shodan_data.get("ports", [])
            logger.info(f"[HTTP Worker] Shodan a trouvé {len(ports)} ports pour {ip}")
            # Si d'autres infos dispo, on délègue:
            for port in ports:
                # ex: appel scan_cve si on identifie un produit dans les CPEs shodan
                pass
                
        # 3. Validation HTTP maison basique (si pas de shodan ou pour compléter)
        # Port 80 et 443
        headers_found = {}
        for scheme in ["http", "https"]:
            url = f"{scheme}://{target}"
            try:
                # Check HTTP (max 5 sec)
                resp = await client.get(url, timeout=5.0, verify=False, follow_redirects=False)
                headers_found[scheme] = dict(resp.headers)
            except Exception as e:
                pass
                
        # TODO: Sauvegarder dans Service Repositories
        
        return {"ip": ip, "http_headers": headers_found}

    try:
        return asyncio.run(logic())
    except Exception as e:
        logger.error(f"[HTTP Worker] Erreur asynchrone: {e}")
        return {"alive": False}
