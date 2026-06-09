import sqlite3
from pathlib import Path
from typing import Any

from app.models.errors import SyncError
from app.models.snapshots import (
    AccountSnapshot,
    CategoryDefinition,
    ExchangeRateSnapshot,
    OptionSnapshot,
    PositionSnapshot,
    SnapshotBatch,
    SymbolCategoryOverride,
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
            self._ensure_snapshot_batch_column(connection, "net_inflow_jpy", "REAL")
            self._ensure_snapshot_batch_column(connection, "cumulative_return_rate", "REAL")

    def save_snapshot_bundle(
        self,
        batch: SnapshotBatch,
        accounts: list[AccountSnapshot],
        positions: list[PositionSnapshot],
        options: list[OptionSnapshot],
        rates: list[ExchangeRateSnapshot],
        errors: list[SyncError],
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO snapshot_batches (
                  snapshot_time, trigger_type, status, base_currency,
                  net_inflow_jpy, cumulative_return_rate, total_assets_jpy,
                  total_pnl_jpy, daily_pnl_jpy, error_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.snapshot_time.isoformat(),
                    batch.trigger_type,
                    batch.status,
                    batch.base_currency,
                    batch.net_inflow_jpy,
                    batch.cumulative_return_rate,
                    batch.total_assets_jpy,
                    batch.total_pnl_jpy,
                    batch.daily_pnl_jpy,
                    batch.error_summary,
                    batch.created_at.isoformat(),
                ),
            )
            batch_id = int(cursor.lastrowid)

            if accounts:
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
                            batch_id,
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

            if positions:
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
                            batch_id,
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

            if options:
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
                            batch_id,
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

            if rates:
                connection.executemany(
                    """
                    INSERT INTO exchange_rates (batch_id, from_currency, to_currency, rate, source, rate_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            batch_id,
                            item.from_currency,
                            item.to_currency,
                            item.rate,
                            item.source,
                            item.rate_time.isoformat(),
                        )
                        for item in rates
                    ],
                )

            if errors:
                connection.executemany(
                    """
                    INSERT INTO sync_errors (batch_id, account_id, data_type, error_code, error_message, raw_payload, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            batch_id,
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

            return batch_id

    def insert_batch(self, batch: SnapshotBatch) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO snapshot_batches (
                  snapshot_time, trigger_type, status, base_currency,
                  net_inflow_jpy, cumulative_return_rate, total_assets_jpy,
                  total_pnl_jpy, daily_pnl_jpy, error_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.snapshot_time.isoformat(),
                    batch.trigger_type,
                    batch.status,
                    batch.base_currency,
                    batch.net_inflow_jpy,
                    batch.cumulative_return_rate,
                    batch.total_assets_jpy,
                    batch.total_pnl_jpy,
                    batch.daily_pnl_jpy,
                    batch.error_summary,
                    batch.created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def insert_account_snapshots(self, accounts: list[AccountSnapshot]) -> None:
        if not accounts:
            return
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
        if not positions:
            return
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
        if not options:
            return
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
        if not rates:
            return
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
        if not errors:
            return
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

    def list_category_definitions(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM category_definitions
                WHERE enabled = 1
                ORDER BY category_type, sort_order, category_name
                """
            ).fetchall()
        return [self._normalize_bool_fields(dict(row), ("enabled",)) for row in rows]

    def upsert_category_definition(self, definition: CategoryDefinition) -> dict[str, Any]:
        code = definition.category_code.lower()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO category_definitions (
                  category_type, category_code, category_name, parent_code,
                  sort_order, enabled, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category_code) DO UPDATE SET
                  category_type = excluded.category_type,
                  category_name = excluded.category_name,
                  parent_code = excluded.parent_code,
                  sort_order = excluded.sort_order,
                  enabled = excluded.enabled,
                  updated_at = excluded.updated_at
                """,
                (
                    definition.category_type,
                    code,
                    definition.category_name,
                    definition.parent_code,
                    definition.sort_order,
                    1 if definition.enabled else 0,
                    definition.updated_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM category_definitions WHERE category_code = ?",
                (code,),
            ).fetchone()
        return self._normalize_bool_fields(dict(row), ("enabled",))

    def list_symbol_category_overrides(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = self._select_symbol_category_overrides(connection).fetchall()
        return [self._category_override_row_to_dict(row) for row in rows]

    def upsert_symbol_category_override(self, override: SymbolCategoryOverride) -> dict[str, Any]:
        symbol = override.symbol.upper()
        market = override.market.upper()
        with self._connect() as connection:
            self._validate_category_code(connection, override.sector_code, "sector", "sector_code")
            self._validate_category_code(connection, override.industry_code, "industry", "industry_code")
            self._validate_category_code(connection, override.theme_code, "theme", "theme_code")
            connection.execute(
                """
                INSERT INTO symbol_category_overrides (
                  symbol, market, sector_code, industry_code, theme_code,
                  reason, enabled, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, market) DO UPDATE SET
                  sector_code = excluded.sector_code,
                  industry_code = excluded.industry_code,
                  theme_code = excluded.theme_code,
                  reason = excluded.reason,
                  enabled = excluded.enabled,
                  updated_at = excluded.updated_at
                """,
                (
                    symbol,
                    market,
                    override.sector_code,
                    override.industry_code,
                    override.theme_code,
                    override.reason,
                    1 if override.enabled else 0,
                    override.updated_at.isoformat(),
                ),
            )
            row = self._select_symbol_category_overrides(connection, symbol, market).fetchone()
        return self._category_override_row_to_dict(row)

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
                "SELECT * FROM theme_mappings WHERE enabled = 1 ORDER BY theme, symbol"
            ).fetchall()
            category_overrides = self._select_symbol_category_overrides(connection, enabled_only=True).fetchall()
        return {
            "batch": [dict(batch)] if batch else [],
            "accounts": [dict(row) for row in accounts],
            "positions": [dict(row) for row in positions],
            "options": [dict(row) for row in options],
            "errors": [dict(row) for row in errors],
            "themes": [dict(row) for row in themes],
            "category_overrides": [self._category_override_row_to_dict(row) for row in category_overrides],
        }

    def _validate_category_code(
        self,
        connection: sqlite3.Connection,
        code: str | None,
        expected_type: str,
        field_name: str,
    ) -> None:
        if not code:
            return
        row = connection.execute(
            """
            SELECT category_type FROM category_definitions
            WHERE category_code = ? AND enabled = 1
            """,
            (code,),
        ).fetchone()
        if row is None or row["category_type"] != expected_type:
            raise ValueError(f"{field_name} must reference an enabled {expected_type} category")

    def _select_symbol_category_overrides(
        self,
        connection: sqlite3.Connection,
        symbol: str | None = None,
        market: str | None = None,
        enabled_only: bool = False,
    ) -> sqlite3.Cursor:
        filters = []
        params: list[Any] = []
        if symbol is not None:
            filters.append("sco.symbol = ?")
            params.append(symbol)
        if market is not None:
            filters.append("sco.market = ?")
            params.append(market)
        if enabled_only:
            filters.append("sco.enabled = 1")
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        return connection.execute(
            f"""
            SELECT
              sco.*,
              sector.category_name AS sector_name,
              industry.category_name AS industry_name,
              theme.category_name AS theme_name,
              'manual' AS category_source
            FROM symbol_category_overrides sco
            LEFT JOIN category_definitions sector
              ON sector.category_code = sco.sector_code AND sector.category_type = 'sector'
            LEFT JOIN category_definitions industry
              ON industry.category_code = sco.industry_code AND industry.category_type = 'industry'
            LEFT JOIN category_definitions theme
              ON theme.category_code = sco.theme_code AND theme.category_type = 'theme'
            {where_clause}
            ORDER BY sco.market, sco.symbol
            """,
            params,
        )

    def _category_override_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        return self._normalize_bool_fields(data, ("enabled",))

    def _normalize_bool_fields(self, data: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        for field in fields:
            if field in data:
                data[field] = bool(data[field])
        return data

    def _ensure_snapshot_batch_column(
        self,
        connection: sqlite3.Connection,
        column_name: str,
        column_type: str,
    ) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(snapshot_batches)").fetchall()
        }
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE snapshot_batches ADD COLUMN {column_name} {column_type}")
