from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScanBase(BaseModel):
    pass


class ScanResponse(ScanBase):
    id: UUID
    project_id: UUID
    status: str
    trigger: str
    risk_score: Optional[float] = None
    assets_count: int
    vulns_count: int
    findings_count: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScanDiff(BaseModel):
    new_assets: int
    new_vulns: int
    score_delta: float


class ScanScoreBreakdown(BaseModel):
    critical_cve_pts: float
    high_cve_pts: float
    secrets_pts: float
    breaches_pts: float
    headers_pts: float
    certificates_pts: float

class ScanScoreResponse(BaseModel):
    score: float
    breakdown: ScanScoreBreakdown
    history: list[dict]
