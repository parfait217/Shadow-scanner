from pydantic import BaseModel
from typing import Dict

class DashboardStats(BaseModel):
    total_projects: int
    total_assets: int
    total_vulnerabilities: int
    risk_score: float
    vulnerability_stats: Dict[str, int]  # e.g., {"critical": 0, "high": 2, ...}
