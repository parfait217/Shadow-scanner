from app.workers.celery_app import celery_app
import httpx
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

async def check_sensitive_files(domain: str):
    """Fuzzing HTTP basique sur des fichiers réputés sensibles."""
    findings = []
    payloads = [
        "/.env",
        "/.git/config",
        "/server-status",
        "/swagger.json",
        "/phpinfo.php"
    ]
    
    async with httpx.AsyncClient(timeout=3.0, verify=False) as http_client:
        for payload in payloads:
            url = f"http://{domain}{payload}"
            try:
                resp = await http_client.get(url, follow_redirects=False)
                if resp.status_code == 200 and len(resp.text) > 5:
                    # Masquage simple du secret pour RG-F01
                    snippet = resp.text[:50].replace("\n", " ") + "..."
                    if "[core]" in snippet or "APP_KEY=" in snippet or "database" in snippet.lower():
                        findings.append({"type": payload, "snippet": snippet, "status": "open"})
            except Exception:
                pass
            
    return findings

@celery_app.task(bind=True, max_retries=1)
def scan_secrets(self, scan_id: str, root_domain: str):
    """
    Recherche de secrets exposés et fichiers sensibles (Fuzzing HTTP + GitHub).
    """
    logger.info(f"[Secrets Worker] Démarrage Scan Secrets pour {root_domain}")
    
    # Exécuter local fuzzing
    try:
        fuzz_results = asyncio.run(check_sensitive_files(root_domain))
    except Exception as e:
        logger.error(f"[Secrets Worker] Erreur fuzzing: {e}")
        fuzz_results = []
        
    logger.info(f"[Secrets Worker] {len(fuzz_results)} fichiers sensibles trouvés pour {root_domain}")
    
    # Fallback GitHub API (si clé présente)
    if settings.GITHUB_API_KEY:
        # Lancer requête GitHub Search API pour 'domain credential'
        pass
        
    # TODO: Enregistrer dans la base de données (FindingRepository)
    
    return {"findings": fuzz_results}
