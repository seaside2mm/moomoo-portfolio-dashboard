from dataclasses import dataclass
from datetime import date, datetime, timedelta
from time import sleep
from zoneinfo import ZoneInfo

from app.adapters.moomoo_adapter import MoomooAdapter
from app.adapters.moomoo_client import MoomooClient, should_sync_account
from app.config import Settings
from app.models.errors import SyncError
from app.models.snapshots import ExchangeRateSnapshot, SnapshotBatch
from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository


def _to_float(value: object) -> float | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_fx_rate(
    original_currency_row: dict,
    base_currency_row: dict,
    original_currency: str,
) -> float | None:
    if original_currency.upper() == "JPY":
        return 1.0
    for field_name in ("total_assets", "market_val", "cash", "power"):
        original_amount = _to_float(original_currency_row.get(field_name))
        base_amount = _to_float(base_currency_row.get(field_name))
        if original_amount not in (None, 0) and base_amount is not None:
            rate = base_amount / original_amount
            if rate > 0:
                return rate
    return None


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


def should_exclude_cash_flow(flow: dict) -> bool:
    flow_type = str(flow.get("cashflow_type") or "")
    remark = str(flow.get("cashflow_remark") or "")
    normalized = f"{flow_type} {remark}".lower()
    return "coupon deposit" in normalized or "卡券" in normalized


def normalize_cash_flow_amount(flow: dict) -> float | None:
    amount = _to_float(flow.get("cashflow_amount"))
    if amount is None:
        return None
    direction = str(flow.get("cashflow_direction") or "").upper()
    if direction == "OUT" and amount > 0:
        return -amount
    if direction == "IN" and amount < 0:
        return abs(amount)
    return amount


def calculate_net_inflow_jpy(flows: list[dict], fx_rates: dict[str, float]) -> float:
    total = 0.0
    for flow in flows:
        if should_exclude_cash_flow(flow):
            continue
        normalized_amount = normalize_cash_flow_amount(flow)
        currency = str(flow.get("currency") or "JPY").upper()
        if normalized_amount is None:
            continue
        rate = fx_rates.get(currency)
        if rate is None:
            continue
        total += normalized_amount * rate
    return total


def calculate_cumulative_return_rate(
    total_assets_jpy: float | None,
    net_inflow_jpy: float | None,
) -> float | None:
    if total_assets_jpy is None or net_inflow_jpy in (None, 0) or net_inflow_jpy <= 0:
        return None
    return (total_assets_jpy - net_inflow_jpy) / net_inflow_jpy


def collect_account_cash_flows(
    client: MoomooClient,
    account_id: str,
    account_row: dict,
    *,
    today: date,
    max_lookback_days: int = 365,
    stop_after_empty_days: int = 365,
    request_interval_seconds: float = 1.6,
) -> list[dict]:
    account_type = str(account_row.get("acc_type") or account_row.get("account_type") or "").upper()
    if account_type != "CASH":
        return []
    collected: list[dict] = []
    empty_streak = 0
    found_any = False
    for offset in range(max_lookback_days + 1):
        clearing_date = (today - timedelta(days=offset)).isoformat()
        rows = client.get_account_cash_flows(account_id, account_row, clearing_date)
        if rows:
            found_any = True
            empty_streak = 0
            collected.extend(rows)
        else:
            empty_streak += 1
        if found_any and empty_streak >= stop_after_empty_days:
            break
        sleep(request_interval_seconds)
    return collected


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
            all_cash_flows: list[dict] = []
            accounts_total = 0
            accounts_succeeded = 0
            accounts_failed = 0

            with MoomooClient(self.settings.moomoo_host, self.settings.moomoo_port) as client:
                account_rows = [row for row in client.list_accounts() if should_sync_account(row)]
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
                        original_currency = "USD"
                        original_funds_row = client.get_account_funds(account_id, account_row, original_currency)
                        funds_row = client.get_account_funds(account_id, account_row, self.settings.base_currency)
                        original_funds_row["acc_id"] = account_id
                        funds_row["acc_id"] = account_id
                        derived_rate = derive_fx_rate(original_funds_row, funds_row, original_currency)
                        if derived_rate:
                            self.adapter.fx_converter.set_rate(original_currency, derived_rate)
                        account_snapshot = self.adapter.to_account_snapshot(
                            batch_id=0,
                            account_info=funds_row,
                            metadata=metadata,
                        )
                        position_rows = client.get_positions(account_id, account_row)
                        batch_total_assets = account_snapshot.total_assets_jpy
                        if self.settings.cash_flow_lookback_days > 0:
                            cash_flow_rows = collect_account_cash_flows(
                                client,
                                account_id,
                                account_row,
                                today=now.date(),
                                max_lookback_days=self.settings.cash_flow_lookback_days,
                                stop_after_empty_days=self.settings.cash_flow_lookback_days,
                                request_interval_seconds=self.settings.cash_flow_request_interval_seconds,
                            )
                            all_cash_flows.extend(cash_flow_rows)

                        if account_snapshot.total_assets_jpy is not None:
                            account_totals.append(account_snapshot.total_assets_jpy)
                        if account_snapshot.total_pnl_jpy is not None:
                            total_pnls.append(account_snapshot.total_pnl_jpy)
                        if account_snapshot.daily_pnl_jpy is not None:
                            daily_pnls.append(account_snapshot.daily_pnl_jpy)

                        accounts.append(account_snapshot)
                        if derived_rate and original_currency != self.settings.base_currency.upper():
                            rates.append(
                                ExchangeRateSnapshot(
                                    batch_id=0,
                                    from_currency=original_currency,
                                    rate=derived_rate,
                                    rate_time=now,
                                )
                            )
                        elif original_currency != self.settings.base_currency.upper():
                            errors.append(
                                self.adapter.build_missing_fx_error(0, account_id, original_currency)
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
            deduped_cash_flows = list(
                {
                    (
                        str(item.get("cashflow_id") or ""),
                        str(item.get("currency") or ""),
                        str(item.get("cashflow_amount") or ""),
                        str(item.get("clearing_date") or ""),
                    ): item
                    for item in all_cash_flows
                }.values()
            )
            fx_rates = dict(self.adapter.fx_converter.rates)
            finalized_batch.net_inflow_jpy = calculate_net_inflow_jpy(deduped_cash_flows, fx_rates)
            finalized_batch.cumulative_return_rate = calculate_cumulative_return_rate(
                finalized_batch.total_assets_jpy,
                finalized_batch.net_inflow_jpy,
            )

            if finalized_batch.status == "failed":
                raise RuntimeError(finalized_batch.error_summary or "sync failed")

            batch_id = self.repository.save_snapshot_bundle(
                batch=finalized_batch,
                accounts=accounts,
                positions=positions,
                options=options,
                rates=rates,
                errors=errors,
            )

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
