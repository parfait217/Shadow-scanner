from typing import AsyncGenerator, Callable
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import decode_access_token
from app.core.exceptions import TokenInvalidError, TokenExpiredError, InsufficientRoleError

logger = logging.getLogger(__name__)

# =============================================================================
# Database Session
# =============================================================================
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI pour obtenir une session de BDD."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================================
# Redis — Seulement utilisé par certains endpoints
# =============================================================================
import redis.asyncio as aioredis

async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Dépendance FastAPI pour obtenir une connexion Redis."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


# =============================================================================
# Authentication & Role-Based Access Control (RBAC) (§7.3)
# =============================================================================

# OAuth2 scheme pour exiger le header Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class CurrentUser:
    def __init__(self, id: str, role: str):
        self.id = id
        self.role = role


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """Déduit l'utilisateur à partir de l'access token."""
    from jose import JWTError, jwt, ExpiredSignatureError

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role")
        if user_id is None or role is None:
            raise TokenInvalidError()
        return CurrentUser(id=user_id, role=role)
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise TokenInvalidError()


def require_role(required_role: str) -> Callable:
    """Créer une dépendance FastAPI pour vérifier le rôle d'un utilisateur."""
    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role != required_role:
            raise InsufficientRoleError()
        return current_user
    return role_checker

# Dépendance raccourcie pour les endpoints Admin
get_admin_user = require_role("admin")
