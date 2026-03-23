import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Finding(Base):
    """Secrets et fichiers sensibles détectés."""
    __tablename__ = "findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(100), nullable=False)  # secret, sensitive_file, etc.
    source = Column(String(100), nullable=False)  # github, server, etc.
    masked_value = Column(String(500), nullable=False)  # RG-F01: Ne jamais stocker en clair
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    asset = relationship("Asset", back_populates="findings")

# Index de performances
Index('idx_findings_asset_type', Finding.asset_id, Finding.type)
