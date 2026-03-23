from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Scan(Base):
    __tablename__ = "scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")
    trigger = Column(String(20), default="manual")
    risk_score = Column(Numeric(5, 2), nullable=True)
    assets_count = Column(Integer, default=0)
    vulns_count = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="scans")
    assets = relationship("Asset", back_populates="scan", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="scan", cascade="all, delete-orphan")

# Création de l'index sur scans(project_id, status)
Index('idx_scans_project_status', Scan.project_id, Scan.status)
