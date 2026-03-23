import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base

class Alert(Base):
    """Notification générée lors d'un changement (diffing)."""
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)  # ex: NEW_ASSET, NEW_VULNERABILITY
    severity = Column(String(20), nullable=False) # low, medium, high, critical
    title = Column(String(255), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="alerts")

# Index de performance : requêtes tableau de bord (alertes non lues)
Index('idx_alerts_project_read', Alert.project_id, Alert.is_read)
