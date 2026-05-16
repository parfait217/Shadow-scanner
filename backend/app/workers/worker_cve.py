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


@celery_app.task(bind=True, max_retries=3)
def scan_cve(self, scan_id: str, service_id: str, cpe_string: str = None, keyword: str = None):
    """
    Recherche de failles CVE connues via la NVD API (NIST — gratuite avec clé).
    Déclenchée par le HTTP Worker quand il identifie un produit/version.
    """
    logger.info(f"[CVE Worker] Recherche CVE pour le service {service_id} | keyword={keyword}")

    async def _run():
        # 1. Fetch CVE depuis NVD
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        params = {}
        if cpe_string:
            params["cpeName"] = cpe_string
        elif keyword:
            params["keywordSearch"] = keyword
        else:
            return None

        headers = {}
        if settings.NVD_API_KEY:
            headers["apiKey"] = settings.NVD_API_KEY

        data = await fetch_json(url, params=params, headers=headers)

        if not data or "vulnerabilities" not in data:
            return {"status": "no_cve_found"}

        vulns = data["vulnerabilities"]
        logger.info(f"[CVE Worker] {len(vulns)} CVE trouvées pour '{keyword or cpe_string}'.")

        # 2. Save — même boucle asyncio
        async with get_worker_session() as session:
            for v in vulns[:5]:  # Limiter à 5 CVE critiques par service
                cve = v.get("cve", {})
                cve_id = cve.get("id")

                cvss = 0.0
                severity = "UNKNOWN"
                metrics = cve.get("metrics", {})

                if "cvssMetricV31" in metrics:
                    m = metrics["cvssMetricV31"][0]["cvssData"]
                    cvss = m["baseScore"]
                    severity = m["baseSeverity"]
                elif "cvssMetricV2" in metrics:
                    m = metrics["cvssMetricV2"][0]["cvssData"]
                    cvss = m["baseScore"]
                    severity = metrics["cvssMetricV2"][0].get("baseSeverity", "MEDIUM")

                vuln = Vulnerability(
                    id=uuid.uuid4(),
                    service_id=service_id,
                    cve_id=cve_id,
                    cvss_score=cvss,
                    severity=severity
                )
                session.add(vuln)

            await session.execute(
                update(Scan).where(Scan.id == scan_id).values(
                    vulns_count=Scan.vulns_count + len(vulns[:5])
                )
            )
            await session.commit()

        return {"status": "success", "cve_count": len(vulns[:5])}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[CVE Worker] Erreur: {e}")
        return {"status": "error", "error": str(e)}
