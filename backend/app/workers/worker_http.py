from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
import httpx
from app.workers.worker_cve import scan_cve
from app.workers.worker_geoip import scan_geoip
from app.core.config import settings
from app.core.dependencies import get_worker_session
from app.models.service import Service

import asyncio
import logging
import socket
import uuid

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

async def _scan_port(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Vérifie si un port TCP est ouvert via asyncio."""
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

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
    Détection de services (Port Scan) et bannières HTTP.
    """
    logger.info(f"[Service Worker] Analyse de {target} (Asset: {asset_id})")
    
    ports_to_scan = [21, 22, 25, 53, 80, 111, 443, 445, 3306, 5432, 6379, 8080, 8443]

    async def logic():
        # 1. Résolution IP
        ip = await _resolve_ip(target)
        if not ip:
            return {"alive": False, "error": "DNS_FAIL"}
            
        # 1.5 Lancement asynchrone GeoIP
        scan_geoip.delay(scan_id, asset_id, ip)
        
        # 2. Scan de ports asynchrone (Concurrence de 10)
        sem = asyncio.Semaphore(10)
        async def _check(p):
            async with sem:
                is_open = await _scan_port(ip, p)
                return p if is_open else None
        
        open_ports = await asyncio.gather(*[_check(p) for p in ports_to_scan])
        open_ports = [p for p in open_ports if p]
        
        logger.info(f"[Service Worker] {len(open_ports)} ports ouverts sur {ip}: {open_ports}")

        # 3. Persistence des services
        async with get_worker_session() as session:
            services_created = []
            for port in open_ports:
                service = Service(
                    id=uuid.uuid4(),
                    asset_id=asset_id,
                    port=port,
                    protocol="tcp",
                    product="Unknown", # Placeholder
                    version=""
                )
                
                # Fingerprint basique pour HTTP
                if port in [80, 443]:
                    scheme = "https" if port == 443 else "http"
                    try:
                        async with httpx.AsyncClient(timeout=3.0, verify=False) as http_client:
                            resp = await http_client.get(f"{scheme}://{target}", follow_redirects=False)
                            server = resp.headers.get("Server", "Unknown")
                            service.product = server
                    except:
                        pass
                
                session.add(service)
                services_created.append(service)
            
            await session.commit()
            
            # 4. Lancer scan_cve pour chaque service identifié
            for s in services_created:
                if s.product and s.product != "Unknown":
                    scan_cve.delay(scan_id, str(s.id), keyword=s.product)

        return {"ip": ip, "ports": open_ports}

    try:
        return asyncio.run(logic())
    except Exception as e:
        logger.error(f"[Service Worker] Erreur: {e}")
        return {"alive": False, "error": str(e)}
