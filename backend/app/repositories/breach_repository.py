from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.breach import Breach

class BreachRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, breach_id: UUID) -> Optional[Breach]:
        stmt = select(Breach).where(Breach.id == breach_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, breach: Breach) -> Breach:
        self.session.add(breach)
        await self.session.flush()
        return breach
