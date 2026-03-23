from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_domain_for_user(self, user_id: UUID, domain: str) -> Optional[Project]:
        stmt = select(Project).where(Project.user_id == user_id, Project.root_domain == domain)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_active_projects(self, user_id: UUID) -> int:
        stmt = select(func.count()).select_from(Project).where(
            Project.user_id == user_id,
            Project.status != "archived"
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_by_user(self, user_id: UUID) -> list[Project]:
        stmt = select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.flush()
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
