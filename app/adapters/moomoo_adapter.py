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
        risk_tag = self._derive_risk_tag(str(parsed["option_type"]), side)
        notional_original = abs(float(parsed["strike"]) * quantity * 100)
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
        try:
            parse_option_contract(raw_code)
            return "option"
        except Exception:
            pass
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
