from uuid import UUID
from fastapi import APIRouter, Depends, status
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, CurrentUser, get_db
from app.models.scan import Scan
from app.models.asset import Asset
from app.models.service import Service
from app.models.vulnerability import Vulnerability
from app.models.finding import Finding
from app.models.project import Project

router = APIRouter()

# --- Assets ---
@router.get("/{id}/assets")
async def list_assets(
    id: UUID,
    page: int = 1,
    limit: int = 50,
    type: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Liste tous les actifs découverts pour un scan donné."""
    # Vérifier que le scan appartient à l'utilisateur
    scan = await db.execute(
        select(Scan)
        .join(Project, Scan.project_id == Project.id)
        .where(Scan.id == id, Project.user_id == UUID(current_user.id))
    )
    scan_obj = scan.scalars().first()
    if not scan_obj:
        return {"items": [], "total": 0}

    stmt = select(Asset).where(Asset.scan_id == id)
    if type:
        stmt = stmt.where(Asset.type == type)

    # Count
    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    # Paginated results with services eager-loaded
    stmt = stmt.options(selectinload(Asset.services).selectinload(Service.vulnerabilities))
    stmt = stmt.order_by(Asset.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    assets = result.scalars().unique().all()

    items = []
    for a in assets:
        services_list = []
        for s in a.services:
            vulns_list = [
                {
                    "id": str(v.id),
                    "cve_id": v.cve_id,
                    "cvss_score": float(v.cvss_score) if v.cvss_score else None,
                    "severity": v.severity,
                }
                for v in s.vulnerabilities
            ]
            services_list.append({
                "id": str(s.id),
                "port": s.port,
                "protocol": s.protocol,
                "product": s.product,
                "version": s.version,
                "vulnerabilities": vulns_list,
            })

        items.append({
            "id": str(a.id),
            "type": a.type,
            "value": a.value,
            "is_alive": a.is_alive,
            "ip": a.ip,
            "country": a.country,
            "isp": a.isp,
            "services": services_list,
            "services_count": len(services_list),
            "vulns_count": sum(len(s["vulnerabilities"]) for s in services_list),
        })

    return {"items": items, "total": total}


@router.get("/{id}/assets/{asset_id}")
async def get_asset(id: UUID, asset_id: UUID, current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Détails d'un actif précis."""
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.services).selectinload(Service.vulnerabilities))
        .where(Asset.id == asset_id, Asset.scan_id == id)
    )
    asset = result.scalars().first()
    if not asset:
        return {}
    return {
        "id": str(asset.id),
        "type": asset.type,
        "value": asset.value,
        "is_alive": asset.is_alive,
        "ip": asset.ip,
        "country": asset.country,
        "isp": asset.isp,
    }


# --- Vulnérabilités ---
@router.get("/{id}/vulnerabilities")
async def list_vulnerabilities(
    id: UUID, page: int = 1, limit: int = 50, severity: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Liste les vulnérabilités du scan."""
    stmt = (
        select(Vulnerability)
        .join(Service, Vulnerability.service_id == Service.id)
        .join(Asset, Service.asset_id == Asset.id)
        .where(Asset.scan_id == id)
    )
    if severity:
        stmt = stmt.where(Vulnerability.severity == severity)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    stmt = stmt.order_by(Vulnerability.cvss_score.desc().nullslast()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    vulns = result.scalars().all()

    items = [
        {
            "id": str(v.id),
            "cve_id": v.cve_id,
            "cvss_score": float(v.cvss_score) if v.cvss_score else None,
            "severity": v.severity,
        }
        for v in vulns
    ]
    return {"items": items, "total": total}


# --- Findings (Secrets) ---
@router.get("/{id}/findings")
async def list_findings(
    id: UUID, page: int = 1, limit: int = 50, type: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Liste les secrets/défauts de config (Findings)."""
    stmt = select(Finding).join(Asset, Finding.asset_id == Asset.id).where(Asset.scan_id == id)
    if type:
        stmt = stmt.where(Finding.type == type)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    stmt = stmt.order_by(Finding.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    findings = result.scalars().all()

    items = [
        {
            "id": str(f.id),
            "type": f.type,
            "masked_value": f.masked_value,
            "source": f.source,
        }
        for f in findings
    ]
    return {"items": items, "total": total}


@router.get("/{id}/findings/{finding_id}")
async def get_finding(id: UUID, finding_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Détails d'un secret précis."""
    return {}

@router.put("/{id}/findings/{finding_id}/status")
async def update_finding_status(id: UUID, finding_id: UUID, status: str, current_user: CurrentUser = Depends(get_current_user)):
    """Modifier le statut d'un secret (ex: false_positive)."""
    return {}

# --- Comparaison / Score / Topology (stubs) ---
@router.get("/{id}/diff")
async def get_scan_diff(id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    return {}

@router.get("/{id}/score")
async def get_scan_score(id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    return {}

@router.get("/{id}/topology")
async def get_scan_topology(id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    return {"nodes": [], "links": []}
