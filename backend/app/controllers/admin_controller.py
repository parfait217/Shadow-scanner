from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_admin_user, CurrentUser
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse

router = APIRouter()

@router.get("/users")
async def list_users(
    page: int = 1,
    limit: int = 50,
    search: str = None,
    admin_user: CurrentUser = Depends(get_admin_user),
    session: AsyncSession = Depends(get_db)
):
    repo = UserRepository(session)
    users, total = await repo.list_users(page, limit, search)
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "limit": limit
    }

@router.put("/users/{id}/status")
async def update_user_status(id: str, is_active: bool, admin_user: CurrentUser = Depends(get_admin_user)):
    pass

@router.delete("/users/{id}")
async def delete_user(id: str, admin_user: CurrentUser = Depends(get_admin_user)):
    pass

@router.get("/stats")
async def global_stats(admin_user: CurrentUser = Depends(get_admin_user)):
    return {"stats": {"users": 0, "projects": 0, "scans": 0}}

@router.get("/logs")
async def global_logs(admin_user: CurrentUser = Depends(get_admin_user)):
    return {"logs": []}

@router.get("/config/apis")
async def get_api_config(admin_user: CurrentUser = Depends(get_admin_user)):
    return {"apis": []}

@router.put("/config/apis")
async def update_api_config(admin_user: CurrentUser = Depends(get_admin_user)):
    pass
