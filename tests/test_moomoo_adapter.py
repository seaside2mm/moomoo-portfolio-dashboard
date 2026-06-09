from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.adapters.fx_converter import FxConverter
from app.adapters.moomoo_adapter import MoomooAdapter
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
