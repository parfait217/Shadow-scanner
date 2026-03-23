from uuid import UUID
from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.core.dependencies import get_current_user, CurrentUser

router = APIRouter()

@router.post("/{id}/report", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(id: UUID, format: str = "pdf", current_user: CurrentUser = Depends(get_current_user)):
    """Déclenche la génération asynchrone d'un rapport PDF ou CSV."""
    return {"status": "generating", "format": format}

@router.get("/{id}/report/download")
async def download_report(id: UUID, format: str = "pdf", current_user: CurrentUser = Depends(get_current_user)):
    """Télécharger le fichier PDF/CSV généré (si prêt)."""
    # En vrai, retourne un StreamingResponse ou FileResponse
    return Response(content=b"dummy_pdf_content", media_type="application/pdf")
