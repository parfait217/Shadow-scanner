from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def list_users(self, page: int, limit: int, search: Optional[str] = None) -> Tuple[list[User], int]:
        stmt = select(User)
        if search:
            stmt = stmt.where(or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            ))
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.execute(count_stmt)
        total_count = total.scalar_one()

        # Pagination
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await self.session.execute(stmt)
        
        return list(result.scalars().all()), total_count
