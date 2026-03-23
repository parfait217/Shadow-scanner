from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, CurrentUser
from app.repositories.project_repository import ProjectRepository
from app.repositories.scan_repository import ScanRepository
from app.services.scan_service import ScanService
from app.schemas.scan import ScanResponse

router = APIRouter()

def get_scan_service(session: AsyncSession = Depends(get_db)) -> ScanService:
    return ScanService(ScanRepository(session), ProjectRepository(session))

@router.post("/projects/{id}/scans", status_code=status.HTTP_201_CREATED)
async def launch_scan(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    scan_service: ScanService = Depends(get_scan_service)
):
    return await scan_service.launch_scan(id, UUID(current_user.id), current_user.role)

@router.get("/projects/{id}/scans")
async def list_scans(
    id: UUID,
    page: int = 1,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
    scan_service: ScanService = Depends(get_scan_service)
):
    items, total = await scan_service.get_history(id, UUID(current_user.id), current_user.role, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}

@router.get("/scans/{id}", response_model=ScanResponse)
async def get_scan(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    scan_service: ScanService = Depends(get_scan_service)
):
    return await scan_service.get_scan(id, UUID(current_user.id), current_user.role)

@router.delete("/scans/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    scan_service: ScanService = Depends(get_scan_service)
):
    await scan_service.delete_scan(id, UUID(current_user.id), current_user.role)

@router.post("/scans/{id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_scan(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Annuler un scan en cours (stub)."""
    return {"message": "Scan annulé."}

@router.get("/scans/{id}/download")
async def download_scan_json(
    id: UUID,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Exporte les résultats bruts en JSON (stub)."""
    return {"scan_id": id, "data": []}
