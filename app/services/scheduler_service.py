from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.sync_service import SyncService


def should_run_scheduled_sync(batches: list[dict], today: str) -> bool:
    for batch in batches:
        if (
            batch.get("trigger_type") == "scheduled"
            and batch.get("status") == "success"
            and str(batch.get("snapshot_time", "")).startswith(today)
        ):
            return False
    return True


def start_daily_scheduler(sync_service: SyncService, hour: int = 7, minute: int = 0):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:
        raise RuntimeError("apscheduler is not installed") from exc

    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")

    def run_daily_sync() -> None:
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        batches = sync_service.repository.list_batches()
        if sync_service.is_running():
            return
        if should_run_scheduled_sync(batches, today=today):
            sync_service.run_sync("scheduled")

    scheduler.add_job(
        run_daily_sync,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_moomoo_sync",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
