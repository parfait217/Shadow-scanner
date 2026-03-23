from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, CurrentUser
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserUpdate, UserUpdatePassword, UserUpdateNotifications

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    repo = UserRepository(session)
    user = await repo.get_by_id(current_user.id)
    return UserResponse.model_validate(user)

@router.put("/me", response_model=UserResponse)
async def update_me(
    user_in: UserUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    repo = UserRepository(session)
    user = await repo.get_by_id(current_user.id)
    
    if user_in.full_name:
        user.full_name = user_in.full_name
    if user_in.webhook_url:
        user.webhook_url = user_in.webhook_url
        
    await session.flush()
    return UserResponse.model_validate(user)

@router.put("/me/password")
async def update_password(
    passwords: UserUpdatePassword,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    # TODO: Appel métier au UserService pour vérifier hash et set_password
    pass

@router.put("/me/notifications", response_model=UserResponse)
async def update_notifications(
    notifs: UserUpdateNotifications,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    repo = UserRepository(session)
    user = await repo.get_by_id(current_user.id)
    if notifs.webhook_url is not None:
        user.webhook_url = notifs.webhook_url
    await session.flush()
    return UserResponse.model_validate(user)
