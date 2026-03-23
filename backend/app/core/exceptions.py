from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class ShadowScannerException(HTTPException):
    """Exception de base pour Shadow-Scanner avec format structuré (§8.1)."""
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: Optional[Any] = None
    ):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "detail": detail})


# =============================================================================
# Codes d'Erreur Métier (§8.2)
# =============================================================================

class InvalidDomainFormatError(ShadowScannerException):
    def __init__(self, domain: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_DOMAIN_FORMAT",
            message="Le domaine soumis n'est pas un FQDN valide.",
            detail=f"domain: {domain}"
        )


class TokenExpiredError(ShadowScannerException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_EXPIRED",
            message="L'access token a expiré."
        )


class TokenInvalidError(ShadowScannerException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="Token JWT malformé ou signature invalide."
        )


class InsufficientRoleError(ShadowScannerException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_ROLE",
            message="Rôle insuffisant pour accéder à cette ressource."
        )


class ScanRunningError(ShadowScannerException):
    def __init__(self, scan_id: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SCAN_RUNNING",
            message="Impossible de supprimer un scan en cours.",
            detail=f"scan_id: {scan_id}"
        )


class ProjectNotFoundError(ShadowScannerException):
    def __init__(self, project_id: str):
        super().__init__(
            # Retourne 404 plutôt que 403 même si ça existe mais n'appartient pas au user (§7.3)
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROJECT_NOT_FOUND",
            message="Projet inexistant ou n'appartenant pas à l'utilisateur.",
            detail=f"project_id: {project_id}"
        )


class ScanNotFoundError(ShadowScannerException):
    def __init__(self, scan_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SCAN_NOT_FOUND",
            message="Scan inexistant ou n'appartenant pas à l'utilisateur.",
            detail=f"scan_id: {scan_id}"
        )


class ReportNotGeneratedError(ShadowScannerException):
    def __init__(self, scan_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REPORT_NOT_GENERATED",
            message="Rapport PDF non encore généré.",
            detail=f"scan_id: {scan_id}"
        )


class ScanAlreadyRunningError(ShadowScannerException):
    def __init__(self, project_id: str, scan_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="SCAN_ALREADY_RUNNING",
            message="Un scan est déjà en cours pour ce projet.",
            detail=f"project_id: {project_id}, running_scan_id: {scan_id}"
        )


class ScanNotDoneError(ShadowScannerException):
    def __init__(self, scan_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="SCAN_NOT_DONE",
            message="Scan non terminé — impossible de générer le rapport.",
            detail=f"scan_id: {scan_id}"
        )


class UserConflictError(ShadowScannerException):
    def __init__(self, field: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="USER_CONFLICT",
            message="Un utilisateur avec cette information existe déjà.",
            detail=f"field: {field}"
        )


class ProjectConflictError(ShadowScannerException):
    def __init__(self, domain: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="PROJECT_CONFLICT",
            message="Un domaine ne peut être dans deux projets du même utilisateur (RG-P03).",
            detail=f"domain: {domain}"
        )


class MaxProjectsExceededError(ShadowScannerException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="MAX_PROJECTS_EXCEEDED",
            message="Max 10 projets actifs simultanés par analyste (RG-P01)."
        )
