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
CategoryType = Literal["sector", "industry", "theme"]


class SnapshotBatch(BaseModel):
    id: int | None = None
    snapshot_time: datetime
    trigger_type: TriggerType
    status: BatchStatus
    base_currency: str = "JPY"
    net_inflow_jpy: float | None = None
    cumulative_return_rate: float | None = None
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


class CategoryDefinition(BaseModel):
    id: int | None = None
    category_type: CategoryType
    category_code: str = Field(min_length=1, max_length=64)
    category_name: str = Field(min_length=1, max_length=80)
    parent_code: str | None = Field(default=None, max_length=64)
    sort_order: int = 0
    enabled: bool = True
    updated_at: datetime

    @field_validator("category_code")
    @classmethod
    def normalize_category_code(cls, value: str) -> str:
        return value.lower()


class SymbolCategoryOverride(BaseModel):
    id: int | None = None
    symbol: str = Field(min_length=1, max_length=32)
    market: Market = "US"
    sector_code: str | None = Field(default=None, max_length=64)
    industry_code: str | None = Field(default=None, max_length=64)
    theme_code: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=200)
    enabled: bool = True
    updated_at: datetime

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()

    @field_validator("market", mode="before")
    @classmethod
    def normalize_market(cls, value: str) -> str:
        return value.upper()

    @field_validator("sector_code", "industry_code", "theme_code")
    @classmethod
    def normalize_category_codes(cls, value: str | None) -> str | None:
        return value.lower() if value else None
