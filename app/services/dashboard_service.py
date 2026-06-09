from collections import defaultdict
from typing import Any

from app.repositories.sqlite_snapshot_repo import SQLiteSnapshotRepository


AUTO_SECTOR_BY_SYMBOL = {
    "RKLB": ("space", "太空"),
    "SATS": ("space", "太空"),
    "SATG": ("space", "太空"),
    "UFO": ("space", "太空"),
    "ONDS": ("space", "太空"),
    "NVDA": ("chip", "芯片"),
    "AVGO": ("chip", "芯片"),
    "ASML": ("ai_infrastructure", "AI基建"),
    "DELL": ("ai_infrastructure", "AI基建"),
    "VRT": ("ai_infrastructure", "AI基建"),
    "ENPH": ("ai_infrastructure", "AI基建"),
    "ORCL": ("ai_infrastructure", "AI基建"),
    "MRVL": ("optical_communication", "光通讯"),
    "GLW": ("optical_communication", "光通讯"),
    "QCOM": ("chip", "芯片"),
    "TSLA": ("ai_app", "AI应用"),
    "SOUN": ("ai_app", "AI应用"),
    "LITE": ("optical_communication", "光通讯"),
    "COHR": ("optical_communication", "光通讯"),
    "TSEN": ("optical_communication", "光通讯"),
    "SIVE": ("optical_communication", "光通讯"),
    "SOL": ("optical_communication", "光通讯"),
    "SERV": ("physical_ai", "物理AI"),
    "SNDK": ("storage", "存储"),
    "MUU": ("storage", "存储"),
    "SOFI": ("financial_service", "金融服务"),
    "EWY": ("etf", "ETF"),
    "COPX": ("etf", "ETF"),
    "CRML": ("energy", "能源"),
    "HIMS": ("healthcare_trade", "医疗"),
    "MSTR": ("financial_service", "金融服务"),
    "CRCL": ("financial_service", "金融服务"),
}

def resolve_auto_sector(symbol: str) -> tuple[str, str] | None:
    normalized = symbol.upper()
    if match := AUTO_SECTOR_BY_SYMBOL.get(normalized):
        return match
    for known_symbol, sector in sorted(AUTO_SECTOR_BY_SYMBOL.items(), key=lambda item: len(item[0]), reverse=True):
        if normalized.startswith(known_symbol):
            return sector
        if normalized.startswith(known_symbol):
            return sector
    return None


def build_asset_allocation(positions: list[dict[str, Any]]) -> dict[str, float]:
    allocation = {"stock": 0.0, "option": 0.0, "cash": 0.0}
    for row in positions:
        asset_type = row.get("asset_type")
        value = float(row.get("market_value_jpy") or 0.0)
        if asset_type in allocation:
            allocation[asset_type] += value
    return allocation


def is_long_equity_position(row: dict[str, Any]) -> bool:
    asset_type = row.get("asset_type")
    quantity = float(row.get("quantity") or 0.0)
    market_value = float(row.get("market_value_jpy") or 0.0)
    return asset_type in {"stock", "etf"} and quantity > 0 and market_value > 0


def build_long_treemap_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in positions:
        if not is_long_equity_position(row):
            continue
        symbol = str(row.get("symbol", "")).upper()
        sector_name = row.get("sector_name") or "未分类"
        key = (symbol, sector_name)
        market_value = float(row.get("market_value_jpy") or 0.0)
        quantity = float(row.get("quantity") or 0.0)
        if key not in grouped:
            grouped[key] = {
                **row,
                "symbol": symbol,
                "sector_name": sector_name,
                "market_value_jpy": market_value,
                "quantity": quantity,
            }
        else:
            grouped[key]["market_value_jpy"] += market_value
            grouped[key]["quantity"] += quantity

    return sorted(grouped.values(), key=lambda item: float(item["market_value_jpy"]), reverse=True)


def calculate_trend_return_rate(
    current_total_assets_jpy: float | None,
    first_close_total_assets_jpy: float | None,
) -> float | None:
    if current_total_assets_jpy is None or first_close_total_assets_jpy in (None, 0):
        return None
    if first_close_total_assets_jpy <= 0:
        return None
    return (current_total_assets_jpy - first_close_total_assets_jpy) / first_close_total_assets_jpy


