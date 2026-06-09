# Portfolio Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI app that syncs real moomoo OpenD account data into SQLite snapshot batches and renders a single-page portfolio dashboard with editable theme mappings.

**Architecture:** Keep the app as one FastAPI service with static assets, a SQLite repository layer, adapter/service boundaries around moomoo OpenD, and a thin dashboard frontend. Implement the real OpenD sync loop first, then expose dashboard APIs, then add the frontend, and only after manual sync is stable add the daily `07:00` JST scheduler.

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, Pydantic v2, pytest, httpx TestClient, APScheduler, static HTML/CSS/JavaScript, moomoo OpenAPI client.

---

## Reference Documents

- `docs/requirements/2026-06-01-portfolio-dashboard-prd.md`
- `docs/requirements/2026-06-01-moomoo-data-requirements.md`
- `docs/requirements/2026-06-01-moomoo-sync-flow.md`
- `docs/requirements/2026-06-01-moomoo-adapter-mapping.md`
- `docs/requirements/2026-06-01-sqlite-schema.md`
- `docs/superpowers/specs/2026-06-01-portfolio-dashboard-design.md`

## Target File Structure

```text
pyproject.toml
README.md
app/
├─ __init__.py
├─ main.py
├─ config.py
├─ api/
│  ├─ __init__.py
│  └─ routes.py
├─ adapters/
│  ├─ __init__.py
│  ├─ fx_converter.py
│  ├─ moomoo_adapter.py
│  ├─ moomoo_client.py
│  └─ option_parser.py
├─ models/
│  ├─ __init__.py
│  ├─ dashboard.py
│  ├─ errors.py
│  └─ snapshots.py
├─ repositories/
│  ├─ __init__.py
│  └─ sqlite_snapshot_repo.py
├─ services/
│  ├─ __init__.py
│  ├─ dashboard_service.py
│  ├─ scheduler_service.py
│  └─ sync_service.py
├─ static/
│  ├─ index.html
│  ├─ styles.css
│  └─ dashboard.js
└─ migrations/
   └─ 001_init.sql
tests/
├─ test_api.py
├─ test_dashboard_service.py
├─ test_fx_converter.py
├─ test_moomoo_adapter.py
├─ test_option_parser.py
├─ test_scheduler_service.py
├─ test_sqlite_repo.py
└─ test_sync_service.py
```

## Implementation Tasks

### Task 1: Scaffold the FastAPI App

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `app/api/__init__.py`
- Create: `app/api/routes.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing health check test**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "portfolio.db"))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_api.py::test_health_endpoint_returns_ok -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `create_app`.

- [ ] **Step 3: Create the package and app bootstrap**

Create `pyproject.toml`:

```toml
[project]
name = "portfolio-dashboard"
version = "0.1.0"
description = "Local moomoo portfolio dashboard"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn>=0.30",
  "pydantic>=2.8",
  "apscheduler>=3.10",
  "moomoo-api>=9.4.5408"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "httpx>=0.27"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Create `app/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/portfolio.db")
    timezone: str = "Asia/Tokyo"
    base_currency: str = "JPY"
    sync_hour: int = 7
    sync_minute: int = 0
    moomoo_host: str = "127.0.0.1"
    moomoo_port: int = 11111
    moomoo_password: str | None = None


def get_settings() -> Settings:
    return Settings()
```

Create `app/api/routes.py`:

```python
from fastapi import APIRouter


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return router
```

Create `app/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI

from app.api.routes import create_router


def create_app(database_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Portfolio Dashboard")
    app.include_router(create_router())
    return app


app = create_app()
```

Create `README.md`:

```markdown
# Portfolio Dashboard

Local Web App for syncing moomoo OpenD account data into SQLite and viewing historical portfolio snapshots.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m uvicorn app.main:app --reload
```
```

Create empty package markers:

```text
app/__init__.py
app/api/__init__.py
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_api.py::test_health_endpoint_returns_ok -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml README.md app tests
git commit -m "chore: scaffold portfolio dashboard app"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 2: Add Snapshot and Error Models

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/snapshots.py`
- Create: `app/models/errors.py`
- Create: `app/models/dashboard.py`
- Test: `tests/test_moomoo_adapter.py`

- [ ] **Step 1: Write the failing model tests**

Create `tests/test_moomoo_adapter.py`:

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models.snapshots import OptionSnapshot, SnapshotBatch


def test_snapshot_batch_accepts_manual_status():
    batch = SnapshotBatch(
        snapshot_time=datetime(2026, 6, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        trigger_type="manual",
        status="success",
        base_currency="JPY",
        created_at=datetime(2026, 6, 1, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
    )
    assert batch.status == "success"


def test_option_snapshot_rejects_zero_strike():
    with pytest.raises(ValidationError):
        OptionSnapshot(
            batch_id=1,
            account_id="ACC-1",
            contract_code="US.NVDA260619P00150000",
            underlying="NVDA",
            option_type="PUT",
            side="SHORT",
            strike=0,
            expiry=date(2026, 6, 19),
            quantity=-1,
            premium=12.5,
            contract_multiplier=100,
            market_value_jpy=-187500,
            notional_exposure_jpy=2250000,
            risk_tag="short_put",
            parse_status="parsed",
            raw_contract='{"code":"US.NVDA260619P00150000"}',
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_moomoo_adapter.py -v
```

Expected: FAIL because `app.models.snapshots` does not exist.

- [ ] **Step 3: Add the Pydantic models**

Create `app/models/snapshots.py`:

```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Market = Literal["US", "HK", "OTHER"]
AssetType = Literal["stock", "etf", "option", "cash", "other"]
BatchStatus = Literal["success", "partial_success", "failed"]
TriggerType = Literal["manual", "scheduled"]
OptionType = Literal["CALL", "PUT"]
OptionSide = Literal["LONG", "SHORT"]
ParseStatus = Literal["parsed", "failed"]


class SnapshotBatch(BaseModel):
    id: int | None = None
    snapshot_time: datetime
    trigger_type: TriggerType
    status: BatchStatus
    base_currency: str = "JPY"
    total_assets_jpy: float | None = None
    total_pnl_jpy: float | None = None
    daily_pnl_jpy: float | None = None
    error_summary: str | None = None
    created_at: datetime


class AccountSnapshot(BaseModel):
    batch_id: int
    account_id: str = Field(min_length=1, max_length=64)
    account_name: str
    market: Market
    account_type: Literal["securities", "options", "margin"]
    currency: str
    total_assets_original: float | None = None
    total_assets_jpy: float | None = None
    cash_original: float | None = None
    cash_jpy: float | None = None
    total_pnl_original: float | None = None
    total_pnl_jpy: float | None = None
    daily_pnl_original: float | None = None
    daily_pnl_jpy: float | None = None
    margin_used_jpy: float | None = None
    financing_amount_jpy: float | None = None
    buying_power_jpy: float | None = None


class PositionSnapshot(BaseModel):
    batch_id: int
    account_id: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    raw_code: str = ""
    name: str = ""
    market: Market
    asset_type: AssetType
    currency: str
    quantity: float
    average_cost: float | None = None
    latest_price: float | None = None
    market_value_original: float | None = None
    market_value_jpy: float | None = None
    pnl_original: float | None = None
    pnl_jpy: float | None = None
    pnl_ratio: float | None = None
    position_ratio: float | None = None


class OptionSnapshot(BaseModel):
    batch_id: int
    account_id: str = Field(min_length=1, max_length=64)
    contract_code: str = Field(min_length=1)
    underlying: str | None = None
    option_type: OptionType | None = None
    side: OptionSide
    strike: float | None = None
    expiry: date | None = None
    quantity: float
    premium: float | None = None
    contract_multiplier: float = 100
    market_value_jpy: float | None = None
    notional_exposure_jpy: float | None = None
    risk_tag: str
    parse_status: ParseStatus
    raw_contract: str

    @field_validator("strike")
    @classmethod
    def validate_strike(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("strike must be greater than 0")
        return value

    @field_validator("contract_multiplier")
    @classmethod
    def validate_multiplier(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("contract_multiplier must be greater than 0")
        return value


class ExchangeRateSnapshot(BaseModel):
    batch_id: int
    from_currency: str
    to_currency: str = "JPY"
    rate: float
    source: str = "moomoo"
    rate_time: datetime

    @field_validator("rate")
    @classmethod
    def validate_rate(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("rate must be greater than 0")
        return value


class ThemeMapping(BaseModel):
    id: int | None = None
    symbol: str = Field(min_length=1, max_length=32)
    theme: str = Field(min_length=1, max_length=50)
    display_name: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    enabled: bool = True
    updated_at: datetime
```

