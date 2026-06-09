from app.services.scheduler_service import should_run_scheduled_sync


def test_should_run_when_no_successful_scheduled_batch_exists_for_today():
    batches = [
        {"trigger_type": "manual", "status": "success", "snapshot_time": "2026-06-01T07:00:00+09:00"},
    ]
    assert should_run_scheduled_sync(batches, today="2026-06-01") is True


def test_should_not_run_when_successful_scheduled_batch_exists_for_today():
    batches = [
        {"trigger_type": "scheduled", "status": "success", "snapshot_time": "2026-06-01T07:00:00+09:00"},
    ]
    assert should_run_scheduled_sync(batches, today="2026-06-01") is False
