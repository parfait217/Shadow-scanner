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
    Recherche de failles CVE connues pour un CPE ou mot-clé (ex: "apache httpd 2.4.49").
    Délégé silencieusement par le HTTP Worker quand il trouve la version exacte d'un serveur.
    """
    logger.info(f"[CVE Worker] Recherche CVE pour le service {service_id}")
    
    # Stratégie : utiliser NVD API
    # En absence de clé NVD API, NVD limite fortement le rate (5/req par minute roulante)
    # L'utilisation du mot clé (keywordSearch) est très utile.
    
    async def fetch():
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
            
        return await fetch_json(url, params=params, headers=headers)

    try:
        data = asyncio.run(fetch())
    except Exception as e:
        logger.error(f"[CVE Worker] Erreur API: {e}")
        return None
        
    cve_list = []
    if data and "vulnerabilities" in data:
        vulns = data["vulnerabilities"]
        logger.info(f"[CVE Worker] {len(vulns)} CVE trouvées pour {keyword or cpe_string}.")
        
        async def save_vulns():
            async with get_worker_session() as session:
                for v in vulns[:5]: # Limiter à 5 CVE critiques/hautes par service
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
                        # V2 severity is in a different place
                        severity = metrics["cvssMetricV2"][0].get("baseSeverity", "MEDIUM")

                    vuln = Vulnerability(
                        id=uuid.uuid4(),
                        service_id=service_id,
                        cve_id=cve_id,
                        cvss_score=cvss,
                        severity=severity
                    )
                    session.add(vuln)
                
                # Optionnel : Mettre à jour vulns_count sur le Scan
                await session.execute(
                    update(Scan).where(Scan.id == scan_id).values(
                        vulns_count=Scan.vulns_count + len(vulns[:5])
                    )
                )
                await session.commit()

        try:
            asyncio.run(save_vulns())
        except Exception as e:
            logger.error(f"[CVE Worker] Erreur Save: {e}")

    return {"status": "success"}