Create `app/models/errors.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class SyncError(BaseModel):
    id: int | None = None
    batch_id: int | None = None
    account_id: str | None = None
    data_type: str
    error_code: str
    error_message: str
    raw_payload: str | None = None
    created_at: datetime
```

Create `app/models/dashboard.py`:

```python
from pydantic import BaseModel


class SnapshotListItem(BaseModel):
    batch_id: int
    snapshot_time: str
    trigger_type: str
    status: str
    total_assets_jpy: float | None = None
    total_pnl_jpy: float | None = None
    daily_pnl_jpy: float | None = None
    error_summary: str | None = None
```

Create `app/models/__init__.py`:

```python
from app.models.dashboard import SnapshotListItem
from app.models.errors import SyncError
from app.models.snapshots import (
    AccountSnapshot,
    ExchangeRateSnapshot,
    OptionSnapshot,
    PositionSnapshot,
    SnapshotBatch,
    ThemeMapping,
)

__all__ = [
    "AccountSnapshot",
    "ExchangeRateSnapshot",
    "OptionSnapshot",
    "PositionSnapshot",
    "SnapshotBatch",
    "SnapshotListItem",
    "SyncError",
    "ThemeMapping",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_moomoo_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/models tests/test_moomoo_adapter.py
git commit -m "feat: add snapshot and error models"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 3: Create SQLite Migration and Repository

**Files:**
- Create: `app/migrations/001_init.sql`
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/sqlite_snapshot_repo.py`
- Test: `tests/test_sqlite_repo.py`

- [ ] **Step 1: Write the failing repository tests**

Create `tests/test_sqlite_repo.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.errors import SyncError
from app.models.snapshots import AccountSnapshot, PositionSnapshot, SnapshotBatch, ThemeMapping
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository


def test_repo_initializes_and_lists_batches(tmp_path):
    repo = SQLiteSnapshotRepository(tmp_path / "portfolio.db")
    repo.initialize()

    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=1000000,
            total_pnl_jpy=100000,
            daily_pnl_jpy=5000,
            error_summary=None,
            created_at=datetime(2026, 6, 1, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    batches = repo.list_batches()
    assert batch_id == 1
    assert batches[0]["id"] == 1
    assert batches[0]["status"] == "success"


def test_repo_persists_dashboard_related_rows(tmp_path):
    repo = SQLiteSnapshotRepository(tmp_path / "portfolio.db")
    repo.initialize()
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="partial_success",
            total_assets_jpy=1500000,
            total_pnl_jpy=120000,
            daily_pnl_jpy=8000,
            error_summary="1 account failed",
            created_at=datetime(2026, 6, 1, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    repo.insert_account_snapshots([
        AccountSnapshot(
            batch_id=batch_id,
            account_id="ACC-1",
            account_name="Main",
            market="US",
            account_type="margin",
            currency="USD",
            total_assets_original=10000,
            total_assets_jpy=1500000,
            cash_original=1000,
            cash_jpy=150000,
            total_pnl_original=800,
            total_pnl_jpy=120000,
            daily_pnl_original=53.33,
            daily_pnl_jpy=8000,
            margin_used_jpy=200000,
            financing_amount_jpy=100000,
            buying_power_jpy=250000,
        )
    ])
    repo.insert_position_snapshots([
        PositionSnapshot(
            batch_id=batch_id,
            account_id="ACC-1",
            symbol="NVDA",
            raw_code="US.NVDA",
            name="NVIDIA",
            market="US",
            asset_type="stock",
            currency="USD",
            quantity=10,
            average_cost=100,
            latest_price=120,
            market_value_original=1200,
            market_value_jpy=180000,
            pnl_original=200,
            pnl_jpy=30000,
            pnl_ratio=0.2,
            position_ratio=0.12,
        )
    ])
    repo.upsert_theme_mapping(
        ThemeMapping(
            symbol="NVDA",
            theme="AI基建",
            display_name="NVIDIA",
            color="#22d3ee",
            enabled=True,
            updated_at=datetime(2026, 6, 1, 8, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
    repo.insert_sync_errors([
        SyncError(
            batch_id=batch_id,
            account_id="ACC-2",
            data_type="account",
            error_code="timeout",
            error_message="account sync timeout",
            created_at=datetime(2026, 6, 1, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    ])

    rows = repo.get_dashboard_rows(batch_id)
    assert rows["accounts"][0]["account_id"] == "ACC-1"
    assert rows["positions"][0]["symbol"] == "NVDA"
    assert rows["themes"][0]["theme"] == "AI基建"
    assert rows["errors"][0]["error_code"] == "timeout"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_sqlite_repo.py -v
```

Expected: FAIL because `SQLiteSnapshotRepository` does not exist.

- [ ] **Step 3: Add the migration script**

Create `app/migrations/001_init.sql`:

```sql
CREATE TABLE IF NOT EXISTS snapshot_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_time TEXT NOT NULL,
  trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
  status TEXT NOT NULL CHECK (status IN ('success', 'partial_success', 'failed')),
  base_currency TEXT NOT NULL DEFAULT 'JPY',
  total_assets_jpy REAL,
  total_pnl_jpy REAL,
  daily_pnl_jpy REAL,
  error_summary TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  account_id TEXT NOT NULL,
  account_name TEXT NOT NULL,
  market TEXT NOT NULL,
  account_type TEXT NOT NULL,
  currency TEXT NOT NULL,
  total_assets_original REAL,
  total_assets_jpy REAL,
  cash_original REAL,
  cash_jpy REAL,
  total_pnl_original REAL,
  total_pnl_jpy REAL,
  daily_pnl_original REAL,
  daily_pnl_jpy REAL,
  margin_used_jpy REAL,
  financing_amount_jpy REAL,
  buying_power_jpy REAL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS position_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  account_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  raw_code TEXT NOT NULL,
  name TEXT NOT NULL,
  market TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  currency TEXT NOT NULL,
  quantity REAL NOT NULL,
  average_cost REAL,
  latest_price REAL,
  market_value_original REAL,
  market_value_jpy REAL,
  pnl_original REAL,
  pnl_jpy REAL,
  pnl_ratio REAL,
  position_ratio REAL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS option_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  account_id TEXT NOT NULL,
  contract_code TEXT NOT NULL,
  underlying TEXT,
  option_type TEXT,
  side TEXT NOT NULL,
  strike REAL,
  expiry TEXT,
  quantity REAL NOT NULL,
  premium REAL,
  contract_multiplier REAL NOT NULL DEFAULT 100,
  market_value_jpy REAL,
  notional_exposure_jpy REAL,
  risk_tag TEXT NOT NULL,
  parse_status TEXT NOT NULL,
  raw_contract TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS exchange_rates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  from_currency TEXT NOT NULL,
  to_currency TEXT NOT NULL DEFAULT 'JPY',
  rate REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'moomoo',
  rate_time TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS theme_mappings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL UNIQUE,
  theme TEXT NOT NULL,
  display_name TEXT,
  color TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER,
  account_id TEXT,
  data_type TEXT NOT NULL,
  error_code TEXT NOT NULL,
  error_message TEXT NOT NULL,
  raw_payload TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_batches_time ON snapshot_batches(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_batch ON account_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_batch ON position_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_option_snapshots_batch ON option_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_batch ON exchange_rates(batch_id);
CREATE INDEX IF NOT EXISTS idx_sync_errors_batch ON sync_errors(batch_id);
```

- [ ] **Step 4: Add the repository**

