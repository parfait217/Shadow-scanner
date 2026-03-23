from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., max_length=150)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Mot de passe fort requis")


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=150)
    webhook_url: Optional[str] = Field(None, max_length=500)


class UserUpdatePassword(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserUpdateNotifications(BaseModel):
    email_alerts: Optional[bool] = None
    webhook_url: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    role: str
    is_active: bool
    webhook_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    tokens: TokenResponse
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str
