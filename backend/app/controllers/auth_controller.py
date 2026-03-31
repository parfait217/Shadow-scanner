from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.dependencies import get_db, get_redis, get_current_user, CurrentUser
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserResponse, LoginResponse, RefreshTokenRequest, TokenResponse

router = APIRouter()

def get_auth_service(
    session: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis)
) -> AuthService:
    return AuthService(UserRepository(session), redis_client)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Créer un compte."""
    return await auth_service.register_user(user_in)

@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Connexion avec nom d'utilisateur (email) et mot de passe."""
    return await auth_service.login(form_data.username, form_data.password)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Pas encore totalement implémenté (Phase 1 basic auth test)."""
    # TODO
    pass

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: RefreshTokenRequest,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Invalide le refresh token."""
    await auth_service.logout(current_user.id, request.refresh_token)

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(email: str):
    """Envoi un lien de réinitialisation (stub)."""
    return {"message": "Si l'email existe, un lien a été envoyé."}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(token: str, new_password: str):
    """Réinitialise le mot de passe avec le token fourni (stub)."""
    return {"message": "Mot de passe réinitialisé."}