def enrich_positions_with_categories(rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    override_lookup = {
        (item["symbol"].upper(), item["market"].upper()): item
        for item in rows.get("category_overrides", [])
        if item.get("enabled")
    }
    theme_lookup = {item["symbol"].upper(): item for item in rows.get("themes", [])}
    enriched = []
    for row in rows["positions"]:
        item = dict(row)
        symbol = item["symbol"].upper()
        market = str(item.get("market", "OTHER")).upper()
        override = override_lookup.get((symbol, market))
        legacy_theme = theme_lookup.get(symbol)

        item.update(
            {
                "sector_code": None,
                "sector_name": "未分类",
                "industry_code": None,
                "industry_name": "未分类",
                "theme_code": None,
                "theme_name": "未分类",
                "category_source": "unclassified",
            }
        )
        if override:
            item.update(
                {
                    "sector_code": override.get("sector_code"),
                    "sector_name": override.get("sector_name") or "未分类",
                    "industry_code": override.get("industry_code"),
                    "industry_name": override.get("industry_name") or "未分类",
                    "theme_code": override.get("theme_code"),
                    "theme_name": override.get("theme_name") or "未分类",
                    "category_source": override.get("category_source") or "manual",
                }
            )
        elif auto_sector := resolve_auto_sector(symbol):
            item.update(
                {
                    "sector_code": auto_sector[0],
                    "sector_name": auto_sector[1],
                    "theme_name": auto_sector[1],
                    "category_source": "auto",
                }
            )
        elif legacy_theme:
            item.update(
                {
                    "sector_name": legacy_theme["theme"],
                    "theme_name": legacy_theme["theme"],
                    "category_source": "manual",
                }
            )
        enriched.append(item)
    return enriched


class DashboardService:
    def __init__(
        self,
        repository: SQLiteSnapshotRepository,
        manual_principal_jpy: float | None = None,
    ) -> None:
        self.repository = repository
        self.manual_principal_jpy = manual_principal_jpy

    def get_dashboard(self, batch_id: int | None = None) -> dict[str, Any]:
        batches = self.repository.list_batches()
        if not batches:
            return {
                "summary": {},
                "positions": [],
                "treemap": [],
                "themes": [],
                "performance": [],
                "options": [],
                "asset_allocation": {"stock": 0.0, "option": 0.0, "cash": 0.0},
            }

        selected_batch_id = batch_id or int(batches[0]["id"])
        rows = self.repository.get_dashboard_rows(selected_batch_id)
        batch = rows["batch"][0]
        positions = enrich_positions_with_categories(rows)

        theme_groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"theme": "未分类", "market_value_jpy": 0.0, "symbols": [], "positions": []}
        )
        total_assets = float(batch["total_assets_jpy"] or 0.0)
        for row in positions:
            if row.get("asset_type") == "option":
                continue
            symbol = row["symbol"].upper()
            sector_name = row.get("sector_name") or "未分类"
            market_value = float(row.get("market_value_jpy") or 0.0)
            share_ratio = (market_value / total_assets) if total_assets else 0.0
            group = theme_groups[sector_name]
            group["theme"] = sector_name
            group["market_value_jpy"] += market_value
            group["symbols"].append(symbol)
            existing_position = next((item for item in group["positions"] if item["symbol"] == symbol), None)
            if existing_position:
                existing_position["market_value_jpy"] += market_value
                existing_position["share_ratio"] += share_ratio
            else:
                group["positions"].append(
                    {
                        "symbol": symbol,
                        "name": row.get("name") or "",
                        "market_value_jpy": market_value,
                        "share_ratio": share_ratio,
                        "description": "",
                        "category_source": row.get("category_source") or "unclassified",
                    }
                )

        for group in theme_groups.values():
            group["share_ratio"] = (group["market_value_jpy"] / total_assets) if total_assets else 0.0
            group["positions"].sort(key=lambda item: abs(float(item["market_value_jpy"])), reverse=True)

        theme_cards = sorted(
            theme_groups.values(),
            key=lambda item: abs(float(item["market_value_jpy"])),
            reverse=True,
        )

        performance = [
            {
                "batch_id": item["id"],
                "snapshot_time": item["snapshot_time"],
                "total_assets_jpy": item["total_assets_jpy"],
                "total_pnl_jpy": item["total_pnl_jpy"],
                "daily_pnl_jpy": item["daily_pnl_jpy"],
            }
            for item in reversed(batches)
        ]
        first_close_total_assets_jpy = performance[0]["total_assets_jpy"] if performance else None
        principal_basis_jpy = self.manual_principal_jpy or first_close_total_assets_jpy
        trend_return_rate = calculate_trend_return_rate(
            batch.get("total_assets_jpy"),
            principal_basis_jpy,
        )

        return {
            "summary": {
                "batch_id": batch["id"],
                "snapshot_time": batch["snapshot_time"],
                "status": batch["status"],
                "net_inflow_jpy": batch.get("net_inflow_jpy"),
                "cumulative_return_rate": trend_return_rate,
                "principal_basis_jpy": principal_basis_jpy,
                "first_close_total_assets_jpy": first_close_total_assets_jpy,
                "first_close_snapshot_time": performance[0]["snapshot_time"] if performance else None,
                "total_assets_jpy": batch["total_assets_jpy"],
                "total_pnl_jpy": batch["total_pnl_jpy"],
                "daily_pnl_jpy": batch["daily_pnl_jpy"],
                "error_summary": batch["error_summary"],
            },
            "positions": positions,
            "treemap": build_long_treemap_positions(positions),
            "themes": theme_cards,
            "performance": performance,
            "options": rows["options"],
            "asset_allocation": build_asset_allocation(positions),
        }
