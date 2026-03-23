from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, CurrentUser
from app.repositories.project_repository import ProjectRepository
from app.services.project_service import ProjectService
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, ProjectScheduleUpdate

router = APIRouter()

def get_project_service(session: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(session))


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: CurrentUser = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    return await project_service.list_user_projects(UUID(current_user.id))

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: CurrentUser = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    return await project_service.create_project(UUID(current_user.id), project_in)

@router.get("/{id}", response_model=ProjectResponse)
async def get_project(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    return await project_service.get_project(id, UUID(current_user.id), current_user.role)

@router.put("/{id}/archive", response_model=ProjectResponse)
async def archive_project(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    return await project_service.archive_project(id, UUID(current_user.id), current_user.role)

@router.put("/{id}", response_model=ProjectResponse)
async def update_project(
    id: UUID,
    project_update: ProjectUpdate,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Modifie les paramètres généraux d'un projet (stub)."""
    pass

@router.put("/{id}/schedule", response_model=ProjectResponse)
async def update_project_schedule(
    id: UUID,
    schedule_update: ProjectScheduleUpdate,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Modifie la fréquence des scans liés au projet (stub)."""
    pass

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Supprime définitivement un projet et ses données (stub)."""
    pass
