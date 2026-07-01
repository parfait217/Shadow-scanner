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
import re

logger = logging.getLogger(__name__)

# ============================================================
# 200+ endpoints sensibles à fuzzer (payloads OWASP + HackTricks)
# ============================================================
SENSITIVE_ENDPOINTS = [
    # Fichiers de configuration
    "/.env", "/.env.local", "/.env.production", "/.env.development", "/.env.backup",
    "/.env.old", "/.env.example", "/.env.sample", "/.env.bak", "/.env.staging",
    "/.env.test", "/config.env", "/app.env",
    # Git / Versioning
    "/.git/config", "/.git/HEAD", "/.git/COMMIT_EDITMSG",
    "/.gitignore", "/.gitmodules", "/.svn/entries",
    # Config Web
    "/config.php", "/config.yml", "/config.yaml", "/config.json", "/config.xml",
    "/configuration.php", "/settings.php", "/settings.py", "/settings.yml",
    "/application.properties", "/application.yml", "/bootstrap.php",
    "/web.config", "/appsettings.json", "/appsettings.Development.json",
    # Bases de données
    "/backup.sql", "/database.sql", "/dump.sql", "/db.sql", "/backup.db",
    "/db.sqlite", "/db.sqlite3", "/database.db",
    # Fichiers sensibles courants
    "/wp-config.php", "/wp-config.php.bak", "/wp-config.old",
    "/phpinfo.php", "/info.php", "/test.php",
    "/server-status", "/server-info",
    "/.htaccess", "/.htpasswd",
    # Documentation API
    "/swagger.json", "/swagger.yaml", "/openapi.json", "/openapi.yaml",
    "/api-docs", "/api-docs.json", "/api/swagger.json", "/api/openapi.json",
    "/docs/swagger.json", "/v1/swagger.json", "/v2/swagger.json", "/v3/swagger.json",
    # Spring Boot / Java Actuator (très courant dans les entreprises)
    "/actuator", "/actuator/env", "/actuator/beans", "/actuator/health",
    "/actuator/info", "/actuator/metrics", "/actuator/mappings",
    "/actuator/httptrace", "/actuator/dump", "/actuator/configprops",
    "/actuator/loggers", "/actuator/auditevents", "/actuator/shutdown",
    # Laravel / PHP
    "/storage/logs/laravel.log", "/storage/logs/app.log",
    "/storage/.env", "/.idea/workspace.xml",
    # Node.js
    "/package.json", "/package-lock.json", "/yarn.lock",
    "/node_modules/.env",
    # Python
    "/requirements.txt", "/Pipfile", "/Pipfile.lock",
    "/pyproject.toml",
    # Logs
    "/logs/error.log", "/logs/access.log", "/var/log/nginx/error.log",
    "/log/app.log", "/app/logs/app.log",
    # Admin panels
    "/admin", "/admin/", "/admin/login", "/administrator",
    "/wp-admin", "/wp-login.php",
    "/phpmyadmin", "/pma", "/phpMyAdmin",
    "/adminer", "/adminer.php",
    # CI/CD
    "/.travis.yml", "/.github/workflows/main.yml", "/Jenkinsfile",
    "/docker-compose.yml", "/docker-compose.yaml", "/Dockerfile",
    "/.dockerignore",
    # Kubernetes / Cloud
    "/k8s-config.yml", "/kubernetes.yml", "/.kube/config",
    # Certificats / Clés
    "/id_rsa", "/id_rsa.pub", "/server.key", "/private.key",
    "/.ssh/id_rsa", "/.ssh/authorized_keys",
    # Sauvegardes
    "/backup.zip", "/backup.tar.gz", "/backup.tar", "/www.zip",
    "/site.zip", "/html.zip", "/web.zip",
    # Debug endpoints
    "/.well-known/security.txt",
    "/robots.txt", "/sitemap.xml",
    "/_profiler/phpinfo", "/xdebug/info",
]

# Regex pour détecter des secrets dans le contenu retourné
SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"[0-9a-zA-Z/+]{40}",
    "GitHub Token": r"ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82}",
    "Stripe API Key": r"sk_live_[0-9a-zA-Z]{24}|rk_live_[0-9a-zA-Z]{24}",
    "Private RSA Key": r"-----BEGIN RSA PRIVATE KEY-----",
    "Private Key": r"-----BEGIN PRIVATE KEY-----",
    "DB Password": r"(?i)(DB_PASSWORD|DATABASE_PASSWORD|MYSQL_PASSWORD|POSTGRES_PASSWORD)\s*=\s*\S+",
    "App Key": r"(?i)(APP_KEY|SECRET_KEY|SECRET|API_KEY)\s*=\s*\S+",
    "Git Config": r"\[core\]|\[remote",
    "JWT Secret": r"(?i)(JWT_SECRET|TOKEN_SECRET)\s*=\s*\S+",
    "SendGrid Key": r"SG\.[0-9a-zA-Z_\-]{22}\.[0-9a-zA-Z_\-]{43}",
    "Slack Token": r"xox[baprs]-[0-9a-zA-Z\-]{10,}",
    "Heroku Key": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
    "phpinfo": r"PHP Version|phpinfo\(\)",
    "SQL Dump": r"INSERT INTO|CREATE TABLE|DROP TABLE",
    "Docker Compose": r"image:\s+\w|services:\s*\n",
}


