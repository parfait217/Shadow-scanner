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

# Regex pour extraire les emails valides
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Domaines de bruit à filtrer (emails génériques de services tiers)
EMAIL_NOISE_DOMAINS = {
    "example.com", "test.com", "domain.com", "yourdomain.com",
    "sentry.io", "cloudflare.com", "amazonaws.com", "google.com",
    "w3.org", "schema.org", "github.com",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _is_valid_email(email: str, domain: str) -> bool:
    """Filtre les faux-positifs et les emails de bruit."""
    email_domain = email.split("@")[-1].lower()
    # Filtre bruit
    if email_domain in EMAIL_NOISE_DOMAINS:
        return False
    # Filtre extension invalide
    if len(email_domain.split(".")[-1]) > 6:
        return False
    # Filtre noreply, support génériques (sauf du bon domaine)
    generic_prefixes = ["noreply", "no-reply", "donotreply", "webmaster@w3"]
    if any(email.lower().startswith(p) for p in generic_prefixes) and email_domain != domain:
        return False
    return True


async def _fetch_security_txt(domain: str) -> Set[str]:
    """
    Fichiers security.txt et humans.txt (standard IETF RFC 9116).
    Les entreprises y publient volontairement leurs contacts sécurité.
    """
    emails = set()
    urls = [
        f"https://{domain}/.well-known/security.txt",
        f"http://{domain}/.well-known/security.txt",
        f"https://{domain}/security.txt",
        f"https://{domain}/humans.txt",
    ]
    async with httpx.AsyncClient(timeout=5.0, verify=False, headers=HEADERS, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.text) > 5:
                    for email in EMAIL_REGEX.findall(resp.text):
                        if _is_valid_email(email, domain):
                            emails.add(email.lower())
            except Exception:
                pass
    if emails:
        logger.info(f"[Harvester] security.txt: {len(emails)} emails pour {domain}")
    return emails


async def _scrape_homepage_emails(domain: str) -> Set[str]:
    """
    Scrape les pages publiques du domaine (homepage, contact, about, team).
    Cible les emails @domain exposés dans le HTML.
    """
    emails = set()
    pages = [
        f"https://{domain}",
        f"https://{domain}/contact",
        f"https://{domain}/contact-us",
        f"https://{domain}/about",
        f"https://{domain}/team",
        f"https://{domain}/about-us",
        f"https://{domain}/who-we-are",
        f"https://{domain}/staff",
        f"https://www.{domain}/contact",
    ]
    sem = asyncio.Semaphore(5)
    async with httpx.AsyncClient(timeout=7.0, verify=False, headers=HEADERS, follow_redirects=True) as client:
        async def _get(url: str):
            async with sem:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        body = resp.text[:100000]
                        for email in EMAIL_REGEX.findall(body):
                            email_domain = email.split("@")[-1].lower()
                            if (email_domain == domain or email_domain.endswith(f".{domain}")) \
                                    and _is_valid_email(email, domain):
                                emails.add(email.lower())
                except Exception:
                    pass
        await asyncio.gather(*[_get(u) for u in pages], return_exceptions=True)
    if emails:
        logger.info(f"[Harvester] Homepage scrape: {len(emails)} emails pour {domain}")
    return emails


async def _scrape_rdap(domain: str) -> Set[str]:
    """
    API RDAP (Registration Data Access Protocol) — standard IANA.
    Retourne les contacts registrar (admin, technique) avec leurs emails.
    """
    emails = set()
    urls = [
        f"https://rdap.org/domain/{domain}",
        f"https://rdap.arin.net/registry/domain/{domain}",
    ]
    async with httpx.AsyncClient(timeout=8.0, verify=False, headers=HEADERS) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    for email in EMAIL_REGEX.findall(resp.text):
                        if _is_valid_email(email, domain):
                            emails.add(email.lower())
            except Exception:
                pass
    if emails:
        logger.info(f"[Harvester] RDAP: {len(emails)} emails pour {domain}")
    return emails


async def _scrape_pgp_keyserver(domain: str) -> Set[str]:
    """
    Serveurs de clés PGP publics (Ubuntu Keyserver + OpenPGP).
    Mine d'or OSINT : les développeurs y publient leurs clés avec leur email pro.
    """
    emails = set()
    servers = [
        f"https://keyserver.ubuntu.com/pks/lookup?search={domain}&op=index&fingerprint=on",
        f"https://keys.openpgp.org/search?q={domain}",
    ]
    async with httpx.AsyncClient(timeout=12.0, verify=False, headers=HEADERS, follow_redirects=True) as client:
        for url in servers:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    for email in EMAIL_REGEX.findall(resp.text):
                        email_domain = email.split("@")[-1].lower()
                        if (email_domain == domain or email_domain.endswith(f".{domain}")) \
                                and _is_valid_email(email, domain):
                            emails.add(email.lower())
            except Exception as e:
                logger.debug(f"[Harvester] PGP Keyserver erreur: {e}")
    if emails:
        logger.info(f"[Harvester] PGP Keyservers: {len(emails)} emails pour {domain}")
    return emails


async def _scrape_github_search(domain: str) -> Set[str]:
    """
    Recherche GitHub via l'API publique (sans clé, limité à 10 req/min).
    Cherche les commits et profiles avec @domain dans le nom.
    """
    emails = set()
    # Search commits with domain email (API publique, sans authentification)
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={
            **HEADERS, "Accept": "application/vnd.github+json"
        }) as client:
            resp = await client.get(
                "https://api.github.com/search/commits",
                params={"q": f"author-email:{domain}", "per_page": 30},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    commit = item.get("commit", {})
                    author_email = commit.get("author", {}).get("email", "")
                    if author_email and _is_valid_email(author_email, domain):
                        emails.add(author_email.lower())
    except Exception as e:
        logger.debug(f"[Harvester] GitHub search erreur: {e}")
    if emails:
        logger.info(f"[Harvester] GitHub: {len(emails)} emails pour {domain}")
    return emails


@celery_app.task(bind=True, max_retries=2)
def harvest_emails(self, scan_id: str, root_domain: str):
    """
    Collecte OSINT d'emails via 6 sources distinctes en parallèle :
    1. security.txt / humans.txt (RFC 9116)
    2. Scraping HTML (homepage, contact, team...)
    3. API RDAP (WHOIS standardisé)
    4. PGP Keyservers (Ubuntu + OpenPGP)
    5. GitHub API publique (commits, profiles)
    + Déclenchement automatique de la détection de fuites (HaveIBeenPwned compatible)
    """
    logger.info(f"[Harvester Worker] Collecte OSINT démarrée pour {root_domain} (6 sources)")

    async def _run():
        # Collecte parallèle de toutes les sources
        results = await asyncio.gather(
            _fetch_security_txt(root_domain),
            _scrape_homepage_emails(root_domain),
            _scrape_rdap(root_domain),
            _scrape_pgp_keyserver(root_domain),
            _scrape_github_search(root_domain),
            return_exceptions=True
        )

        found_emails = set()
        for r in results:
            if isinstance(r, set):
                found_emails.update(r)
            elif isinstance(r, Exception):
                logger.warning(f"[Harvester] Source échouée: {r}")

        # Déduplification finale et nettoyage
        found_emails = {e.strip().lower() for e in found_emails if "@" in e and len(e) < 100}

        logger.info(f"[Harvester Worker] ✓ {len(found_emails)} emails uniques collectés pour {root_domain}")

        if not found_emails:
            return {"emails_found": 0, "emails": []}

        scan_uuid = uuid.UUID(scan_id)
        async with get_worker_session() as session:
            repo = EmployeeRepository(session)
            new_count = 0

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
                    new_count += 1
                else:
                    employee_id = str(existing.id)

                # Vérification de brèche pour chaque email
                check_breach.delay(scan_id, employee_id, email)

            await session.commit()

            logger.info(f"[Harvester Worker] {new_count} nouveaux employés persistés en DB")

            # Notifier le frontend en temps réel
            await publish_scan_update(scan_id, "REFRESH", {
                "type": "osint",
                "emails_found": len(found_emails),
                "new_employees": new_count,
            })

        return {"emails_found": len(found_emails), "emails": list(found_emails)}

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[Harvester Worker] Erreur critique: {e}")
        return {"emails_found": 0, "emails": [], "error": str(e)}
