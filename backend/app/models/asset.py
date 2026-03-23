from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)  # 'subdomain', 'ip'
    value = Column(String(255), nullable=False)
    is_alive = Column(Boolean, default=False)
    ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scan = relationship("Scan", back_populates="assets")
    services = relationship("Service", back_populates="asset", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="asset", cascade="all, delete-orphan")

# Index de performances
Index('idx_assets_scan_id', Asset.scan_id)
Index('idx_assets_ip', Asset.ip)