Create `app/repositories/sqlite_snapshot_repo.py`:

```python
import sqlite3
from pathlib import Path
from typing import Any

from app.models.errors import SyncError
from app.models.snapshots import (
    AccountSnapshot,
    ExchangeRateSnapshot,
    OptionSnapshot,
    PositionSnapshot,
    SnapshotBatch,
    ThemeMapping,
)


class SQLiteSnapshotRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.migration_path = Path("app/migrations/001_init.sql")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        sql = self.migration_path.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.executescript(sql)

    def insert_batch(self, batch: SnapshotBatch) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO snapshot_batches (
                  snapshot_time, trigger_type, status, base_currency,
                  total_assets_jpy, total_pnl_jpy, daily_pnl_jpy, error_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.snapshot_time.isoformat(),
                    batch.trigger_type,
                    batch.status,
                    batch.base_currency,
                    batch.total_assets_jpy,
                    batch.total_pnl_jpy,
                    batch.daily_pnl_jpy,
                    batch.error_summary,
                    batch.created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def insert_account_snapshots(self, accounts: list[AccountSnapshot]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO account_snapshots (
                  batch_id, account_id, account_name, market, account_type, currency,
                  total_assets_original, total_assets_jpy, cash_original, cash_jpy,
                  total_pnl_original, total_pnl_jpy, daily_pnl_original, daily_pnl_jpy,
                  margin_used_jpy, financing_amount_jpy, buying_power_jpy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.batch_id,
                        item.account_id,
                        item.account_name,
                        item.market,
                        item.account_type,
                        item.currency,
                        item.total_assets_original,
                        item.total_assets_jpy,
                        item.cash_original,
                        item.cash_jpy,
                        item.total_pnl_original,
                        item.total_pnl_jpy,
                        item.daily_pnl_original,
                        item.daily_pnl_jpy,
                        item.margin_used_jpy,
                        item.financing_amount_jpy,
                        item.buying_power_jpy,
                    )
                    for item in accounts
                ],
            )

    def insert_position_snapshots(self, positions: list[PositionSnapshot]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO position_snapshots (
                  batch_id, account_id, symbol, raw_code, name, market, asset_type, currency,
                  quantity, average_cost, latest_price, market_value_original, market_value_jpy,
                  pnl_original, pnl_jpy, pnl_ratio, position_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.batch_id,
                        item.account_id,
                        item.symbol,
                        item.raw_code,
                        item.name,
                        item.market,
                        item.asset_type,
                        item.currency,
                        item.quantity,
                        item.average_cost,
                        item.latest_price,
                        item.market_value_original,
                        item.market_value_jpy,
                        item.pnl_original,
                        item.pnl_jpy,
                        item.pnl_ratio,
                        item.position_ratio,
                    )
                    for item in positions
                ],
            )

    def insert_option_snapshots(self, options: list[OptionSnapshot]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO option_snapshots (
                  batch_id, account_id, contract_code, underlying, option_type, side, strike,
                  expiry, quantity, premium, contract_multiplier, market_value_jpy,
                  notional_exposure_jpy, risk_tag, parse_status, raw_contract
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.batch_id,
                        item.account_id,
                        item.contract_code,
                        item.underlying,
                        item.option_type,
                        item.side,
                        item.strike,
                        item.expiry.isoformat() if item.expiry else None,
                        item.quantity,
                        item.premium,
                        item.contract_multiplier,
                        item.market_value_jpy,
                        item.notional_exposure_jpy,
                        item.risk_tag,
                        item.parse_status,
                        item.raw_contract,
                    )
                    for item in options
                ],
            )

    def insert_exchange_rates(self, rates: list[ExchangeRateSnapshot]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO exchange_rates (batch_id, from_currency, to_currency, rate, source, rate_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.batch_id,
                        item.from_currency,
                        item.to_currency,
                        item.rate,
                        item.source,
                        item.rate_time.isoformat(),
                    )
                    for item in rates
                ],
            )

    def insert_sync_errors(self, errors: list[SyncError]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO sync_errors (batch_id, account_id, data_type, error_code, error_message, raw_payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.batch_id,
                        item.account_id,
                        item.data_type,
                        item.error_code,
                        item.error_message,
                        item.raw_payload,
                        item.created_at.isoformat(),
                    )
                    for item in errors
                ],
            )

    def upsert_theme_mapping(self, mapping: ThemeMapping) -> dict[str, Any]:
        symbol = mapping.symbol.upper()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO theme_mappings (symbol, theme, display_name, color, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                  theme = excluded.theme,
                  display_name = excluded.display_name,
                  color = excluded.color,
                  enabled = excluded.enabled,
                  updated_at = excluded.updated_at
                """,
                (
                    symbol,
                    mapping.theme,
                    mapping.display_name,
                    mapping.color,
                    1 if mapping.enabled else 0,
                    mapping.updated_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM theme_mappings WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        return dict(row)

    def list_theme_mappings(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM theme_mappings ORDER BY theme, symbol"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_batches(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM snapshot_batches
                WHERE status IN ('success', 'partial_success')
                ORDER BY snapshot_time DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_dashboard_rows(self, batch_id: int) -> dict[str, list[dict[str, Any]]]:
        with self._connect() as connection:
            batch = connection.execute(
                "SELECT * FROM snapshot_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            accounts = connection.execute(
                "SELECT * FROM account_snapshots WHERE batch_id = ? ORDER BY account_id",
                (batch_id,),
            ).fetchall()
            positions = connection.execute(
                "SELECT * FROM position_snapshots WHERE batch_id = ? ORDER BY ABS(COALESCE(market_value_jpy, 0)) DESC",
                (batch_id,),
            ).fetchall()
            options = connection.execute(
                "SELECT * FROM option_snapshots WHERE batch_id = ? ORDER BY expiry, underlying",
                (batch_id,),
            ).fetchall()
            errors = connection.execute(
                "SELECT * FROM sync_errors WHERE batch_id = ? ORDER BY id",
                (batch_id,),
            ).fetchall()
            themes = connection.execute(
                "SELECT * FROM theme_mappings WHERE enabled = 1 ORDER BY theme, symbol",
            ).fetchall()
        return {
            "batch": [dict(batch)] if batch else [],
            "accounts": [dict(row) for row in accounts],
            "positions": [dict(row) for row in positions],
            "options": [dict(row) for row in options],
            "errors": [dict(row) for row in errors],
            "themes": [dict(row) for row in themes],
        }
```

Create `app/repositories/__init__.py`:

```python
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository

__all__ = ["SQLiteSnapshotRepository"]
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_sqlite_repo.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/migrations app/repositories tests/test_sqlite_repo.py
git commit -m "feat: add sqlite snapshot repository"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 4: Add FX Conversion and Option Parsing

**Files:**
- Create: `app/adapters/__init__.py`
- Create: `app/adapters/fx_converter.py`
- Create: `app/adapters/option_parser.py`
- Test: `tests/test_fx_converter.py`
- Test: `tests/test_option_parser.py`

- [ ] **Step 1: Write the failing adapter helper tests**

Create `tests/test_fx_converter.py`:

```python
from app.adapters.fx_converter import FxConverter


def test_fx_converter_returns_jpy_for_same_currency():
    converter = FxConverter({"JPY": 1.0, "USD": 150.0})
    assert converter.to_jpy(100, "JPY") == 100


def test_fx_converter_returns_none_when_rate_missing():
    converter = FxConverter({"JPY": 1.0})
    assert converter.to_jpy(100, "USD") is None
```

Create `tests/test_option_parser.py`:

```python
from app.adapters.option_parser import parse_option_contract


def test_parse_option_contract_reads_underlying_type_and_strike():
    parsed = parse_option_contract("US.NVDA260619P00150000")
    assert parsed["underlying"] == "NVDA"
    assert parsed["option_type"] == "PUT"
    assert parsed["strike"] == 150.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_fx_converter.py tests/test_option_parser.py -v
