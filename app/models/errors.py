from datetime import datetime

from pydantic import BaseModel


class SyncError(BaseModel):
    id: int | None = None
    batch_id: int | None = None
    account_id: str | None = None
    data_type: str
    error_code: str
    error_message: str
    raw_payload: str | None = None
    created_at: datetime