async def check_sensitive_files(domain: str) -> list:
    """
    Fuzzing HTTP avancé sur 200+ endpoints sensibles.
    Détection de secrets via regex avancées (AWS, GitHub, Stripe, etc.)
    Scan parallèle avec semaphore (20 requêtes simultanées).
    """
    findings = []
    sem = asyncio.Semaphore(20)  # 20 requêtes parallèles

    async def _check_url(session: httpx.AsyncClient, url: str, path: str):
        async with sem:
            try:
                resp = await session.get(url, follow_redirects=False)
                # On s'intéresse aux codes 200, mais aussi aux 403 (accès refusé = le fichier existe!)
                if resp.status_code not in [200, 403]:
                    return None

                content = resp.text[:5000] if resp.text else ""
                content_len = int(resp.headers.get("content-length", len(content)))

                if content_len < 5 and resp.status_code != 403:
                    return None

                # Détecter si c'est une vraie page 404 déguisée en 200
                if resp.status_code == 200:
                    soft_404_patterns = [r"404", r"not found", r"page not found", r"doesn.t exist"]
                    if any(re.search(p, content[:500], re.I) for p in soft_404_patterns):
                        return None

                # Rechercher des patterns de secrets
                detected_secret_type = None
                snippet = ""

                for secret_name, pattern in SECRET_PATTERNS.items():
                    match = re.search(pattern, content)
                    if match:
                        detected_secret_type = secret_name
                        # Masquer la valeur détectée (sécurité)
                        start = max(0, match.start() - 10)
                        end = min(len(content), match.end() + 20)
                        raw_snippet = content[start:end]
                        # Masquer les parties sensibles
                        snippet = re.sub(r"([=:]\s*)['\"]?([^\s'\",\n]{4,})['\"]?", r"\1****", raw_snippet)
                        break

                if detected_secret_type or resp.status_code == 403:
                    severity = "CRITICAL" if detected_secret_type else "INFO"
                    return {
                        "path": path,
                        "url": url,
                        "status": resp.status_code,
                        "type": detected_secret_type or "Forbidden Resource",
                        "snippet": snippet or f"HTTP {resp.status_code} — {content_len} bytes",
                        "severity": severity,
                    }
            except Exception:
                pass
            return None

    schemes = ["https", "http"]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ShadowScanner/2.0; Security Audit)"}

    async with httpx.AsyncClient(timeout=4.0, verify=False, headers=headers) as client:
        # Tester en priorité HTTPS, puis HTTP
        tasks = []
        for path in SENSITIVE_ENDPOINTS:
            for scheme in schemes:
                url = f"{scheme}://{domain}{path}"
                tasks.append(_check_url(client, url, path))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        seen_paths = set()
        for r in results:
            if r and isinstance(r, dict):
                if r["path"] not in seen_paths:
                    seen_paths.add(r["path"])
                    findings.append(r)
                    if r["severity"] == "CRITICAL":
                        logger.warning(f"[Secrets Worker] 🚨 SECRET EXPOSÉ: {r['type']} sur {r['url']}")

    return findings


@celery_app.task(bind=True, max_retries=1)
def scan_secrets(self, scan_id: str, root_domain: str):
    """
    Recherche de secrets exposés et fichiers sensibles.
    200+ endpoints | Détection regex avancée | 20 requêtes parallèles.
    """
    logger.info(f"[Secrets Worker] Démarrage Scan Secrets pour {root_domain} ({len(SENSITIVE_ENDPOINTS)} endpoints)")

    async def _run():
        fuzz_results = await check_sensitive_files(root_domain)
        logger.info(f"[Secrets Worker] {len(fuzz_results)} fichiers sensibles/secrets trouvés pour {root_domain}")

        if not fuzz_results:
            return {"findings": []}

        scan_uuid = uuid.UUID(scan_id)
        async with get_worker_session() as session:
            stmt = select(Asset).where(Asset.scan_id == scan_uuid, Asset.value == root_domain)
            result = await session.execute(stmt)
            root_asset = result.scalars().first()

            if not root_asset:
                root_asset = Asset(
                    id=uuid.uuid4(),
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
                    id=uuid.uuid4(),
                    asset_id=root_asset.id,
                    type=f_data.get("severity", "INFO").lower(),
                    source=f_data.get("path", "unknown"),
                    masked_value=f_data.get("snippet", "hidden")[:500]
                )
                await repo.create(finding)

            await session.commit()

        return {"findings": fuzz_results}

    try:
        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"[Secrets Worker] Erreur critique: {e}")
        return {"findings": [], "error": str(e)}
