from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.dependencies import get_db, get_current_user, CurrentUser
from app.models.project import Project
from app.models.scan import Scan
from app.models.asset import Asset
from app.models.vulnerability import Vulnerability
from app.models.service import Service
from app.schemas.dashboard import DashboardStats

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = UUID(current_user.id)
    
    # 1. Nombre de projets
    projects_query = select(func.count(Project.id)).where(Project.user_id == user_id)
    projects_count = (await db.execute(projects_query)).scalar_one()
    
    # 2. Nombre d'actifs (liés aux scans des projets de l'user)
    # Jointure: User -> Project -> Scan -> Asset
    assets_query = select(func.count(Asset.id))\
        .join(Scan, Asset.scan_id == Scan.id)\
        .join(Project, Scan.project_id == Project.id)\
        .where(Project.user_id == user_id)
    assets_count = (await db.execute(assets_query)).scalar_one()
    
    # 3. Nombre de vulnérabilités
    # Jointure: User -> Project -> Scan -> Asset -> Service -> Vulnerability
    vulns_query = select(func.count(Vulnerability.id))\
        .join(Service, Vulnerability.service_id == Service.id)\
        .join(Asset, Service.asset_id == Asset.id)\
        .join(Scan, Asset.scan_id == Scan.id)\
        .join(Project, Scan.project_id == Project.id)\
        .where(Project.user_id == user_id)
    vulns_count = (await db.execute(vulns_query)).scalar_one()
    
    # 4. Stats par sévérité
    severity_query = select(Vulnerability.severity, func.count(Vulnerability.id))\
        .join(Service, Vulnerability.service_id == Service.id)\
        .join(Asset, Service.asset_id == Asset.id)\
        .join(Scan, Asset.scan_id == Scan.id)\
        .join(Project, Scan.project_id == Project.id)\
        .where(Project.user_id == user_id)\
        .group_by(Vulnerability.severity)
    
    severity_results = (await db.execute(severity_query)).all()
    vuln_stats = {row[0]: row[1] for row in severity_results}
    
    # 5. Risk Score basique (Somme des CVSS ou pondération par sévérité)
    # Pour l'instant on fait simple
    risk_score = 0.0
    if vulns_count > 0:
        # Score = (Critical * 10 + High * 7 + Medium * 4 + Low * 1) / total
        c = vuln_stats.get("critical", 0)
        h = vuln_stats.get("high", 0)
        m = vuln_stats.get("medium", 0)
        l = vuln_stats.get("low", 0)
        risk_score = min(100, (c * 20 + h * 10 + m * 5 + l * 2))

    return DashboardStats(
        total_projects=projects_count,
        total_assets=assets_count,
        total_vulnerabilities=vulns_count,
        risk_score=risk_score,
        vulnerability_stats=vuln_stats
    )
