from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.fx_converter import FxConverter
from app.adapters.moomoo_adapter import MoomooAdapter
from app.api.routes import create_router
from app.config import get_settings
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository
from app.services.dashboard_service import DashboardService
from app.services.scheduler_service import start_daily_scheduler
from app.services.sync_service import SyncService


def create_app(database_path: Path | None = None, enable_scheduler: bool = False) -> FastAPI:
    settings = get_settings()
    repository = SQLiteSnapshotRepository(database_path or settings.database_path)
    repository.initialize()
    adapter = MoomooAdapter(FxConverter({"JPY": 1.0, "USD": 150.0, "HKD": 19.0}))
    sync_service = SyncService(settings=settings, adapter=adapter, repository=repository)
    dashboard_service = DashboardService(
        repository,
        manual_principal_jpy=settings.manual_principal_jpy,
    )

    app = FastAPI(title="Portfolio Dashboard")
    app.include_router(create_router(repository, dashboard_service, sync_service))
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse("app/static/index.html")

    if enable_scheduler:
        try:
            start_daily_scheduler(sync_service, settings.sync_hour, settings.sync_minute)
        except RuntimeError:
            pass

    return app


app = create_app(enable_scheduler=True)
