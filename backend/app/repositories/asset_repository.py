from typing import Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_scan(self, scan_id: UUID, page: int, limit: int, severity: str = None) -> Tuple[list[Asset], int]:
        stmt = select(Asset).where(Asset.scan_id == scan_id)
        
        # Filtre sur la sévérité (par exemple via jointure vulnerabilities si demandé plus tard)
        # Pour Phase 1 : retourne simple paginate.
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.execute(count_stmt)
        total_count = total.scalar_one()

        stmt = stmt.order_by(Asset.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await self.session.execute(stmt)
        
        return list(result.scalars().all()), total_count

    async def create(self, asset: Asset) -> Asset:
        self.session.add(asset)
        await self.session.flush()
        return asset
