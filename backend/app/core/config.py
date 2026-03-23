from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Base de données
    DATABASE_URL: str = "postgresql+asyncpg://shadow_scanner:shadow_secret@localhost:5432/shadow_scanner"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "change_me_in_production_min_32_chars_please!!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # APIs Externes — Tier 2 (clé requise)
    SHODAN_API_KEY: Optional[str] = None
    VIRUSTOTAL_API_KEY: Optional[str] = None
    SECURITYTRAILS_API_KEY: Optional[str] = None
    HIBP_API_KEY: Optional[str] = None
    GITHUB_API_KEY: Optional[str] = None
    NVD_API_KEY: Optional[str] = None

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
