from contextlib import AbstractContextManager
from typing import Any


def default_filter_trdmarket() -> str:
    return "N/A"


def normalize_acc_id_for_query(acc_id: Any) -> Any:
    if isinstance(acc_id, str) and acc_id.isdigit():
        return int(acc_id)
    return acc_id


def should_sync_account(account_row: dict[str, Any]) -> bool:
    return str(account_row.get("trd_env", "")).upper() != "SIMULATE"


def build_account_query_params(account_row: dict[str, Any], currency: str = "USD") -> dict[str, Any]:
    acc_type = str(account_row.get("acc_type", "")).upper()
    return {
        "trd_env": str(account_row.get("trd_env", "REAL")),
        "currency": currency.upper(),
        "asset_category": "US" if acc_type == "DERIVATIVES" else "N/A",
    }


class MoomooClient(AbstractContextManager):
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.context = None

    def __enter__(self) -> "MoomooClient":
        try:
            from moomoo import OpenSecTradeContext
        except ImportError as exc:
            raise RuntimeError("moomoo Python SDK is not installed") from exc
        self.context = OpenSecTradeContext(
            filter_trdmarket=default_filter_trdmarket(),
            host=self.host,
            port=self.port,
        )
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self.context is not None:
            self.context.close()
            self.context = None

    def list_accounts(self) -> list[dict[str, Any]]:
        ret, data = self.context.get_acc_list()
        if ret != 0:
            raise RuntimeError(f"get_acc_list failed: {data}")
        return data.to_dict("records")

    def get_account_funds(self, account_id: str, account_row: dict[str, Any], currency: str = "USD") -> dict[str, Any]:
        query_params = build_account_query_params(account_row, currency)
        ret, data = self.context.accinfo_query(
            acc_id=normalize_acc_id_for_query(account_id),
            **query_params,
        )
        if ret != 0:
            raise RuntimeError(f"accinfo_query failed for {account_id}: {data}")
        records = data.to_dict("records")
        return records[0] if records else {}

    def get_positions(self, account_id: str, account_row: dict[str, Any]) -> list[dict[str, Any]]:
        query_params = build_account_query_params(account_row)
        ret, data = self.context.position_list_query(
            acc_id=normalize_acc_id_for_query(account_id),
            **query_params,
        )
        if ret != 0:
            raise RuntimeError(f"position_list_query failed for {account_id}: {data}")
        return data.to_dict("records")

    def get_account_cash_flows(
        self,
        account_id: str,
        account_row: dict[str, Any],
        clearing_date: str,
    ) -> list[dict[str, Any]]:
        ret, data = self.context.get_acc_cash_flow(
            acc_id=normalize_acc_id_for_query(account_id),
            trd_env=str(account_row.get("trd_env", "REAL")),
            clearing_date=clearing_date,
        )
        if ret != 0:
            raise RuntimeError(f"get_acc_cash_flow failed for {account_id} on {clearing_date}: {data}")
        return data.to_dict("records")
