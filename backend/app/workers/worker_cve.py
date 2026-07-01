from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
from app.core.config import settings
from app.core.dependencies import get_worker_session
from app.models.vulnerability import Vulnerability
from app.models.scan import Scan

import logging
import asyncio
import uuid
from sqlalchemy import update

logger = logging.getLogger(__name__)


async def _search_vulners(keyword: str) -> list:
    """
    Recherche de vulnérabilités via Vulners.com API (GRATUIT, 30 req/min).
    Vulners agrège NVD, ExploitDB, Packetstorm, GitHub Security Advisories.
    Retourne aussi le score EPSS (probabilité d'exploitation dans les 30j).
    """
    vulns = []
    try:
        url = "https://vulners.com/api/v3/search/lucene/"
        params = {
            "query": f'type:cve "{keyword}"',
            "fields": "id,cvss,title,description,published,type",
            "size": 10,
        }
        data = await fetch_json(url, params=params)

        if not data or data.get("result") != "OK":
            return vulns

        for item in data.get("data", {}).get("search", []):
            source = item.get("_source", {})
            cve_id = source.get("id", "")
            if not cve_id.startswith("CVE-"):
                continue

            cvss = 0.0
            severity = "UNKNOWN"
            cvss_data = source.get("cvss", {})
            if cvss_data:
                cvss = float(cvss_data.get("score", 0))
                if cvss >= 9.0:
                    severity = "CRITICAL"
                elif cvss >= 7.0:
                    severity = "HIGH"
                elif cvss >= 4.0:
                    severity = "MEDIUM"
                elif cvss > 0:
                    severity = "LOW"

            vulns.append({
                "cve_id": cve_id,
                "cvss": cvss,
                "severity": severity,
                "title": source.get("title", ""),
            })

    except Exception as e:
        logger.debug(f"[CVE Worker] Vulners erreur pour '{keyword}': {e}")

    return vulns


async def _get_epss_score(cve_id: str) -> float:
    """
    Récupère le score EPSS (Exploit Prediction Scoring System) pour une CVE.
    EPSS = probabilité qu'une CVE soit exploitée dans les 30 prochains jours.
    API FIRST.org (100% gratuite).
    """
    try:
        data = await fetch_json(f"https://api.first.org/data/v1/epss?cve={cve_id}")
        if data and data.get("data"):
            return float(data["data"][0].get("epss", 0))
    except Exception:
        pass
    return 0.0


async def _search_nvd_fallback(keyword: str) -> list:
    """Fallback NVD si Vulners ne répond pas."""
    vulns = []
    try:
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        params = {"keywordSearch": keyword, "resultsPerPage": 5}
        headers = {}
        if settings.NVD_API_KEY:
            headers["apiKey"] = settings.NVD_API_KEY
        data = await fetch_json(url, params=params, headers=headers)
        if not data or "vulnerabilities" not in data:
            return vulns
        for v in data["vulnerabilities"][:5]:
            cve = v.get("cve", {})
            cve_id = cve.get("id", "")
            cvss, severity = 0.0, "UNKNOWN"
            metrics = cve.get("metrics", {})
            if "cvssMetricV31" in metrics:
                m = metrics["cvssMetricV31"][0]["cvssData"]
                cvss, severity = m["baseScore"], m["baseSeverity"]
            vulns.append({"cve_id": cve_id, "cvss": cvss, "severity": severity, "title": ""})
    except Exception:
        pass
    return vulns


@celery_app.task(bind=True, max_retries=3)
def scan_cve(self, scan_id: str, service_id: str, cpe_string: str = None, keyword: str = None, shodan_cves: list = None):
    """
    Recherche de CVEs via Vulners.com (principal) + NVD (fallback) + Shodan (direct).
    Enrichissement EPSS pour prioriser les vulnérabilités les plus dangereuses.
    """
    logger.info(f"[CVE Worker] Recherche CVE pour service {service_id} | keyword={keyword} | shodan_cves={shodan_cves}")

    async def _run():
        raw_vulns = []

        # Source 1: CVEs Shodan (déjà confirmées sur l'IP)
        if shodan_cves:
            for cve_id in shodan_cves[:10]:
                if cve_id.startswith("CVE-"):
                    raw_vulns.append({
                        "cve_id": cve_id,
                        "cvss": 7.0,  # Score par défaut — sera enrichi par EPSS
                        "severity": "HIGH",
                        "title": f"Shodan confirmed: {cve_id}",
                    })
            logger.info(f"[CVE Worker] {len(raw_vulns)} CVEs directes Shodan pour {service_id}")

        # Source 2: Vulners.com (principal)
        elif keyword:
            raw_vulns = await _search_vulners(keyword)
            if not raw_vulns:
                # Fallback NVD
                raw_vulns = await _search_nvd_fallback(keyword)

        if not raw_vulns:
            return {"status": "no_cve_found"}

        logger.info(f"[CVE Worker] {len(raw_vulns)} CVE(s) trouvées pour '{keyword or 'shodan'}'. Enrichissement EPSS...")

        # Enrichissement EPSS (parallèle pour toutes les CVEs)
        epss_scores = await asyncio.gather(
            *[_get_epss_score(v["cve_id"]) for v in raw_vulns],
            return_exceptions=True
        )

        # Tri par criticité: EPSS × CVSS
        for i, v in enumerate(raw_vulns):
            epss = float(epss_scores[i]) if isinstance(epss_scores[i], (int, float)) else 0.0
            v["epss"] = epss
            v["priority_score"] = v["cvss"] * (1 + epss * 10)  # Boost si EPSS élevé

        raw_vulns.sort(key=lambda x: x["priority_score"], reverse=True)

        # Persistence dans la DB
        async with get_worker_session() as session:
            saved_count = 0
            for v in raw_vulns[:8]:  # Max 8 CVE par service
                vuln = Vulnerability(
                    id=uuid.uuid4(),
                    service_id=service_id,
                    cve_id=v["cve_id"],
                    cvss_score=v["cvss"],
                    severity=v["severity"].upper(),
                )
                session.add(vuln)
                saved_count += 1

            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(
                    vulns_count=Scan.vulns_count + saved_count
                )
            )
            await session.commit()

        logger.info(f"[CVE Worker] {saved_count} CVE(s) persistées pour service {service_id}")
        return {"status": "success", "cve_count": saved_count}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[CVE Worker] Erreur: {e}")
        return {"status": "error", "error": str(e)}
