from app.workers.celery_app import celery_app
import httpx
from app.workers.worker_cve import scan_cve
from app.workers.worker_geoip import scan_geoip
from app.core.config import settings
from app.core.dependencies import get_worker_session
from app.models.service import Service
from app.models.asset import Asset
from app.utils.http_client import fetch_json

import asyncio
import logging
import socket
import uuid
import re

logger = logging.getLogger(__name__)

# ============================================================
# Ports à scanner si Shodan ne fournit pas de données
# ============================================================
FALLBACK_PORTS = [21, 22, 23, 25, 53, 80, 110, 111, 143, 443, 445, 587, 993, 995,
                  1433, 1521, 2181, 3306, 3389, 4848, 5432, 5900, 5984, 6379,
                  7001, 8000, 8080, 8443, 8888, 9000, 9200, 11211, 27017]

# ============================================================
# Wappalyzer - signatures de détection de technologies (open-source)
# ============================================================
TECH_SIGNATURES = {
    # Serveurs web
    "nginx": {"headers": {"server": r"nginx"}, "category": "Web Server"},
    "apache": {"headers": {"server": r"Apache"}, "category": "Web Server"},
    "IIS": {"headers": {"server": r"IIS|Microsoft-IIS"}, "category": "Web Server"},
    "cloudflare": {"headers": {"server": r"cloudflare", "cf-ray": r"."}, "category": "CDN"},
    "aws-cloudfront": {"headers": {"x-amz-cf-id": r".", "via": r"CloudFront"}, "category": "CDN"},
    # Frameworks
    "django": {"headers": {"x-frame-options": r"SAMEORIGIN"}, "body": r"csrfmiddlewaretoken", "category": "Framework"},
    "wordpress": {"body": r"/wp-content/|/wp-includes/", "category": "CMS"},
    "drupal": {"body": r"Drupal\.settings|sites/default/files", "category": "CMS"},
    "joomla": {"body": r"/components/com_|Joomla!", "category": "CMS"},
    "laravel": {"headers": {"set-cookie": r"laravel_session"}, "category": "Framework"},
    "rails": {"headers": {"x-powered-by": r"Phusion Passenger", "server": r"Puma"}, "category": "Framework"},
    "react": {"body": r"react\.development\.js|__REACT_DEVTOOLS", "category": "JS Framework"},
    "vue.js": {"body": r"vue\.min\.js|__vue__", "category": "JS Framework"},
    "angular": {"body": r"ng-version|angular\.min\.js", "category": "JS Framework"},
    "next.js": {"body": r"__NEXT_DATA__|_next/static", "category": "JS Framework"},
    # Bases de données / APIs
    "elasticsearch": {"body": r'"tagline"\s*:\s*"You Know, for Search"', "category": "Search Engine"},
    "graphql": {"body": r'{"data":|"errors":\[', "category": "API"},
    "swagger": {"body": r"swagger-ui|SwaggerUIBundle", "category": "API Documentation"},
    # Services cloud
    "aws-s3": {"body": r"AmazonS3|s3\.amazonaws\.com", "category": "Cloud"},
    "azure": {"headers": {"x-ms-request-id": r"."}, "category": "Cloud"},
    # Sécurité
    "jwt": {"body": r"eyJhbGciOiJ|bearer token", "category": "Authentication"},
    "apache-struts": {"headers": {"x-powered-by": r"Struts"}, "category": "Framework"},
    "phpmyadmin": {"body": r"phpMyAdmin|pma_", "category": "Database Admin"},
}


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


async def _get_http_info(target: str, port: int) -> dict:
    """
    Fingerprinting HTTP avancé : récupère les headers, le titre, le contenu,
    et détecte les technologies via les signatures Wappalyzer.
    """
    scheme = "https" if port in [443, 8443] else "http"
    result = {
        "server": "Unknown",
        "title": "",
        "technologies": [],
        "x_powered_by": "",
        "status_code": 0,
    }
    try:
        async with httpx.AsyncClient(
            timeout=5.0, verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ShadowScanner/2.0)"},
            follow_redirects=True
        ) as client:
            resp = await client.get(f"{scheme}://{target}", )
            result["status_code"] = resp.status_code
            result["server"] = resp.headers.get("Server", "Unknown")
            result["x_powered_by"] = resp.headers.get("X-Powered-By", "")
            body = resp.text[:50000]  # Limiter à 50KB

            # Extraire le titre
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", body, re.I)
            if title_match:
                result["title"] = title_match.group(1).strip()[:200]

            # Détection des technologies via signatures
            for tech_name, sig in TECH_SIGNATURES.items():
                detected = False
                # Check headers
                if "headers" in sig:
                    for header, pattern in sig["headers"].items():
                        header_val = resp.headers.get(header, "")
                        if re.search(pattern, header_val, re.I):
                            detected = True
                            break
                # Check body
                if not detected and "body" in sig:
                    if re.search(sig["body"], body, re.I):
                        detected = True

                if detected:
                    result["technologies"].append({
                        "name": tech_name,
                        "category": sig.get("category", "Unknown")
                    })

    except Exception:
        pass

    return result


