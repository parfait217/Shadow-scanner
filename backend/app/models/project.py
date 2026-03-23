from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    root_domain = Column(String(255), nullable=False)
    status = Column(String(20), default="active")
    scan_frequency = Column(String(20), nullable=True)
    risk_score = Column(Numeric(5, 2), default=0.0)
    alert_threshold = Column(Integer, default=10)
    next_scan_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="projects")
    scans = relationship("Scan", back_populates="project", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="project", cascade="all, delete-orphan")
