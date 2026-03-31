from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Employee

class EmployeeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, employee_id: UUID) -> Optional[Employee]:
        stmt = select(Employee).where(Employee.id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email_and_scan(self, email: str, scan_id: UUID) -> Optional[Employee]:
        stmt = select(Employee).where(Employee.email == email, Employee.scan_id == scan_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scan(self, scan_id: UUID, page: int = 1, limit: int = 50) -> list[Employee]:
        stmt = (
            select(Employee)
            .options(selectinload(Employee.breaches))
            .where(Employee.scan_id == scan_id)
            .order_by(Employee.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_by_scan(self, scan_id: UUID) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(Employee).where(Employee.scan_id == scan_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, employee: Employee) -> Employee:
        self.session.add(employee)
        await self.session.flush()
        return employee
