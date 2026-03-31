import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import ShadowScannerException

# Initialisation du logging
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: Importer les routeurs (à faire dans la prochaine étape)
# from app.controllers import auth_controller, user_controller, ...

from fastapi.security import OAuth2PasswordBearer, HTTPBearer

# ... (reste du code)

app = FastAPI(
    title="Shadow-Scanner API",
    description="API pour attack surface management & OSINT",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

# Indiquer à Swagger d'utiliser Bearer Auth (plus simple pour copier-coller le token)
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.security import HTTPBearer
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # On force l'affichage du cadenas Bearer Auth
    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    # On l'applique par défaut à toutes les routes /api/
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if path.startswith("/api/"):
                openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}, {"OAuth2PasswordBearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les domaines React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Exception Handler Global (§8.1 Format Standard)
# =============================================================================
@app.exception_handler(ShadowScannerException)
async def shadow_scanner_exception_handler(request: Request, exc: ShadowScannerException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Erreur interne inattendue : {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Erreur interne inattendue.",
                "detail": str(exc) if settings.DEBUG else None
            }
        }
    )

from app.controllers import auth_controller, user_controller, project_controller, scan_controller, admin_controller, result_controller, report_controller, alert_controller, dashboard_controller

app.include_router(dashboard_controller.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(auth_controller.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(user_controller.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(project_controller.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(scan_controller.router, prefix="/api/v1", tags=["Scans"])
app.include_router(result_controller.router, prefix="/api/v1/scans", tags=["Scan Results"])
app.include_router(report_controller.router, prefix="/api/v1/scans", tags=["Scan Report"])
app.include_router(alert_controller.router, prefix="/api/v1", tags=["Alerts"])
app.include_router(admin_controller.router, prefix="/api/v1/admin", tags=["Admin"])

@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
