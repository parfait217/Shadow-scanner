import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Pool global de connexions HTTPX pour réutiliser les sockets TLS (performances)
DEFAULT_TIMEOUT = 10.0
MAX_CONNECTIONS = 100

limits = httpx.Limits(max_keepalive_connections=50, max_connections=MAX_CONNECTIONS)
client = httpx.AsyncClient(limits=limits, timeout=DEFAULT_TIMEOUT, verify=False)  # verify=False pour certains scans OSINT

async def fetch_json(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Any]:
    """Fait une requête GET et retourne le JSON, gère les erreurs silencieusement."""
    try:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"Erreur HTTP {e.response.status_code} sur {url}")
        return None
    except httpx.RequestError as e:
        logger.warning(f"Erreur de connexion sur {url}: {e}")
        return None

async def fetch_text(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
    """Fait une requête GET et retourne le texte brut."""
    try:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"Erreur fetch_text sur {url}: {e}")
        return None

async def close_client():
    await client.aclose()