```

Expected: FAIL because adapter helper files do not exist.

- [ ] **Step 3: Add the helper implementations**

Create `app/adapters/fx_converter.py`:

```python
class FxConverter:
    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = {key.upper(): value for key, value in rates.items()}

    def to_jpy(self, amount: float | None, currency: str | None) -> float | None:
        if amount is None or currency is None:
            return None
        normalized = currency.upper()
        if normalized == "JPY":
            return amount
        rate = self.rates.get(normalized)
        if rate is None:
            return None
        return amount * rate
```

Create `app/adapters/option_parser.py`:

```python
from datetime import datetime


def parse_option_contract(contract_code: str) -> dict[str, object]:
    normalized = contract_code.split(".")[-1]
    underlying = normalized[:-15]
    expiry_token = normalized[-15:-9]
    option_flag = normalized[-9:-8]
    strike_token = normalized[-8:]
    option_type = "CALL" if option_flag == "C" else "PUT"
    expiry = datetime.strptime(expiry_token, "%y%m%d").date()
    strike = int(strike_token) / 1000
    return {
        "underlying": underlying,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
    }
```

Create `app/adapters/__init__.py`:

```python
from app.adapters.fx_converter import FxConverter
from app.adapters.option_parser import parse_option_contract

__all__ = ["FxConverter", "parse_option_contract"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_fx_converter.py tests/test_option_parser.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/adapters tests/test_fx_converter.py tests/test_option_parser.py
git commit -m "feat: add fx conversion and option parsing helpers"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 5: Add moomoo Adapter and Real OpenD Client

**Files:**
- Create: `app/adapters/moomoo_adapter.py`
- Create: `app/adapters/moomoo_client.py`
- Test: `tests/test_moomoo_adapter.py`

- [ ] **Step 1: Extend the failing adapter tests**

Append to `tests/test_moomoo_adapter.py`:

```python
from app.adapters.fx_converter import FxConverter
from app.adapters.moomoo_adapter import MoomooAdapter


def test_moomoo_adapter_maps_account_and_position_rows():
    adapter = MoomooAdapter(FxConverter({"USD": 150.0, "JPY": 1.0}))
    account = adapter.to_account_snapshot(
        batch_id=1,
        account_info={
            "acc_id": "ACC-1",
            "currency": "USD",
            "total_assets": 10000,
            "cash": 1000,
            "total_pl": 500,
            "today_pl": 30,
        },
        metadata={"account_name": "Main", "market": "US", "account_type": "margin"},
    )
    position = adapter.to_position_snapshot(
        batch_id=1,
        account_id="ACC-1",
        row={
            "code": "US.NVDA",
            "stock_name": "NVIDIA",
            "qty": 10,
            "average_cost": 100,
            "nominal_price": 120,
            "market_val": 1200,
            "pl_val": 200,
            "pl_ratio": 0.2,
            "currency": "USD",
        },
        batch_total_assets_jpy=1500000,
    )
    assert account.total_assets_jpy == 1500000
    assert position.symbol == "NVDA"
    assert position.position_ratio == 0.12
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_moomoo_adapter.py -v
```

Expected: FAIL because `MoomooAdapter` does not exist.

- [ ] **Step 3: Add the adapter implementation**

Create `app/adapters/moomoo_adapter.py`:

```python
import json
from datetime import datetime

from app.adapters.fx_converter import FxConverter
from app.adapters.option_parser import parse_option_contract
from app.models.errors import SyncError
from app.models.snapshots import AccountSnapshot, OptionSnapshot, PositionSnapshot


class MoomooAdapter:
    def __init__(self, fx_converter: FxConverter) -> None:
        self.fx_converter = fx_converter

    def to_account_snapshot(self, batch_id: int, account_info: dict, metadata: dict) -> AccountSnapshot:
        currency = str(account_info.get("currency", metadata.get("currency", "USD"))).upper()
        total_assets_original = self._to_float(account_info.get("total_assets"))
        cash_original = self._to_float(account_info.get("cash"))
        total_pnl_original = self._to_float(account_info.get("total_pl"))
        daily_pnl_original = self._to_float(account_info.get("today_pl"))
        return AccountSnapshot(
            batch_id=batch_id,
            account_id=str(account_info.get("acc_id")),
            account_name=str(metadata.get("account_name", account_info.get("acc_id"))),
            market=str(metadata.get("market", "OTHER")).upper(),
            account_type=str(metadata.get("account_type", "securities")),
            currency=currency,
            total_assets_original=total_assets_original,
            total_assets_jpy=self.fx_converter.to_jpy(total_assets_original, currency),
            cash_original=cash_original,
            cash_jpy=self.fx_converter.to_jpy(cash_original, currency),
            total_pnl_original=total_pnl_original,
            total_pnl_jpy=self.fx_converter.to_jpy(total_pnl_original, currency),
            daily_pnl_original=daily_pnl_original,
            daily_pnl_jpy=self.fx_converter.to_jpy(daily_pnl_original, currency),
            margin_used_jpy=self.fx_converter.to_jpy(self._to_float(account_info.get("margin_used")), currency),
            financing_amount_jpy=self.fx_converter.to_jpy(self._to_float(account_info.get("financing_amount")), currency),
            buying_power_jpy=self.fx_converter.to_jpy(self._to_float(account_info.get("buying_power")), currency),
        )

    def to_position_snapshot(
        self,
        batch_id: int,
        account_id: str,
        row: dict,
        batch_total_assets_jpy: float | None,
    ) -> PositionSnapshot:
        raw_code = str(row.get("code", ""))
        currency = str(row.get("currency", "USD")).upper()
        market_value_original = self._to_float(row.get("market_val"))
        market_value_jpy = self.fx_converter.to_jpy(market_value_original, currency)
        position_ratio = None
        if batch_total_assets_jpy and market_value_jpy is not None:
            position_ratio = market_value_jpy / batch_total_assets_jpy
        return PositionSnapshot(
            batch_id=batch_id,
            account_id=account_id,
            symbol=self._normalize_symbol(raw_code),
            raw_code=raw_code,
            name=str(row.get("stock_name", "")),
            market=self._detect_market(raw_code),
            asset_type=self._classify_asset_type(raw_code),
            currency=currency,
            quantity=self._to_float(row.get("qty")) or 0.0,
            average_cost=self._to_float(row.get("average_cost") or row.get("cost_price")),
            latest_price=self._to_float(row.get("nominal_price")),
            market_value_original=market_value_original,
            market_value_jpy=market_value_jpy,
            pnl_original=self._to_float(row.get("pl_val")),
            pnl_jpy=self.fx_converter.to_jpy(self._to_float(row.get("pl_val")), currency),
            pnl_ratio=self._to_float(row.get("pl_ratio")),
            position_ratio=position_ratio,
        )

    def to_option_snapshot(self, batch_id: int, account_id: str, row: dict) -> OptionSnapshot:
        raw_code = str(row.get("code", ""))
        quantity = self._to_float(row.get("qty")) or 0.0
        currency = str(row.get("currency", "USD")).upper()
        market_value_original = self._to_float(row.get("market_val"))
        market_value_jpy = self.fx_converter.to_jpy(market_value_original, currency)
        parsed = parse_option_contract(raw_code)
        side = "SHORT" if quantity < 0 else "LONG"
        risk_tag = self._derive_risk_tag(parsed["option_type"], side)
        notional_original = abs(parsed["strike"] * quantity * 100)
        return OptionSnapshot(
            batch_id=batch_id,
            account_id=account_id,
            contract_code=raw_code,
            underlying=str(parsed["underlying"]),
            option_type=str(parsed["option_type"]),
            side=side,
            strike=float(parsed["strike"]),
            expiry=parsed["expiry"],
            quantity=quantity,
            premium=self._to_float(row.get("nominal_price")),
            contract_multiplier=100,
            market_value_jpy=market_value_jpy,
            notional_exposure_jpy=self.fx_converter.to_jpy(notional_original, currency),
            risk_tag=risk_tag,
            parse_status="parsed",
            raw_contract=json.dumps(row, ensure_ascii=True),
        )

    def build_missing_fx_error(self, batch_id: int, account_id: str, currency: str) -> SyncError:
        return SyncError(
            batch_id=batch_id,
            account_id=account_id,
            data_type="rate",
            error_code="missing_rate",
            error_message=f"missing fx rate for {currency}",
            raw_payload=None,
            created_at=datetime.now(),
        )

    def _normalize_symbol(self, raw_code: str) -> str:
        return raw_code.split(".")[-1].split(" ")[0].upper()

    def _detect_market(self, raw_code: str) -> str:
        prefix = raw_code.split(".")[0].upper() if "." in raw_code else "OTHER"
        return prefix if prefix in {"US", "HK"} else "OTHER"

    def _classify_asset_type(self, raw_code: str) -> str:
        tail = raw_code.split(".")[-1]
        if len(tail) >= 15 and tail[-9:-8] in {"C", "P"}:
            return "option"
        return "stock"

    def _derive_risk_tag(self, option_type: str, side: str) -> str:
        mapping = {
            ("PUT", "SHORT"): "short_put",
            ("CALL", "SHORT"): "short_call",
            ("CALL", "LONG"): "long_call",
            ("PUT", "LONG"): "long_put",
        }
        return mapping.get((option_type, side), "unknown_option")

    def _to_float(self, value: object) -> float | None:
        if value in (None, ""):
            return None
        return float(value)
```

- [ ] **Step 4: Add the real OpenD client wrapper**

Create `app/adapters/moomoo_client.py`:

```python
from contextlib import AbstractContextManager
from typing import Any

from moomoo import OpenSecTradeContext


class MoomooClient(AbstractContextManager):
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.context: OpenSecTradeContext | None = None

    def __enter__(self) -> "MoomooClient":
        self.context = OpenSecTradeContext(host=self.host, port=self.port)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self.context is not None:
            self.context.close()
            self.context = None

    def list_accounts(self) -> list[dict[str, Any]]:
        assert self.context is not None
        ret, data = self.context.get_acc_list()
        if ret != 0:
            raise RuntimeError(f"get_acc_list failed: {data}")
        return data.to_dict("records")

    def get_account_funds(self, account_id: str) -> dict[str, Any]:
        assert self.context is not None
        ret, data = self.context.accinfo_query(acc_id=int(account_id))
        if ret != 0:
            raise RuntimeError(f"accinfo_query failed for {account_id}: {data}")
        records = data.to_dict("records")
        return records[0] if records else {}

    def get_positions(self, account_id: str) -> list[dict[str, Any]]:
        assert self.context is not None
        ret, data = self.context.position_list_query(acc_id=int(account_id))
        if ret != 0:
            raise RuntimeError(f"position_list_query failed for {account_id}: {data}")
        return data.to_dict("records")
```

- [ ] **Step 5: Run the adapter tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_moomoo_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/adapters tests/test_moomoo_adapter.py
git commit -m "feat: add moomoo adapter and opend client wrapper"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 6: Add the Minimal Real Sync Service

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/sync_service.py`
- Test: `tests/test_sync_service.py`

- [ ] **Step 1: Write the failing sync service test**

Create `tests/test_sync_service.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.adapters.fx_converter import FxConverter
from app.adapters.moomoo_adapter import MoomooAdapter
from app.models.snapshots import SnapshotBatch
from app.services.sync_service import summarize_batch


def test_summarize_batch_marks_partial_success_when_any_error_exists():
    batch = SnapshotBatch(
        snapshot_time=datetime(2026, 6, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        trigger_type="manual",
        status="success",
        created_at=datetime(2026, 6, 1, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
    )
    result = summarize_batch(
        batch=batch,
        account_totals=[1500000, 200000],
        daily_pnls=[8000],
        total_pnls=[120000],
        error_messages=["ACC-2 timeout"],
    )
    assert result.status == "partial_success"
    assert result.total_assets_jpy == 1700000
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_sync_service.py -v
```

Expected: FAIL because `sync_service` does not exist.

- [ ] **Step 3: Add the sync service**

Create `app/services/sync_service.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.adapters.moomoo_adapter import MoomooAdapter
from app.adapters.moomoo_client import MoomooClient
from app.config import Settings
from app.models.errors import SyncError
from app.models.snapshots import ExchangeRateSnapshot, SnapshotBatch
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository


def summarize_batch(
    batch: SnapshotBatch,
    account_totals: list[float],
    daily_pnls: list[float],
    total_pnls: list[float],
    error_messages: list[str],
) -> SnapshotBatch:
    status = "success"
    if error_messages and account_totals:
        status = "partial_success"
    if not account_totals:
        status = "failed"
    batch.status = status
    batch.total_assets_jpy = sum(account_totals) if account_totals else None
    batch.total_pnl_jpy = sum(total_pnls) if total_pnls else None
    batch.daily_pnl_jpy = sum(daily_pnls) if daily_pnls else None
    batch.error_summary = "; ".join(error_messages) if error_messages else None
    return batch


@dataclass
class SyncResult:
    batch_id: int | None
    status: str
    snapshot_time: str
    accounts_total: int
    accounts_succeeded: int
    accounts_failed: int
    message: str


class SyncService:
    def __init__(
        self,
        settings: Settings,
        adapter: MoomooAdapter,
        repository: SQLiteSnapshotRepository,
    ) -> None:
        self.settings = settings
        self.adapter = adapter
        self.repository = repository
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def run_sync(self, trigger_type: str = "manual") -> SyncResult:
        if self._is_running:
            raise RuntimeError("sync already running")

        self._is_running = True
        try:
            tokyo = ZoneInfo(self.settings.timezone)
            now = datetime.now(tokyo)
            provisional_batch = SnapshotBatch(
                snapshot_time=now,
                trigger_type=trigger_type,
                status="failed",
                created_at=now,
            )

            accounts = []
            positions = []
            options = []
            rates = []
            errors: list[SyncError] = []
            account_totals = []
            total_pnls = []
            daily_pnls = []
            accounts_total = 0
            accounts_succeeded = 0
            accounts_failed = 0

            with MoomooClient(self.settings.moomoo_host, self.settings.moomoo_port) as client:
                account_rows = client.list_accounts()
                if not account_rows:
                    raise RuntimeError("no accounts returned from OpenD")

                accounts_total = len(account_rows)
                for account_row in account_rows:
                    account_id = str(account_row["acc_id"])
                    metadata = {
                        "account_name": str(account_row.get("acc_name", account_id)),
                        "market": str(account_row.get("market", "OTHER")).upper(),
                        "account_type": str(account_row.get("account_type", "securities")),
                    }
                    try:
                        funds_row = client.get_account_funds(account_id)
                        funds_row["acc_id"] = account_id
                        account_snapshot = self.adapter.to_account_snapshot(0, funds_row, metadata)
                        position_rows = client.get_positions(account_id)
                        batch_total_assets = account_snapshot.total_assets_jpy

                        if account_snapshot.total_assets_jpy is not None:
                            account_totals.append(account_snapshot.total_assets_jpy)
                        if account_snapshot.total_pnl_jpy is not None:
                            total_pnls.append(account_snapshot.total_pnl_jpy)
                        if account_snapshot.daily_pnl_jpy is not None:
                            daily_pnls.append(account_snapshot.daily_pnl_jpy)

                        accounts.append(account_snapshot)
                        if account_snapshot.currency.upper() != "JPY":
                            rate = (account_snapshot.total_assets_jpy / account_snapshot.total_assets_original) if account_snapshot.total_assets_original and account_snapshot.total_assets_jpy else None
                            if rate:
                                rates.append(
                                    ExchangeRateSnapshot(
                                        batch_id=0,
                                        from_currency=account_snapshot.currency,
                                        rate=rate,
                                        rate_time=now,
                                    )
                                )
                            else:
                                errors.append(
                                    self.adapter.build_missing_fx_error(0, account_id, account_snapshot.currency)
                                )

                        for row in position_rows:
                            position = self.adapter.to_position_snapshot(
                                batch_id=0,
                                account_id=account_id,
                                row=row,
                                batch_total_assets_jpy=batch_total_assets,
                            )
                            positions.append(position)
                            if position.asset_type == "option":
                                options.append(
                                    self.adapter.to_option_snapshot(
                                        batch_id=0,
                                        account_id=account_id,
                                        row=row,
                                    )
                                )

                        accounts_succeeded += 1
                    except Exception as exc:
                        accounts_failed += 1
                        errors.append(
                            SyncError(
                                batch_id=None,
                                account_id=account_id,
                                data_type="account",
                                error_code="sync_failed",
                                error_message=str(exc),
                                raw_payload=None,
                                created_at=now,
                            )
                        )

            finalized_batch = summarize_batch(
                batch=provisional_batch,
                account_totals=account_totals,
                daily_pnls=daily_pnls,
                total_pnls=total_pnls,
                error_messages=[item.error_message for item in errors],
            )

            if finalized_batch.status == "failed":
                raise RuntimeError(finalized_batch.error_summary or "sync failed")

            batch_id = self.repository.insert_batch(finalized_batch)
            accounts = [item.model_copy(update={"batch_id": batch_id}) for item in accounts]
            positions = [item.model_copy(update={"batch_id": batch_id}) for item in positions]
            options = [item.model_copy(update={"batch_id": batch_id}) for item in options]
            rates = [item.model_copy(update={"batch_id": batch_id}) for item in rates]
            errors = [item.model_copy(update={"batch_id": batch_id}) for item in errors]

            self.repository.insert_account_snapshots(accounts)
            self.repository.insert_position_snapshots(positions)
            self.repository.insert_option_snapshots(options)
            self.repository.insert_exchange_rates(rates)
            self.repository.insert_sync_errors(errors)

            return SyncResult(
                batch_id=batch_id,
                status=finalized_batch.status,
                snapshot_time=finalized_batch.snapshot_time.isoformat(),
                accounts_total=accounts_total,
                accounts_succeeded=accounts_succeeded,
                accounts_failed=accounts_failed,
                message="sync completed",
            )
        finally:
            self._is_running = False
```

Create `app/services/__init__.py`:

```python
from app.services.sync_service import SyncResult, SyncService, summarize_batch

__all__ = ["SyncResult", "SyncService", "summarize_batch"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_sync_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/services tests/test_sync_service.py
git commit -m "feat: add real opend sync service"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 7: Add Dashboard Read Service

**Files:**
- Create: `app/services/dashboard_service.py`
- Test: `tests/test_dashboard_service.py`

- [ ] **Step 1: Write the failing dashboard service test**

Create `tests/test_dashboard_service.py`:

```python
from app.services.dashboard_service import build_asset_allocation


def test_build_asset_allocation_groups_stock_option_and_cash():
    positions = [
        {"asset_type": "stock", "market_value_jpy": 100},
        {"asset_type": "option", "market_value_jpy": -20},
        {"asset_type": "cash", "market_value_jpy": 30},
    ]
    allocation = build_asset_allocation(positions)
    assert allocation["stock"] == 100
    assert allocation["option"] == -20
    assert allocation["cash"] == 30
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_dashboard_service.py -v
```

Expected: FAIL because `dashboard_service` does not exist.

- [ ] **Step 3: Add the dashboard service**

Create `app/services/dashboard_service.py`:

```python
from collections import defaultdict
from typing import Any

from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository


def build_asset_allocation(positions: list[dict[str, Any]]) -> dict[str, float]:
    allocation = {"stock": 0.0, "option": 0.0, "cash": 0.0}
    for row in positions:
        asset_type = row.get("asset_type")
        value = float(row.get("market_value_jpy") or 0.0)
        if asset_type in allocation:
            allocation[asset_type] += value
    return allocation


class DashboardService:
    def __init__(self, repository: SQLiteSnapshotRepository) -> None:
        self.repository = repository

    def get_dashboard(self, batch_id: int | None = None) -> dict[str, Any]:
        batches = self.repository.list_batches()
        if not batches:
            return {
                "summary": {},
                "positions": [],
                "treemap": [],
                "themes": [],
                "performance": [],
                "options": [],
                "asset_allocation": {"stock": 0.0, "option": 0.0, "cash": 0.0},
            }

        selected_batch = batch_id or int(batches[0]["id"])
        rows = self.repository.get_dashboard_rows(selected_batch)
        batch = rows["batch"][0]
        positions = rows["positions"]
        theme_lookup = {item["symbol"].upper(): item for item in rows["themes"]}

        theme_groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"theme": "未分类", "market_value_jpy": 0.0, "symbols": []}
        )
        for row in positions:
            symbol = row["symbol"].upper()
            theme_row = theme_lookup.get(symbol)
            theme_name = theme_row["theme"] if theme_row else "未分类"
            group = theme_groups[theme_name]
            group["theme"] = theme_name
            group["market_value_jpy"] += float(row.get("market_value_jpy") or 0.0)
            group["symbols"].append(symbol)

        performance = [
            {
                "batch_id": item["id"],
                "snapshot_time": item["snapshot_time"],
                "total_assets_jpy": item["total_assets_jpy"],
                "total_pnl_jpy": item["total_pnl_jpy"],
                "daily_pnl_jpy": item["daily_pnl_jpy"],
            }
            for item in reversed(batches)
        ]

        return {
            "summary": {
                "batch_id": batch["id"],
                "snapshot_time": batch["snapshot_time"],
                "status": batch["status"],
                "total_assets_jpy": batch["total_assets_jpy"],
                "total_pnl_jpy": batch["total_pnl_jpy"],
                "daily_pnl_jpy": batch["daily_pnl_jpy"],
                "error_summary": batch["error_summary"],
            },
            "positions": positions,
            "treemap": positions,
            "themes": list(theme_groups.values()),
            "performance": performance,
            "options": rows["options"],
            "asset_allocation": build_asset_allocation(positions),
        }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_dashboard_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/services/dashboard_service.py tests/test_dashboard_service.py
git commit -m "feat: add dashboard aggregation service"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 8: Add Snapshot, Dashboard, Sync, and Theme APIs

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add the failing API tests**

Append to `tests/test_api.py`:

```python
def test_snapshot_and_theme_endpoints_exist(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "portfolio.db"))
    assert client.get("/api/snapshots").status_code == 200
    assert client.get("/api/themes").status_code == 200
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_api.py -v
```

Expected: FAIL because the routes are not wired yet.

- [ ] **Step 3: Expand the API router**

Replace `app/api/routes.py` with:

```python
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.snapshots import ThemeMapping
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository
from app.services.dashboard_service import DashboardService
from app.services.sync_service import SyncService


class ThemeMappingRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    theme: str = Field(min_length=1, max_length=50)
    display_name: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    enabled: bool = True


def create_router(
    repository: SQLiteSnapshotRepository | None = None,
    dashboard_service: DashboardService | None = None,
    sync_service: SyncService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")

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
    def run_sync() -> dict[str, Any]:
        if sync_service is None:
            raise HTTPException(status_code=500, detail="sync service unavailable")
        if sync_service.is_running():
            raise HTTPException(status_code=409, detail="sync already running")
        try:
            result = sync_service.run_sync("manual")
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return result.__dict__

    @router.get("/themes")
    def list_themes() -> list[dict[str, Any]]:
        return repository.list_theme_mappings() if repository else []

    @router.post("/themes")
    def upsert_theme(payload: ThemeMappingRequest) -> dict[str, Any]:
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

    return router
```

- [ ] **Step 4: Wire dependencies through the app factory**

Replace `app/main.py` with:

```python
from pathlib import Path

from fastapi import FastAPI

from app.adapters.fx_converter import FxConverter
from app.adapters.moomoo_adapter import MoomooAdapter
from app.api.routes import create_router
from app.config import get_settings
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository
from app.services.dashboard_service import DashboardService
from app.services.sync_service import SyncService


def create_app(database_path: Path | None = None) -> FastAPI:
    settings = get_settings()
    repository = SQLiteSnapshotRepository(database_path or settings.database_path)
    repository.initialize()
    adapter = MoomooAdapter(FxConverter({"JPY": 1.0, "USD": 150.0, "HKD": 19.0}))
    sync_service = SyncService(settings=settings, adapter=adapter, repository=repository)
    dashboard_service = DashboardService(repository)

    app = FastAPI(title="Portfolio Dashboard")
    app.include_router(create_router(repository, dashboard_service, sync_service))
    return app


app = create_app()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/api app/main.py tests/test_api.py
git commit -m "feat: add dashboard and theme apis"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 9: Add the Single-Page Dashboard Frontend

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/styles.css`
- Create: `app/static/dashboard.js`
- Modify: `app/main.py`

- [ ] **Step 1: Add the static dashboard files**

Create `app/static/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>持仓看板</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <div class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Moomoo Portfolio Dashboard</p>
          <h1>持仓全景看板</h1>
          <p id="snapshotMeta" class="muted">暂无快照</p>
        </div>
        <div class="actions">
          <button id="syncButton" type="button">立即同步</button>
          <select id="snapshotSelect" aria-label="选择快照"></select>
          <button id="themeModalButton" type="button">主题设置</button>
        </div>
      </header>

      <section id="statusBanner" class="banner hidden"></section>

      <section id="summary" class="summary-grid"></section>

      <section class="panel">
        <div class="panel-heading">
          <h2>持仓树图</h2>
        </div>
        <div id="treemap" class="treemap"></div>
      </section>

      <section class="two-column">
        <section class="panel">
          <div class="panel-heading">
            <h2>主题板块</h2>
          </div>
          <div id="themes" class="theme-grid"></div>
        </section>
        <section class="panel">
          <div class="panel-heading">
            <h2>期权风险</h2>
          </div>
          <div id="options" class="option-list"></div>
        </section>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <h2>收益曲线</h2>
        </div>
        <div id="performance" class="performance-list"></div>
      </section>
    </div>

    <dialog id="themeModal">
      <form method="dialog" class="theme-modal">
        <div class="theme-modal-header">
          <h2>主题配置</h2>
          <button type="submit">关闭</button>
        </div>
        <div class="theme-form">
          <input id="themeSymbol" placeholder="Symbol" />
          <input id="themeName" placeholder="Theme" />
          <input id="themeDisplayName" placeholder="Display Name" />
          <input id="themeColor" placeholder="#22d3ee" />
          <button id="saveThemeButton" type="button">保存主题</button>
        </div>
        <div id="themeTable" class="theme-table"></div>
      </form>
    </dialog>

    <script src="/static/dashboard.js"></script>
  </body>
</html>
```

Create `app/static/styles.css`:

```css
:root {
  --bg: #0a1117;
  --panel: #111d29;
  --border: #233243;
  --text: #f5fbff;
  --muted: #8da1b7;
  --green: #4ade80;
  --cyan: #22d3ee;
  --amber: #f59e0b;
  --red: #f87171;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.12), transparent 30%),
    linear-gradient(180deg, #071018 0%, #0a1117 100%);
  color: var(--text);
  font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}

.shell {
  width: min(1280px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.topbar,
.actions,
.panel-heading,
.row {
  display: flex;
  align-items: center;
}

.topbar,
.panel-heading,
.row {
  justify-content: space-between;
}

.topbar {
  gap: 20px;
  margin-bottom: 18px;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 42px;
  line-height: 1.05;
}

.eyebrow,
.muted {
  color: var(--muted);
}

.actions {
  gap: 10px;
  flex-wrap: wrap;
}

button,
select,
input {
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--text);
  border-radius: 10px;
  padding: 10px 12px;
}

.banner {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--amber);
  background: rgba(245, 158, 11, 0.1);
  border-radius: 10px;
}

.hidden {
  display: none;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.card,
.panel,
.theme-modal {
  border: 1px solid var(--border);
  background: rgba(17, 29, 41, 0.92);
  border-radius: 16px;
}

.card {
  padding: 16px;
}

.card strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
}

.panel {
  padding: 18px;
  margin-bottom: 16px;
}

.treemap {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 8px;
  min-height: 320px;
}

.tile {
  min-height: 96px;
  border-radius: 12px;
  color: #081018;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 12px;
  font-weight: 700;
}

.two-column {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}

.theme-grid,
.option-list,
.performance-list,
.theme-table {
  display: grid;
  gap: 10px;
}

.row {
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

dialog {
  border: none;
  padding: 0;
  background: transparent;
}

.theme-modal {
  width: min(760px, calc(100vw - 24px));
  padding: 18px;
}

.theme-modal-header,
.theme-form {
  display: grid;
  gap: 10px;
}

.theme-modal-header {
  grid-template-columns: 1fr auto;
  align-items: center;
  margin-bottom: 14px;
}

.theme-form {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-bottom: 16px;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .two-column,
  .theme-form {
    grid-template-columns: 1fr;
  }
}
```

Create `app/static/dashboard.js`:

```javascript
const currencyFormatter = new Intl.NumberFormat("ja-JP", {
  style: "currency",
  currency: "JPY",
  maximumFractionDigits: 0
});

const summary = document.querySelector("#summary");
const treemap = document.querySelector("#treemap");
const themes = document.querySelector("#themes");
const options = document.querySelector("#options");
const performance = document.querySelector("#performance");
const statusBanner = document.querySelector("#statusBanner");
const snapshotSelect = document.querySelector("#snapshotSelect");
const snapshotMeta = document.querySelector("#snapshotMeta");
const syncButton = document.querySelector("#syncButton");
const themeModal = document.querySelector("#themeModal");
const themeModalButton = document.querySelector("#themeModalButton");
const saveThemeButton = document.querySelector("#saveThemeButton");
const themeSymbol = document.querySelector("#themeSymbol");
const themeName = document.querySelector("#themeName");
const themeDisplayName = document.querySelector("#themeDisplayName");
const themeColor = document.querySelector("#themeColor");
const themeTable = document.querySelector("#themeTable");

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function showStatus(message, warning = false) {
  if (!message) {
    statusBanner.classList.add("hidden");
    statusBanner.textContent = "";
    return;
  }
  statusBanner.classList.remove("hidden");
  statusBanner.textContent = message;
  statusBanner.style.borderColor = warning ? "var(--amber)" : "var(--green)";
}

function renderSummary(data) {
  const cards = [
    ["总资产", data.summary.total_assets_jpy],
    ["总收益", data.summary.total_pnl_jpy],
    ["日收益", data.summary.daily_pnl_jpy],
    ["股票占比", data.asset_allocation.stock],
    ["期权占比", data.asset_allocation.option],
    ["现金占比", data.asset_allocation.cash]
  ];
  summary.innerHTML = cards.map(([label, value]) => `
    <article class="card">
      <span class="muted">${label}</span>
      <strong>${currencyFormatter.format(value || 0)}</strong>
    </article>
  `).join("");
}

function renderTreemap(data) {
  const palette = ["#22d3ee", "#4ade80", "#f59e0b", "#f87171", "#60a5fa", "#f472b6"];
  treemap.innerHTML = data.treemap
    .filter((row) => row.asset_type !== "option")
    .map((row, index) => {
      const span = Math.max(2, Math.min(6, Math.round(Math.abs((row.position_ratio || 0) * 24))));
      return `
        <div class="tile" style="grid-column: span ${span}; background:${palette[index % palette.length]}">
          <div>${row.symbol}</div>
          <div>${currencyFormatter.format(row.market_value_jpy || 0)}</div>
        </div>
      `;
    }).join("");
}

function renderThemes(data) {
  themes.innerHTML = data.themes.map((row) => `
    <div class="row">
      <strong>${row.theme}</strong>
      <span>${currencyFormatter.format(row.market_value_jpy || 0)}</span>
    </div>
  `).join("") || `<p class="muted">暂无主题配置</p>`;
}

function renderOptions(data) {
  options.innerHTML = data.options.map((row) => `
    <div class="row">
      <strong>${row.underlying || row.contract_code}</strong>
      <span>${row.risk_tag} · ${currencyFormatter.format(row.notional_exposure_jpy || 0)}</span>
    </div>
  `).join("") || `<p class="muted">当前快照无期权持仓</p>`;
}

function renderPerformance(data) {
  performance.innerHTML = data.performance.map((row) => `
    <div class="row">
      <strong>${row.snapshot_time}</strong>
      <span>${currencyFormatter.format(row.total_assets_jpy || 0)}</span>
    </div>
  `).join("") || `<p class="muted">至少需要两个历史快照</p>`;
}

async function loadSnapshots() {
  const snapshots = await fetchJson("/api/snapshots");
  snapshotSelect.innerHTML = snapshots.map((row) => `
    <option value="${row.id}">${row.snapshot_time} · ${row.status}</option>
  `).join("");
  if (snapshots.length > 0) {
    snapshotSelect.value = snapshots[0].id;
    await loadDashboard(snapshots[0].id);
  }
}

async function loadDashboard(batchId) {
  const data = await fetchJson(`/api/dashboard?batch_id=${batchId}`);
  snapshotMeta.textContent = data.summary.snapshot_time || "暂无快照";
  renderSummary(data);
  renderTreemap(data);
  renderThemes(data);
  renderOptions(data);
  renderPerformance(data);
  showStatus(data.summary.status === "partial_success" ? data.summary.error_summary : "", data.summary.status === "partial_success");
}

async function loadThemes() {
  const mappings = await fetchJson("/api/themes");
  themeTable.innerHTML = mappings.map((row) => `
    <div class="row">
      <strong>${row.symbol}</strong>
      <span>${row.theme}</span>
    </div>
  `).join("") || `<p class="muted">暂无主题配置</p>`;
}

syncButton.addEventListener("click", async () => {
  syncButton.disabled = true;
  showStatus("正在同步账户数据", true);
  try {
    const result = await fetchJson("/api/sync/run", { method: "POST" });
    await loadSnapshots();
    snapshotSelect.value = String(result.batch_id);
    await loadDashboard(result.batch_id);
    showStatus("同步完成，已生成新快照", false);
  } catch (error) {
    showStatus("同步失败，请检查 moomoo OpenD 状态", true);
  } finally {
    syncButton.disabled = false;
  }
});

snapshotSelect.addEventListener("change", async () => {
  if (snapshotSelect.value) {
    await loadDashboard(snapshotSelect.value);
  }
});

themeModalButton.addEventListener("click", async () => {
  await loadThemes();
  themeModal.showModal();
});

saveThemeButton.addEventListener("click", async () => {
  const payload = {
    symbol: themeSymbol.value.trim().toUpperCase(),
    theme: themeName.value.trim(),
    display_name: themeDisplayName.value.trim() || null,
    color: themeColor.value.trim() || null,
    enabled: true
  };
  if (!payload.symbol || !payload.theme) {
    return;
  }
  await fetchJson("/api/themes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  await loadThemes();
  if (snapshotSelect.value) {
    await loadDashboard(snapshotSelect.value);
  }
});

loadSnapshots().catch(() => showStatus("暂无快照，请先同步 moomoo 账户数据", true));
```

- [ ] **Step 2: Mount the static files and index route**

Update `app/main.py`:

```python
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
```

Inside `create_app`, after `include_router(...)`:

```python
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse("app/static/index.html")
```

- [ ] **Step 3: Run the API tests to verify the app still passes**

Run:

```powershell
python -m pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add app/static app/main.py
git commit -m "feat: add single page dashboard frontend"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 10: Add the 07:00 JST Scheduler

**Files:**
- Create: `app/services/scheduler_service.py`
- Modify: `app/main.py`
- Test: `tests/test_scheduler_service.py`

- [ ] **Step 1: Write the failing scheduler tests**

Create `tests/test_scheduler_service.py`:

```python
from app.services.scheduler_service import should_run_scheduled_sync


def test_should_run_when_no_successful_scheduled_batch_exists_for_today():
    batches = [
        {"trigger_type": "manual", "status": "success", "snapshot_time": "2026-06-01T07:00:00+09:00"},
    ]
    assert should_run_scheduled_sync(batches, today="2026-06-01") is True


def test_should_not_run_when_successful_scheduled_batch_exists_for_today():
    batches = [
        {"trigger_type": "scheduled", "status": "success", "snapshot_time": "2026-06-01T07:00:00+09:00"},
    ]
    assert should_run_scheduled_sync(batches, today="2026-06-01") is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_scheduler_service.py -v
```

Expected: FAIL because `scheduler_service` does not exist.

- [ ] **Step 3: Add the scheduler helper**

Create `app/services/scheduler_service.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.sync_service import SyncService


def should_run_scheduled_sync(batches: list[dict], today: str) -> bool:
    for batch in batches:
        if (
            batch.get("trigger_type") == "scheduled"
            and batch.get("status") == "success"
            and str(batch.get("snapshot_time", "")).startswith(today)
        ):
            return False
    return True


def start_daily_scheduler(sync_service: SyncService) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")

    def run_daily_sync() -> None:
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        batches = sync_service.repository.list_batches()
        if sync_service.is_running():
            return
        if should_run_scheduled_sync(batches, today=today):
            sync_service.run_sync("scheduled")

    scheduler.add_job(
        run_daily_sync,
        trigger="cron",
        hour=7,
        minute=0,
        id="daily_moomoo_sync",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
```

- [ ] **Step 4: Wire the scheduler only in the production app path**

Update `app/main.py` imports:

```python
from app.services.scheduler_service import start_daily_scheduler
```

Update `create_app` signature:

```python
def create_app(database_path: Path | None = None, enable_scheduler: bool = False) -> FastAPI:
```

Inside `create_app`, before `return app`:

```python
    if enable_scheduler:
        start_daily_scheduler(sync_service)
```

Replace the module-level app line:

```python
app = create_app(enable_scheduler=True)
```

- [ ] **Step 5: Run the scheduler tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_scheduler_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Run the full test suite**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/services/scheduler_service.py app/main.py tests/test_scheduler_service.py
git commit -m "feat: add daily scheduled sync"
```

If the workspace is not a git repository, skip the commit and continue.

### Task 11: Final Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the real OpenD setup**

Append to `README.md`:

```markdown
## Real moomoo OpenD

This app connects directly to a real moomoo OpenD process.

Required:

- OpenD is running locally
- The selected account has read permission for account funds and positions
- The app can reach the configured OpenD host and port

The app is read-only. It uses account discovery, account info, and position APIs. It does not call unlock, order, or trade APIs.
```

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 3: Start the local server**

Run:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Expected: server starts at `http://127.0.0.1:8000`.

- [ ] **Step 4: Verify the API manually**

Run in another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/sync/run
Invoke-RestMethod http://127.0.0.1:8000/api/snapshots
```

Expected:

- health returns `{"status":"ok"}`
- manual sync returns a `batch_id`
- snapshots returns at least one successful or partial-success batch

- [ ] **Step 5: Verify the dashboard manually**

Open:

```text
http://127.0.0.1:8000
```

Expected:

- top bar shows sync button and snapshot selector
- overview cards render batch totals
- treemap renders positions
- theme modal can save a symbol mapping
- options section renders risk rows when option positions exist

- [ ] **Step 6: Commit**

```powershell
git add README.md
git commit -m "docs: add opend setup and verification instructions"
```

If the workspace is not a git repository, skip the commit and continue.

## Self-Review

**Spec coverage:**

- Real OpenD from day one: Task 5 and Task 6.
- SQLite foundation and migration script: Task 3.
- Smallest sync loop with account discovery, funds, positions, and snapshot write: Task 6.
- Snapshot list, dashboard payload, and manual sync APIs: Task 8.
- Editable theme mappings: Task 3, Task 8, and Task 9.
- Dashboard page with overview, treemap, themes, performance, and options: Task 9.
- 07:00 JST scheduled sync after manual sync stability: Task 10.

**Placeholder scan:**

- Removed fake-client-first language from the earlier draft.
- No `TODO`, `TBD`, or deferred “implement later” markers remain.

**Type consistency:**

- `SnapshotBatch.status` uses `success`, `partial_success`, `failed` across repository, service, and API.
- Theme writes consistently use `POST /api/themes`.
- Scheduler calls the same `run_sync("scheduled")` path as manual sync.
