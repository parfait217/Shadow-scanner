from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, constr


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=200)
    root_domain: str = Field(
        ...,
        max_length=255,
        pattern=r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$",
        description="Must be a valid FQDN (RG-P02)"
    )
    scan_frequency: Optional[Literal["24h", "48h", "72h", "7d"]] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    scan_frequency: Optional[Literal["24h", "48h", "72h", "7d"]] = None
    alert_threshold: Optional[int] = Field(None, ge=0, le=100)


class ProjectScheduleUpdate(BaseModel):
    frequency: Optional[Literal["24h", "48h", "72h", "7d"]] = None


class ProjectResponse(ProjectBase):
    id: UUID
    user_id: UUID
    status: str
    risk_score: float
    alert_threshold: int
    next_scan_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
