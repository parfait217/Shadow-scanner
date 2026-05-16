from app.workers.celery_app import celery_app
import httpx
from app.workers.worker_cve import scan_cve
from app.workers.worker_geoip import scan_geoip
from app.core.config import settings
from app.core.dependencies import get_worker_session
from app.models.service import Service
from app.utils.http_client import fetch_json

import asyncio
import logging
import socket
import uuid

logger = logging.getLogger(__name__)

PORTS_TO_SCAN = [21, 22, 25, 53, 80, 111, 443, 445, 3306, 5432, 6379, 8080, 8443]


async def _resolve_ip(hostname: str) -> str:
    """Résolution DNS via thread executor (non bloquant)."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, socket.gethostbyname, hostname)
    except Exception:
        return None


async def _scan_port(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Vérifie si un port TCP est ouvert."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def _get_http_banner(target: str, port: int) -> str:
    """Récupère le header Server via HTTP/HTTPS."""
    scheme = "https" if port == 443 else "http"
    try:
        async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
            resp = await client.get(f"{scheme}://{target}", follow_redirects=False)
            return resp.headers.get("Server", "Unknown")
    except Exception:
        return "Unknown"


@celery_app.task(bind=True, max_retries=3)
def scan_http(self, scan_id: str, asset_id: str, target: str):
    """
    Détection de services ouverts (port scan) et fingerprinting HTTP.
    Corrigé : une seule boucle asyncio pour éviter 'Event loop is closed'.
    """
    logger.info(f"[Service Worker] Analyse de {target} (Asset: {asset_id})")

    async def _run():
        # 1. Résolution IP
        ip = await _resolve_ip(target)
        if not ip:
            return {"alive": False, "error": "DNS_FAIL"}

        # 1.5 Lancer GeoIP en tâche Celery séparée (non-blocking)
        scan_geoip.delay(scan_id, asset_id, ip)

        # 2. Scan de ports concurrent (max 10 en parallèle)
        sem = asyncio.Semaphore(10)

        async def _check(p):
            async with sem:
                return p if await _scan_port(ip, p) else None

        results = await asyncio.gather(*[_check(p) for p in PORTS_TO_SCAN])
        open_ports = [p for p in results if p]

        logger.info(f"[Service Worker] {len(open_ports)} ports ouverts sur {ip}: {open_ports}")

        if not open_ports:
            return {"ip": ip, "ports": []}

        # 3. Persistence des services — même boucle asyncio
        async with get_worker_session() as session:
            services_to_cve = []

            for port in open_ports:
                product = "Unknown"

                # Fingerprint HTTP basique
                if port in [80, 443, 8080, 8443]:
                    product = await _get_http_banner(target, port)

                service = Service(
                    id=uuid.uuid4(),
                    asset_id=asset_id,
                    port=port,
                    protocol="tcp",
                    product=product,
                    version=""
                )
                session.add(service)
                services_to_cve.append((str(service.id), product))

            await session.commit()

            # 4. Lancer scan_cve pour chaque service identifié (hors "Unknown")
            for svc_id, product in services_to_cve:
                if product and product not in ("Unknown", ""):
                    scan_cve.delay(scan_id, svc_id, keyword=product)

        return {"ip": ip, "ports": open_ports}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[Service Worker] Erreur: {e}")
        return {"alive": False, "error": str(e)}
