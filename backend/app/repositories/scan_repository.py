from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan


class ScanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, scan_id: UUID) -> Optional[Scan]:
        stmt = select(Scan).where(Scan.id == scan_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_scan_for_project(self, project_id: UUID) -> Optional[Scan]:
        stmt = select(Scan).where(
            Scan.project_id == project_id,
            Scan.status.in_(["pending", "running"])
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_project(self, project_id: UUID, page: int, limit: int) -> Tuple[list[Scan], int]:
        stmt = select(Scan).where(Scan.project_id == project_id)
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.execute(count_stmt)
        total_count = total.scalar_one()

        stmt = stmt.order_by(Scan.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await self.session.execute(stmt)
        
        return list(result.scalars().all()), total_count

    async def create(self, scan: Scan) -> Scan:
        self.session.add(scan)
        await self.session.flush()
        return scan

    async def delete(self, scan: Scan) -> None:
        await self.session.delete(scan)
