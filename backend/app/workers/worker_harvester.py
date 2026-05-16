from app.workers.celery_app import celery_app
from app.workers.worker_breach import check_breach
from app.core.dependencies import get_worker_session
from app.repositories.employee_repository import EmployeeRepository
from app.models.employee import Employee
from app.utils.redis_pub import publish_scan_update
import httpx
import re
import logging
import asyncio
import uuid
from typing import Set

logger = logging.getLogger(__name__)

# Regex pour extraire les emails valides d'un domaine
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# User-Agent réaliste pour éviter les blocages basiques
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ShadowScanner/1.0; +https://github.com/shadow-scanner)"
}


async def _fetch_security_txt(domain: str) -> Set[str]:
    """
    Interroge les fichiers security.txt et humans.txt pour extraire des emails.
    Ces fichiers sont un standard IETF (RFC 9116) que les entreprises publient volontairement.
    """
    emails = set()
    urls = [
        f"https://{domain}/.well-known/security.txt",
        f"http://{domain}/.well-known/security.txt",
        f"https://{domain}/security.txt",
        f"https://{domain}/humans.txt",
        f"http://{domain}/humans.txt",
    ]

    async with httpx.AsyncClient(timeout=5.0, verify=False, headers=HEADERS, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.text) > 5:
                    found = EMAIL_REGEX.findall(resp.text)
                    for email in found:
                        if domain in email or True:  # on garde tous les emails du fichier
                            emails.add(email.lower())
                    if found:
                        logger.info(f"[Harvester] {len(found)} emails trouvés dans {url}")
            except Exception:
                pass

    return emails


async def _scrape_homepage_emails(domain: str) -> Set[str]:
    """
    Scrape la page principale du domaine et les pages de contact classiques
    pour extraire les emails exposés dans le HTML.
    """
    emails = set()
    urls_to_check = [
        f"https://{domain}",
        f"https://{domain}/contact",
        f"https://{domain}/contact-us",
        f"https://{domain}/about",
        f"https://{domain}/team",
        f"http://{domain}",
    ]

    async with httpx.AsyncClient(timeout=8.0, verify=False, headers=HEADERS, follow_redirects=True) as client:
        for url in urls_to_check:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    found = EMAIL_REGEX.findall(resp.text)
                    for email in found:
                        # Filtre les emails qui contiennent le domaine ou les sous-domaines
                        email_domain = email.split("@")[-1]
                        if email_domain == domain or email_domain.endswith(f".{domain}"):
                            emails.add(email.lower())
            except Exception:
                pass

    return emails


async def _scrape_rdap(domain: str) -> Set[str]:
    """
    Interroge l'API RDAP (Registration Data Access Protocol) — standard IANA.
    Retourne les emails publics des contacts du registrar (technique, admin, etc.).
    """
    emails = set()
    url = f"https://rdap.org/domain/{domain}"

    try:
        async with httpx.AsyncClient(timeout=8.0, verify=False, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                # Parcours récursif du JSON RDAP pour trouver les vcardArray
                raw_text = resp.text
                found = EMAIL_REGEX.findall(raw_text)
                for email in found:
                    emails.add(email.lower())
    except Exception as e:
        logger.debug(f"[Harvester] RDAP indisponible pour {domain}: {e}")

    return emails


async def _scrape_duckduckgo(domain: str) -> Set[str]:
    """
    Scrape DuckDuckGo HTML pour la requête 'site:domain email @domain'
    et extrait les emails trouvés dans les extraits de résultats.
    Pas de rate-limit strict sur DuckDuckGo HTML (contrairement à Google).
    """
    emails = set()
    query = f'"@{domain}" email contact'
    url = "https://html.duckduckgo.com/html/"

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False, headers=HEADERS) as client:
            resp = await client.post(url, data={"q": query})
            if resp.status_code == 200:
                found = EMAIL_REGEX.findall(resp.text)
                for email in found:
                    email_domain = email.split("@")[-1]
                    if email_domain == domain or email_domain.endswith(f".{domain}"):
                        emails.add(email.lower())
                if found:
                    logger.info(f"[Harvester] DuckDuckGo a retourné {len(found)} candidats email pour {domain}")
    except Exception as e:
        logger.debug(f"[Harvester] DuckDuckGo scraper erreur: {e}")

    return emails

async def _scrape_pgp_keyserver(domain: str) -> Set[str]:
    """
    Interroge les serveurs de clés PGP publics (Ubuntu Keyserver).
    C'est une excellente mine d'or OSINT gratuite pour trouver des emails d'employés (développeurs, admins).
    """
    emails = set()
    url = f"http://keyserver.ubuntu.com/pks/lookup?search={domain}&op=index"
    
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                found = EMAIL_REGEX.findall(resp.text)
                for email in found:
                    email_domain = email.split("@")[-1]
                    if email_domain == domain or email_domain.endswith(f".{domain}"):
                        emails.add(email.lower())
                if emails:
                    logger.info(f"[Harvester] PGP Keyserver a retourné {len(emails)} emails pour {domain}")
    except Exception as e:
        logger.debug(f"[Harvester] PGP Keyserver erreur: {e}")
        
    return emails


@celery_app.task(bind=True, max_retries=2)
def harvest_emails(self, scan_id: str, root_domain: str):
    """
    Recherche réelle d'adresses emails liées au domaine via 4 sources distinctes :
    1. security.txt / humans.txt (RFC 9116)
    2. Scraping des pages HTML du domaine
    3. API RDAP (données WHOIS standardisées)
    4. Scraping DuckDuckGo HTML
    """
    logger.info(f"[Harvester Worker] Démarrage de la collecte emails pour {root_domain}")

    async def _run():
        results = await asyncio.gather(
            _fetch_security_txt(root_domain),
            _scrape_homepage_emails(root_domain),
            _scrape_rdap(root_domain),
            _scrape_duckduckgo(root_domain),
            _scrape_pgp_keyserver(root_domain),
            return_exceptions=True  # Ne pas planter si une source échoue
        )
        
        found_emails = set()
        for r in results:
            if isinstance(r, set):
                found_emails.update(r)
            elif isinstance(r, Exception):
                logger.warning(f"[Harvester] Une source a échoué: {r}")

        logger.info(f"[Harvester Worker] {len(found_emails)} emails uniques trouvés pour {root_domain}: {found_emails}")

        if not found_emails:
            return {"emails_found": 0, "emails": []}

        scan_uuid = uuid.UUID(scan_id)
        async with get_worker_session() as session:
            repo = EmployeeRepository(session)

            for email in found_emails:
                existing = await repo.get_by_email_and_scan(email, scan_uuid)
                
                if not existing:
                    emp = Employee(
                        id=uuid.uuid4(),
                        scan_id=scan_uuid,
                        email=email
                    )
                    await repo.create(emp)
                    await session.flush()
                    employee_id = str(emp.id)
                else:
                    employee_id = str(existing.id)

                # Lancer la vérification de brèche pour chaque email
                check_breach.delay(scan_id, employee_id, email)

            await session.commit()
            
            # Notifier le frontend
            if found_emails:
                await publish_scan_update(scan_id, "REFRESH", {"type": "osint", "emails_count": len(found_emails)})

        return {"emails_found": len(found_emails), "emails": list(found_emails)}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[Harvester Worker] Erreur lors de la collecte ou de la persistance: {e}")
        return {"emails_found": 0, "emails": [], "error": str(e)}
