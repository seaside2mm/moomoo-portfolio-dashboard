from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models.errors import SyncError
from app.models.snapshots import (
    AccountSnapshot,
    CategoryDefinition,
    PositionSnapshot,
    SnapshotBatch,
    SymbolCategoryOverride,
    ThemeMapping,
)
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository


def make_db_path() -> Path:
    base_dir = Path(".tmp_testdata")
    base_dir.mkdir(exist_ok=True)
    return base_dir / f"{uuid4().hex}.db"


def test_repo_initializes_and_lists_batches():
    repo = SQLiteSnapshotRepository(make_db_path())
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


def test_repo_persists_dashboard_related_rows():
    repo = SQLiteSnapshotRepository(make_db_path())
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


def test_repo_save_snapshot_bundle_persists_related_rows_in_one_call():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    batch_id = repo.save_snapshot_bundle(
        batch=SnapshotBatch(
            snapshot_time=datetime(2026, 6, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=1500000,
            total_pnl_jpy=120000,
            daily_pnl_jpy=8000,
            error_summary=None,
            created_at=datetime(2026, 6, 1, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        accounts=[
            AccountSnapshot(
                batch_id=0,
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
        ],
        positions=[
            PositionSnapshot(
                batch_id=0,
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
        ],
        options=[],
        rates=[],
        errors=[],
    )

    rows = repo.get_dashboard_rows(batch_id)
    assert rows["batch"][0]["id"] == batch_id
    assert rows["accounts"][0]["batch_id"] == batch_id
    assert rows["positions"][0]["batch_id"] == batch_id


def test_repo_lists_categories_and_upserts_symbol_category_override():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()

    categories = repo.list_category_definitions()
    assert any(item["category_code"] == "semiconductor" for item in categories)
    requested_sector_names = {
        "太空",
        "AI基建",
        "光通讯",
        "物理AI",
        "存储",
        "芯片",
        "ETF",
        "日股",
        "能源",
        "防御",
        "金融服务",
    }
    actual_sector_names = {
        item["category_name"]
        for item in categories
        if item["category_type"] == "sector"
    }
    assert requested_sector_names <= actual_sector_names
    assert "软件应用" not in actual_sector_names
    assert "特别组合" not in actual_sector_names

    result = repo.upsert_symbol_category_override(
        SymbolCategoryOverride(
            symbol="nvda",
            market="us",
            sector_code="semiconductor",
            industry_code="ai_chip",
            theme_code="ai",
            reason="manual test",
            enabled=True,
            updated_at=datetime(2026, 6, 2, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    assert result["symbol"] == "NVDA"
    assert result["market"] == "US"
    assert result["sector_name"] == "半导体"
    assert result["industry_name"] == "AI芯片"
    assert result["theme_name"] == "AI"

    overrides = repo.list_symbol_category_overrides()
    assert overrides[0]["symbol"] == "NVDA"
    assert overrides[0]["category_source"] == "manual"


def test_repo_rejects_override_with_wrong_category_type():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()

    try:
        repo.upsert_symbol_category_override(
            SymbolCategoryOverride(
                symbol="NVDA",
                market="US",
                sector_code="ai",
                industry_code=None,
                theme_code=None,
                reason=None,
                enabled=True,
                updated_at=datetime(2026, 6, 2, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            )
        )
    except ValueError as exc:
        assert "sector_code" in str(exc)
    else:
        raise AssertionError("expected invalid category type to be rejected")
