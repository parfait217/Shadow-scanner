from uuid import UUID
from typing import Tuple

from app.core.exceptions import MaxProjectsExceededError, ProjectConflictError, ProjectNotFoundError
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectScheduleUpdate, ProjectResponse


class ProjectService:
    def __init__(self, project_repo: ProjectRepository):
        self.project_repo = project_repo

    async def create_project(self, user_id: UUID, project_in: ProjectCreate) -> ProjectResponse:
        # RG-P01 : Max 10 projets actifs par analyste
        active_count = await self.project_repo.count_active_projects(user_id)
        if active_count >= 10:
            raise MaxProjectsExceededError()

        # RG-P03 : Un domaine ne peut être dans deux projets du même utilisateur
        existing = await self.project_repo.get_by_domain_for_user(user_id, project_in.root_domain)
        if existing:
            raise ProjectConflictError(domain=project_in.root_domain)

        # Création (RG-P02 validée par le schéma Pydantic)
        project = Project(
            user_id=user_id,
            name=project_in.name,
            root_domain=project_in.root_domain,
            scan_frequency=project_in.scan_frequency
        )
        project = await self.project_repo.create(project)
        return ProjectResponse.model_validate(project)

    async def get_project(self, project_id: UUID, user_id: UUID, role: str) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project or (project.user_id != user_id and role != "admin"):
            raise ProjectNotFoundError(str(project_id))
        return ProjectResponse.model_validate(project)

    async def list_user_projects(self, user_id: UUID) -> list[ProjectResponse]:
        projects = await self.project_repo.list_by_user(user_id)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def archive_project(self, project_id: UUID, user_id: UUID, role: str) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project or (project.user_id != user_id and role != "admin"):
            raise ProjectNotFoundError(str(project_id))
        
        project.status = "archived"
        # La session sqlalchemy va commit via get_db dependency
        return ProjectResponse.model_validate(project)
