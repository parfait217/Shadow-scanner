import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Breach(Base):
    """Résultat HaveIBeenPwned pour un employé."""
    __tablename__ = "breaches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    breach_name = Column(String(200), nullable=False)
    date = Column(DateTime, nullable=True)
    data_types = Column(String(500), nullable=True)  # ex: "Email, Passwords, Names"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    employee = relationship("Employee", back_populates="breaches")
