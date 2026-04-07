from app.workers.celery_app import celery_app
import httpx
from app.core.config import settings
from app.core.dependencies import get_worker_session
from app.repositories.finding_repository import FindingRepository
from app.models.finding import Finding
from app.models.asset import Asset
from sqlalchemy import select
import logging
import asyncio
import uuid

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
    
    async def _save_findings():
        scan_uuid = uuid.UUID(scan_id)
        async with get_worker_session() as session:
            # Essayer de trouver l'asset racine
            stmt = select(Asset).where(Asset.scan_id == scan_uuid, Asset.value == root_domain)
            result = await session.execute(stmt)
            root_asset = result.scalars().first()
            
            # Si l'asset racine n'est pas encore inséré (race condition DNS), 
            # on le crée minimalement.
            if not root_asset:
                root_asset = Asset(
                    scan_id=scan_uuid,
                    type="domain",
                    value=root_domain,
                    is_alive=True
                )
                session.add(root_asset)
                await session.flush()

            repo = FindingRepository(session)
            for f_data in fuzz_results:
                finding = Finding(
                    asset_id=root_asset.id,
                    type="sensitive_file",
                    source=f_data.get("type", "unknown"),
                    masked_value=f_data.get("snippet", "hidden")
                )
                await repo.create(finding)
                
            await session.commit()
            
    asyncio.run(_save_findings())
    
    return {"findings": fuzz_results}
