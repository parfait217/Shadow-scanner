import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
import redis.asyncio as aioredis

from app.core.config import settings

# =============================================================================
# Argon2id — Hashage des mots de passe (§7.2)
# memory=65536 KB, iterations=3, parallelism=4
# =============================================================================
_argon2_hasher = PasswordHasher(
    memory_cost=65536,
    time_cost=3,
    parallelism=4,
)


def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2id."""
    return _argon2_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash Argon2id."""
    try:
        return _argon2_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# =============================================================================
# JWT — Access Token (§7.1)
# Payload : user_id, role, iat, exp uniquement
# =============================================================================
def create_access_token(user_id: str, role: str) -> str:
    """Crée un access token JWT HS256 valide 15 minutes."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Décode et valide un access token JWT. Retourne None si invalide."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# =============================================================================
# Refresh Token — Stockage dans Redis (§7.1)
# Hash SHA-256 du token → clé Redis avec TTL 7 jours
# =============================================================================
def _hash_refresh_token(token: str) -> str:
    """Hash SHA-256 du refresh token pour stockage Redis."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(user_id: str) -> str:
    """Crée un refresh token JWT valide 7 jours."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def store_refresh_token(redis_client: aioredis.Redis, user_id: str, token: str) -> None:
    """Stocke le hash SHA-256 du refresh token dans Redis avec TTL."""
    token_hash = _hash_refresh_token(token)
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    await redis_client.setex(f"refresh:{user_id}:{token_hash}", ttl, user_id)


async def validate_refresh_token(redis_client: aioredis.Redis, user_id: str, token: str) -> bool:
    """Vérifie que le refresh token est valide et présent dans Redis."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh" or payload.get("user_id") != user_id:
            return False
    except JWTError:
        return False

    token_hash = _hash_refresh_token(token)
    exists = await redis_client.exists(f"refresh:{user_id}:{token_hash}")
    return bool(exists)


async def revoke_refresh_token(redis_client: aioredis.Redis, user_id: str, token: str) -> None:
    """Révoque un refresh token (supprime de Redis)."""
    token_hash = _hash_refresh_token(token)
    await redis_client.delete(f"refresh:{user_id}:{token_hash}")
