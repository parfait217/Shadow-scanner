from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.asset import Asset

class FindingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, finding_id: UUID) -> Optional[Finding]:
        stmt = select(Finding).where(Finding.id == finding_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scan(self, scan_id: UUID, page: int = 1, limit: int = 50) -> list[Finding]:
        stmt = (
            select(Finding)
            .join(Asset, Finding.asset_id == Asset.id)
            .where(Asset.scan_id == scan_id)
            .order_by(Finding.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_scan(self, scan_id: UUID) -> int:
        from sqlalchemy import func
        stmt = (
            select(func.count())
            .select_from(Finding)
            .join(Asset, Finding.asset_id == Asset.id)
            .where(Asset.scan_id == scan_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, finding: Finding) -> Finding:
        self.session.add(finding)
        await self.session.flush()
        return finding
