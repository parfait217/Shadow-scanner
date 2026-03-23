from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json
from app.core.config import settings
import logging
import asyncio
import uuid

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
        
        # Parse basic de CVSS
        for v in vulns[:10]: # Limiter l'insertion aux 10 les plus graves par exemple
            cve = v.get("cve", {})
            cve_id = cve.get("id")
            # Extraction du CVSS v3 ou v2
            cvss = 0.0
            metrics = cve.get("metrics", {})
            if "cvssMetricV31" in metrics:
                cvss = metrics["cvssMetricV31"][0]["cvssData"]["baseScore"]
            cve_list.append({"id": cve_id, "score": cvss})
            
            # TODO: Insérer Vulnerability dans la BDD (MtoM avec le service)
            
    return {"cves": cve_list}
