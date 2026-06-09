from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.models.snapshots import SymbolCategoryOverride, ThemeMapping
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository
from app.services.dashboard_service import DashboardService
from app.services.sync_service import SyncService


class ThemeMappingRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    theme: str = Field(min_length=1, max_length=50)
    display_name: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    enabled: bool = True


class SymbolCategoryOverrideRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    market: str = Field(default="US", min_length=1, max_length=16)
    sector_code: str | None = Field(default=None, max_length=64)
    industry_code: str | None = Field(default=None, max_length=64)
    theme_code: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=200)
    enabled: bool = True


def create_router(
    repository: SQLiteSnapshotRepository | None = None,
    dashboard_service: DashboardService | None = None,
    sync_service: SyncService | None = None,
    write_token: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def require_write_access(x_dashboard_token: str | None) -> None:
        if write_token and x_dashboard_token != write_token:
            raise HTTPException(status_code=401, detail="invalid dashboard token")

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/snapshots")
    def snapshots() -> list[dict[str, Any]]:
        return repository.list_batches() if repository else []

    @router.get("/dashboard")
    def dashboard(batch_id: int | None = None) -> dict[str, Any]:
        if dashboard_service is None:
            return {
                "summary": {},
                "positions": [],
                "treemap": [],
                "themes": [],
                "performance": [],
                "options": [],
                "asset_allocation": {"stock": 0.0, "option": 0.0, "cash": 0.0},
            }
        data = dashboard_service.get_dashboard(batch_id)
        if batch_id is not None and not data["summary"]:
            raise HTTPException(status_code=404, detail="snapshot batch not found")
        return data

    @router.post("/sync/run")
    def run_sync(x_dashboard_token: str | None = Header(default=None)) -> dict[str, Any]:
        require_write_access(x_dashboard_token)
        if sync_service is None:
            raise HTTPException(status_code=500, detail="sync service unavailable")
        if sync_service.is_running():
            raise HTTPException(status_code=409, detail="sync already running")
        try:
            result = sync_service.run_sync("manual")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return result.__dict__

    @router.get("/themes")
    def list_themes() -> list[dict[str, Any]]:
        return repository.list_theme_mappings() if repository else []

    @router.post("/themes")
    def upsert_theme(
        payload: ThemeMappingRequest,
        x_dashboard_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_write_access(x_dashboard_token)
        if repository is None:
            raise HTTPException(status_code=500, detail="repository unavailable")
        mapping = ThemeMapping(
            symbol=payload.symbol.upper(),
            theme=payload.theme,
            display_name=payload.display_name,
            color=payload.color,
            enabled=payload.enabled,
            updated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
        )
        return repository.upsert_theme_mapping(mapping)

    @router.get("/categories")
    def list_categories() -> list[dict[str, Any]]:
        return repository.list_category_definitions() if repository else []

    @router.get("/category-overrides")
    def list_category_overrides() -> list[dict[str, Any]]:
        return repository.list_symbol_category_overrides() if repository else []

    @router.post("/category-overrides")
    def upsert_category_override(
        payload: SymbolCategoryOverrideRequest,
        x_dashboard_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_write_access(x_dashboard_token)
        if repository is None:
            raise HTTPException(status_code=500, detail="repository unavailable")
        try:
            override = SymbolCategoryOverride(
                symbol=payload.symbol.upper(),
                market=payload.market.upper(),
                sector_code=payload.sector_code,
                industry_code=payload.industry_code,
                theme_code=payload.theme_code,
                reason=payload.reason,
                enabled=payload.enabled,
                updated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
            )
            return repository.upsert_symbol_category_override(override)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
