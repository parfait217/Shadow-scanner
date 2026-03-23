import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Service(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    port = Column(Integer, nullable=False)
    protocol = Column(String(20), nullable=False)
    product = Column(String(100), nullable=True)
    version = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    asset = relationship("Asset", back_populates="services")
    vulnerabilities = relationship("Vulnerability", back_populates="service", cascade="all, delete-orphan")
