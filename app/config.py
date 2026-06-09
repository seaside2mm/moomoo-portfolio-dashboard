from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/portfolio.db")
    timezone: str = "Asia/Tokyo"
    base_currency: str = "JPY"
    manual_principal_jpy: float | None = 5_000_000
    sync_hour: int = 7
    sync_minute: int = 0
    cash_flow_lookback_days: int = 0
    cash_flow_request_interval_seconds: float = 0.2
    moomoo_host: str = "127.0.0.1"
    moomoo_port: int = 11111
    moomoo_password: str | None = None
    dashboard_api_token: str | None = None
    cors_allow_origins: tuple[str, ...] = ()


def get_settings() -> Settings:
    cors_allow_origins = tuple(
        item.strip()
        for item in os.environ.get("PORTFOLIO_CORS_ALLOW_ORIGINS", "").split(",")
        if item.strip()
    )
    return Settings(
        dashboard_api_token=os.environ.get("PORTFOLIO_DASHBOARD_API_TOKEN") or None,
        cors_allow_origins=cors_allow_origins,
    )
