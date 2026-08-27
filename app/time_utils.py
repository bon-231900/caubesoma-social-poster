from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def normalize_schedule(value: str | datetime) -> str:
    """Interpret naive user-entered times as Vietnam time and store UTC ISO-8601."""
    if isinstance(value, datetime):
        dt = value
    else:
        raw = (value or "").strip().replace("/", "-")
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            raise ValueError("Thời gian phải theo YYYY-MM-DD HH:MM hoặc YYYY-MM-DDTHH:MM.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc).isoformat()

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
