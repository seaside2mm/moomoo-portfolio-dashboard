from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models.snapshots import PositionSnapshot, SnapshotBatch, SymbolCategoryOverride
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository
from app.services.dashboard_service import (
    DashboardService,
    build_asset_allocation,
    build_long_treemap_positions,
    resolve_auto_sector,
)


def make_db_path() -> Path:
    base_dir = Path(".tmp_testdata")
    base_dir.mkdir(exist_ok=True)
    return base_dir / f"{uuid4().hex}.db"


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


def test_build_long_treemap_positions_keeps_only_positive_long_equities_and_merges_symbols():
    positions = [
        {"symbol": "QCOM", "sector_name": "芯片", "asset_type": "stock", "quantity": 2, "market_value_jpy": 100},
        {"symbol": "QCOM", "sector_name": "芯片", "asset_type": "stock", "quantity": 3, "market_value_jpy": 150},
        {"symbol": "SOFI260618P15000", "sector_name": "金融服务", "asset_type": "option", "quantity": -1, "market_value_jpy": -20},
        {"symbol": "SHORT", "sector_name": "未分类", "asset_type": "stock", "quantity": -5, "market_value_jpy": -80},
        {"symbol": "CASH", "sector_name": "现金", "asset_type": "cash", "quantity": 1, "market_value_jpy": 500},
    ]

    treemap_rows = build_long_treemap_positions(positions)

    assert len(treemap_rows) == 1
    assert treemap_rows[0]["symbol"] == "QCOM"
    assert treemap_rows[0]["quantity"] == 5
    assert treemap_rows[0]["market_value_jpy"] == 250


def test_dashboard_enriches_positions_and_groups_by_sector_category():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=1000000,
            total_pnl_jpy=100000,
            daily_pnl_jpy=5000,
            error_summary=None,
            created_at=datetime(2026, 6, 2, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
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
            market_value_jpy=180000,
            position_ratio=0.18,
        )
    ])
    repo.upsert_symbol_category_override(
        SymbolCategoryOverride(
            symbol="NVDA",
            market="US",
            sector_code="semiconductor",
            industry_code="ai_chip",
            theme_code="ai",
            reason="manual test",
            enabled=True,
            updated_at=datetime(2026, 6, 2, 8, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    data = DashboardService(repo).get_dashboard(batch_id)

    assert data["positions"][0]["sector_name"] == "半导体"
    assert data["positions"][0]["industry_name"] == "AI芯片"
    assert data["positions"][0]["theme_name"] == "AI"
    assert data["positions"][0]["category_source"] == "manual"
    assert data["themes"][0]["theme"] == "半导体"
    assert data["themes"][0]["symbols"] == ["NVDA"]


def test_dashboard_auto_assigns_known_symbols_to_sector_cards():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=1000000,
            total_pnl_jpy=100000,
            daily_pnl_jpy=5000,
            error_summary=None,
            created_at=datetime(2026, 6, 2, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
    repo.insert_position_snapshots([
        PositionSnapshot(
            batch_id=batch_id,
            account_id="ACC-1",
            symbol="RKLB",
            raw_code="US.RKLB",
            name="Rocket Lab",
            market="US",
            asset_type="stock",
            currency="USD",
            quantity=10,
            market_value_jpy=550000,
            position_ratio=0.55,
        ),
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
            market_value_jpy=150000,
            position_ratio=0.15,
        ),
    ])

    data = DashboardService(repo).get_dashboard(batch_id)
    themes = {item["theme"]: item for item in data["themes"]}

    assert data["positions"][0]["sector_name"] == "太空"
    assert data["positions"][0]["category_source"] == "auto"
    assert data["positions"][1]["sector_name"] == "芯片"
    assert themes["太空"]["share_ratio"] == 0.55
    assert themes["太空"]["positions"][0]["symbol"] == "RKLB"
    assert themes["芯片"]["positions"][0]["share_ratio"] == 0.15


def test_manual_override_takes_priority_over_auto_sector():
    assert resolve_auto_sector("NVDA") == ("chip", "芯片")

    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=1000000,
            created_at=datetime(2026, 6, 2, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
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
            market_value_jpy=100000,
            position_ratio=0.1,
        )
    ])
    repo.upsert_symbol_category_override(
        SymbolCategoryOverride(
            symbol="NVDA",
            market="US",
            sector_code="space",
            reason="manual test",
            enabled=True,
            updated_at=datetime(2026, 6, 2, 8, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    data = DashboardService(repo).get_dashboard(batch_id)

    assert data["positions"][0]["sector_name"] == "太空"
    assert data["positions"][0]["category_source"] == "manual"


def test_auto_sector_rules_cover_current_portfolio_symbols():
    expected = {
        "COHR": "光通讯",
        "MRVL": "光通讯",
        "SERV": "物理AI",
        "SOFI": "金融服务",
        "SNDK": "存储",
        "EWY": "ETF",
        "CRCL": "金融服务",
        "QCOM": "芯片",
        "NVDA": "芯片",
        "AVGO": "芯片",
        "GLW": "光通讯",
        "DELL": "AI基建",
        "CRML": "能源",
        "SOFI260618P15000": "金融服务",
    }

    for symbol, sector_name in expected.items():
        resolved = resolve_auto_sector(symbol)
        assert resolved is not None
        assert resolved[1] == sector_name

    assert resolve_auto_sector("MUU") == ("storage", "存储")


def test_tracked_symbols_follow_underlying_sector_group():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 4, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=1000000,
            created_at=datetime(2026, 6, 4, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
    repo.insert_position_snapshots([
        PositionSnapshot(
            batch_id=batch_id,
            account_id="ACC-1",
            symbol="MUU",
            raw_code="US.MUU",
            name="Leveraged ETF",
            market="US",
            asset_type="stock",
            currency="USD",
            quantity=1,
            market_value_jpy=80000,
            position_ratio=0.08,
        )
    ])

    data = DashboardService(repo).get_dashboard(batch_id)
    themes = {item["theme"]: item for item in data["themes"]}

    assert "存储" in themes
    assert themes["存储"]["positions"][0]["symbol"] == "MUU"


def test_dashboard_prefers_manual_principal_for_cumulative_return_rate():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=5500000,
            created_at=datetime(2026, 6, 2, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 4, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=6000000,
            created_at=datetime(2026, 6, 4, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    data = DashboardService(repo, manual_principal_jpy=5000000).get_dashboard(batch_id)

    assert data["summary"]["principal_basis_jpy"] == 5000000
    assert data["summary"]["cumulative_return_rate"] == 0.2


def test_dashboard_falls_back_to_first_close_when_manual_principal_missing():
    repo = SQLiteSnapshotRepository(make_db_path())
    repo.initialize()
    repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=5000000,
            created_at=datetime(2026, 6, 2, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )
    batch_id = repo.insert_batch(
        SnapshotBatch(
            snapshot_time=datetime(2026, 6, 4, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
            trigger_type="manual",
            status="success",
            total_assets_jpy=5750000,
            created_at=datetime(2026, 6, 4, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
    )

    data = DashboardService(repo).get_dashboard(batch_id)

    assert data["summary"]["principal_basis_jpy"] == 5000000
    assert data["summary"]["cumulative_return_rate"] == 0.15
