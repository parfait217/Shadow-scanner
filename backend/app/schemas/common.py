from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None

class ErrorResponse(BaseModel):
    """Format d'erreur standardisé de l'API (§8.1)."""
    error: ErrorDetail


class PaginationParams(BaseModel):
    page: int = 1
    limit: int = 50


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    total_pages: int