@celery_app.task(bind=True, max_retries=3)
def scan_http(self, scan_id: str, asset_id: str, target: str, known_ip: str = None, shodan_data: dict = None):
    """
    Scanner de services TURBOBOOSTÉ :
    - Utilise les données Shodan InternetDB si disponibles (ports + CVEs déjà scannés)
    - Fallback port scan si Shodan n'a pas de données
    - Fingerprinting HTTP avancé avec détection de technologies (Wappalyzer-like)
    """
    logger.info(f"[Service Worker] Analyse de {target} (Asset: {asset_id})")
    if not shodan_data:
        shodan_data = {}

    async def _run():
        # 1. Résolution IP
        ip = known_ip or await _resolve_ip(target)
        if not ip:
            return {"alive": False, "error": "DNS_FAIL"}

        # 1.5 Lancer GeoIP en tâche Celery séparée
        scan_geoip.delay(scan_id, asset_id, ip)

        # 2. Détermination des ports ouverts
        # Priorité: données Shodan (instantané) → sinon port scan traditionnel
        shodan_ports = shodan_data.get("ports", [])
        shodan_cves = shodan_data.get("vulns", [])  # CVEs déjà trouvées par Shodan

        if shodan_ports:
            open_ports = shodan_ports
            logger.info(f"[Service Worker] Shodan InternetDB: {len(open_ports)} ports pour {ip}: {open_ports}")
        else:
            # Fallback: scan TCP traditionnel
            sem = asyncio.Semaphore(15)

            async def _check(p):
                async with sem:
                    return p if await _scan_port(ip, p) else None

            results = await asyncio.gather(*[_check(p) for p in FALLBACK_PORTS])
            open_ports = [p for p in results if p]
            logger.info(f"[Service Worker] Port scan: {len(open_ports)} ports ouverts sur {ip}: {open_ports}")

        if not open_ports:
            return {"ip": ip, "ports": []}

        # 3. Fingerprinting HTTP et persistence des services
        async with get_worker_session() as session:
            services_to_cve = []

            for port in open_ports:
                http_info = {}
                product = "Unknown"

                if port in [80, 443, 8000, 8080, 8443, 8888, 9000]:
                    http_info = await _get_http_info(target, port)
                    product = http_info.get("server", "Unknown")

                    # Utiliser les technos détectées comme mot-clé CVE
                    techs = http_info.get("technologies", [])
                    if techs:
                        product = techs[0]["name"]  # La techno la plus spécifique

                service = Service(
                    id=uuid.uuid4(),
                    asset_id=asset_id,
                    port=port,
                    protocol="tcp",
                    product=product,
                    version=http_info.get("x_powered_by", ""),
                    banner=http_info.get("title", "")[:500] if hasattr(Service, 'banner') else None
                )
                session.add(service)
                services_to_cve.append((str(service.id), product, http_info.get("technologies", [])))

            await session.commit()

            # 4. CVE lookup: Shodan a déjà trouvé des CVEs → les enregistrer directement
            for svc_id, product, techs in services_to_cve:
                # CVEs Shodan (si disponibles)
                if shodan_cves:
                    scan_cve.delay(scan_id, svc_id, keyword=None, shodan_cves=list(shodan_cves))
                elif product and product not in ("Unknown", ""):
                    # Sinon fallback sur Vulners
                    scan_cve.delay(scan_id, svc_id, keyword=product)

                # Scan CVE additionnel pour les technos détectées (Wappalyzer)
                for tech in techs[:2]:  # Max 2 techs par service
                    if tech["name"] not in (product, "Unknown"):
                        scan_cve.delay(scan_id, svc_id, keyword=tech["name"])

        return {"ip": ip, "ports": open_ports, "shodan": bool(shodan_ports)}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[Service Worker] Erreur: {e}")
        return {"alive": False, "error": str(e)}
