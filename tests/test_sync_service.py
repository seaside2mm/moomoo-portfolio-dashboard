from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.snapshots import SnapshotBatch
from app.services.sync_service import (
    calculate_cumulative_return_rate,
    calculate_net_inflow_jpy,
    derive_fx_rate,
    summarize_batch,
)


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


def test_derive_fx_rate_uses_moomoo_base_and_original_currency_rows():
    rate = derive_fx_rate(
        original_currency_row={"currency": "USD", "total_assets": 39485.2245},
        base_currency_row={"currency": "JPY", "total_assets": 6310909.7146},
        original_currency="USD",
    )
    assert rate is not None
    assert round(rate, 4) == 159.8297


def test_derive_fx_rate_falls_back_to_market_value_when_total_assets_is_zero():
    rate = derive_fx_rate(
        original_currency_row={"currency": "USD", "total_assets": 0, "market_val": -11.5},
        base_currency_row={"currency": "JPY", "total_assets": 0, "market_val": -1838.0508},
        original_currency="USD",
    )
    assert rate is not None
    assert round(rate, 4) == 159.8305


def test_calculate_net_inflow_jpy_excludes_coupon_rewards_and_normalizes_outflows():
    flows = [
        {
            "cashflow_amount": 1000,
            "cashflow_direction": "IN",
            "currency": "USD",
            "cashflow_type": "其他",
            "cashflow_remark": "",
        },
        {
            "cashflow_amount": -200,
            "cashflow_direction": "OUT",
            "currency": "USD",
            "cashflow_type": "其他",
            "cashflow_remark": "",
        },
        {
            "cashflow_amount": 50,
            "cashflow_direction": "IN",
            "currency": "USD",
            "cashflow_type": "卡券",
            "cashflow_remark": "Coupon Deposit",
        },
        {
            "cashflow_amount": 3000,
            "cashflow_direction": "IN",
            "currency": "JPY",
            "cashflow_type": "其他",
            "cashflow_remark": "",
        },
    ]

    net_inflow = calculate_net_inflow_jpy(flows, {"USD": 150.0, "JPY": 1.0})

    assert net_inflow == 123000


def test_calculate_cumulative_return_rate_uses_net_inflow_as_principal():
    rate = calculate_cumulative_return_rate(total_assets_jpy=135000, net_inflow_jpy=100000)
    assert rate == 0.35


def test_calculate_cumulative_return_rate_returns_none_without_positive_principal():
    assert calculate_cumulative_return_rate(total_assets_jpy=100000, net_inflow_jpy=0) is None
