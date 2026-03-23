from app.workers.celery_app import celery_app
from app.utils.http_client import fetch_json, fetch_text
from app.workers.worker_http import scan_http
from app.workers.worker_geoip import scan_geoip
from celery import chord
import asyncio
import logging
import uuid
from typing import Set

logger = logging.getLogger(__name__)

async def _fetch_crt_sh(domain: str) -> Set[str]:
    """Interroge crt.sh pour trouver des sous-domaines dans les certificats (Gratuit)."""
    subdomains = set()
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    data = await fetch_json(url)
    if not data:
        return subdomains
        
    for entry in data:
        name_value = entry.get("name_value", "")
        # Gère les certificats "multidomaines" séparés par des retours chariot
        for sub in name_value.split("\n"):
            sub = sub.strip().lower()
            if sub.endswith(domain) and not sub.startswith("*"):
                subdomains.add(sub)
    return subdomains

async def _fetch_hackertarget(domain: str) -> Set[str]:
    """Interroge HackerTarget hostsearch (Gratuit, limité mais utile)."""
    subdomains = set()
    url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
    text = await fetch_text(url)
    if not text or "error" in text.lower():
        return subdomains
        
    for line in text.split("\n"):
        if "," in line:
            sub = line.split(",")[0].strip().lower()
            if sub.endswith(domain):
                subdomains.add(sub)
    return subdomains

@celery_app.task(bind=True, max_retries=3)
def scan_dns(self, scan_id: str, target_domain: str):
    """
    Découverte de sous-domaines (crt.sh, HackerTarget) puis lancement de l'étape suivante (HTTP/GeoIP).
    Dans Celery, on doit lancer la boucle event async manuellement si on a des fcts async.
    """
    logger.info(f"[DNS Worker] Scan {scan_id} pour {target_domain}")
    
    # 1. Résolution asynchrone concurrente
    async def _gather():
        crt, ht = await asyncio.gather(
            _fetch_crt_sh(target_domain),
            _fetch_hackertarget(target_domain)
        )
        return crt.union(ht)
    
    try:
        found_subdomains = asyncio.run(_gather())
    except Exception as e:
        logger.error(f"[DNS Worker] Erreur asynchrone: {e}")
        found_subdomains = set()
    found_subdomains.add(target_domain)  # On ajoute toujours le domaine racine
    
    logger.info(f"[DNS Worker] {len(found_subdomains)} trouvés pour {target_domain}")

    # 2. Sauvegarde dans la base
    # (En condition réelle, on appellerait une session sqlalchemy synchrone ou un endpoint interne)
    # TODO: Enregistrer Asset(type="subdomain", value=sub)

    # 3. Lancer les Scans HTTP et GeoIP pour CHAQUE sous_domaine.
    tasks = []
    for sub in found_subdomains:
        # Mock d'UUID pour chaque Asset inséré en base
        asset_id = str(uuid.uuid4())
        
        # On peut attacher la résolution DNS à ces tâches. Pour l'instant on passe l'ID
        # scan_http sera chargé du TLS et du Shodan/Ports
        # scan_geoip sera chargé de l'ASN de l'IP une fois lue (résolution faite dans le worker_http idéalement)
        
        # Le trigger: HTTP
        tasks.append(scan_http.s(scan_id, asset_id, sub))
    
    # Exécution des tâches HTTP en parallèle.
    if tasks:
        # On utilise une map simple. chord() pourrait fermer si on a un cleanup.
        from celery import group
        group(tasks).apply_async()

    return {"subdomains": list(found_subdomains)}
