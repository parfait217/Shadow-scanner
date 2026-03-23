import redis.asyncio as aioredis
from uuid import UUID

from app.core.exceptions import UserConflictError, TokenInvalidError
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    store_refresh_token,
    revoke_refresh_token,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserResponse, LoginResponse, TokenResponse


class AuthService:
    def __init__(self, user_repo: UserRepository, redis_client: aioredis.Redis):
        self.user_repo = user_repo
        self.redis_client = redis_client

    async def register_user(self, user_in: UserCreate) -> UserResponse:
        # 1. Vérifie si l'email existe déjà
        existing = await self.user_repo.get_by_email(user_in.email)
        if existing:
            raise UserConflictError(field="email")

        # 2. Hashage du mot de passe
        hashed_password = hash_password(user_in.password)

        # 3. Création utilisateur
        user = User(
            email=user_in.email,
            password_hash=hashed_password,
            full_name=user_in.full_name,
            role="analyst"  # Analyste par défaut
        )
        user = await self.user_repo.create(user)
        return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> LoginResponse:
        # 1. Récupère user
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise TokenInvalidError()  # 401 si credentials invalides

        if not user.is_active:
            raise TokenInvalidError()  # Utilisateur désactivé

        # 2. Génère tokens
        access_token = create_access_token(str(user.id), user.role)
        refresh_token = create_refresh_token(str(user.id))

        # 3. Stocke refresh token dans Redis
        await store_refresh_token(self.redis_client, str(user.id), refresh_token)

        # TODO: Mettre à jour last_login

        tokens = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=15 * 60  # 15 minutes
        )
        return LoginResponse(tokens=tokens, user=UserResponse.model_validate(user))

    async def logout(self, user_id: str, refresh_token: str) -> None:
        """Révoque le refresh token en le supprimant de Redis."""
        await revoke_refresh_token(self.redis_client, user_id, refresh_token)
