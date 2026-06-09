from app.adapters.moomoo_client import (
    build_account_query_params,
    default_filter_trdmarket,
    normalize_acc_id_for_query,
    should_sync_account,
)


def test_default_filter_trdmarket_uses_none():
    assert default_filter_trdmarket() == "N/A"


def test_build_account_query_params_uses_us_asset_category_for_derivatives():
    params = build_account_query_params(
        {"acc_type": "DERIVATIVES", "trd_env": "REAL"}
    )
    assert params["trd_env"] == "REAL"
    assert params["currency"] == "USD"
    assert params["asset_category"] == "US"


def test_build_account_query_params_accepts_requested_currency():
    params = build_account_query_params(
        {"acc_type": "CASH", "trd_env": "REAL"},
        currency="JPY",
    )
    assert params["currency"] == "JPY"


def test_build_account_query_params_uses_none_asset_category_for_cash_accounts():
    params = build_account_query_params(
        {"acc_type": "CASH", "trd_env": "REAL"}
    )
    assert params["asset_category"] == "N/A"


def test_normalize_acc_id_for_query_converts_numeric_string_to_int():
    assert normalize_acc_id_for_query("1239628") == 1239628


def test_should_sync_account_skips_simulate_accounts():
    assert should_sync_account({"trd_env": "SIMULATE"}) is False
    assert should_sync_account({"trd_env": "REAL"}) is True
