from uuid import UUID
from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, CurrentUser

router = APIRouter()

@router.get("/alerts")
async def list_alerts(
    project_id: UUID = None,
    page: int = 1,
    limit: int = 50,
    is_read: bool = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lister les alertes générées par le Diffing."""
    return {"items": [], "total": 0}

@router.get("/alerts/{id}")
async def get_alert(id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Détail clair d'une alerte spécifique."""
    return {}

@router.put("/alerts/{id}/read")
async def mark_alert_read(id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Marquer une alerte comme lue."""
    return {"success": True}

@router.put("/alerts/read-all")
async def mark_all_alerts_read(project_id: UUID = None, current_user: CurrentUser = Depends(get_current_user)):
    """Marquer toutes les alertes comme lues d'un coup."""
    return {"success": True}

@router.post("/alerts/test-webhook", status_code=status.HTTP_200_OK)
async def test_webhook(current_user: CurrentUser = Depends(get_current_user)):
    """Envoyer une alerte de test sur le Webhook Discord/Slack configuré par l'utilisateur."""
    return {"success": True}
