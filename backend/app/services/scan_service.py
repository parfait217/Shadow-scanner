from uuid import UUID
from datetime import datetime, timezone

from app.core.exceptions import ProjectNotFoundError, ScanAlreadyRunningError, ScanNotFoundError, ScanRunningError
from app.models.scan import Scan
from app.repositories.scan_repository import ScanRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.scan import ScanResponse

class ScanService:
    def __init__(self, scan_repo: ScanRepository, project_repo: ProjectRepository):
        self.scan_repo = scan_repo
        self.project_repo = project_repo

    async def launch_scan(self, project_id: UUID, user_id: UUID, role: str) -> dict:
        # Vérif accès projet
        project = await self.project_repo.get_by_id(project_id)
        if not project or (project.user_id != user_id and role != "admin"):
            raise ProjectNotFoundError(str(project_id))

        # RG-S01 : Un seul scan actif par projet
        active_scan = await self.scan_repo.get_active_scan_for_project(project_id)
        if active_scan:
            raise ScanAlreadyRunningError(str(project_id), str(active_scan.id))

        # Création scan
        scan = Scan(
            project_id=project_id,
            status="pending",
            trigger="manual",
            started_at=datetime.now(timezone.utc)
        )
        scan = await self.scan_repo.create(scan)

        # Appel au cluster Celery (exécution non-bloquante via RabbitMQ/Redis)
        from app.workers.orchestrator import run_project_scan
        run_project_scan.delay(str(scan.id), str(project.id), project.root_domain)

        return {"scan_id": str(scan.id)}

    async def get_scan(self, scan_id: UUID, user_id: UUID, role: str) -> ScanResponse:
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ScanNotFoundError(str(scan_id))
            
        # Il faut vérifier le projet pour valider le propriétaire
        project = await self.project_repo.get_by_id(scan.project_id)
        if not project or (project.user_id != user_id and role != "admin"):
            raise ScanNotFoundError(str(scan_id))

        return ScanResponse.model_validate(scan)

    async def get_history(self, project_id: UUID, user_id: UUID, role: str, page: int, limit: int) -> tuple[list[ScanResponse], int]:
        project = await self.project_repo.get_by_id(project_id)
        if not project or (project.user_id != user_id and role != "admin"):
            raise ProjectNotFoundError(str(project_id))

        scans, total = await self.scan_repo.list_by_project(project_id, page, limit)
        return [ScanResponse.model_validate(s) for s in scans], total

    async def delete_scan(self, scan_id: UUID, user_id: UUID, role: str) -> None:
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ScanNotFoundError(str(scan_id))
            
        project = await self.project_repo.get_by_id(scan.project_id)
        if not project or (project.user_id != user_id and role != "admin"):
            raise ScanNotFoundError(str(scan_id))

        # RG-S02 : Suppression scan uniquement si done/error
        if scan.status not in ("done", "error", "partial"):
            raise ScanRunningError(str(scan_id))

        await self.scan_repo.delete(scan)
