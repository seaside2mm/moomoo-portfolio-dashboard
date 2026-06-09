from pydantic import BaseModel


class SnapshotListItem(BaseModel):
    batch_id: int
    snapshot_time: str
    trigger_type: str
    status: str
    total_assets_jpy: float | None = None
    total_pnl_jpy: float | None = None
    daily_pnl_jpy: float | None = None
    error_summary: str | None = None
