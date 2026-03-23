import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Employee(Base):
    """Employés découverts (OSINT) potentiellement présents dans des brèches."""
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=True)
    breach_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scan = relationship("Scan", back_populates="employees")
    breaches = relationship("Breach", back_populates="employee", cascade="all, delete-orphan")
