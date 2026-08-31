import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import BACKUP_DIR, DB_PATH, LOG_DIR, UPLOAD_DIR, get_settings
from app.database import get_db

logger = logging.getLogger(__name__)

def configure_logging():
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_DIR / "social-poster.log", encoding="utf-8"), logging.StreamHandler()],
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

def backup_database() -> Path:
    destination = BACKUP_DIR / f"automation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as source, sqlite3.connect(destination) as target:
            source.backup(target)
    else:
        destination.touch()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for old in BACKUP_DIR.glob("automation-*.db"):
        if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
            old.unlink(missing_ok=True)
    logger.info("Created database backup %s", destination.name)
    return destination

def cleanup_orphaned_media() -> int:
    settings = get_settings()
    retention = timedelta(days=settings["media_retention_days"])
    referenced = set()
    with get_db() as conn:
        for row in conn.execute("SELECT images, story_image FROM posts"):
            try:
                referenced.update(x for x in json.loads(row["images"] or "[]") if isinstance(x, str) and not x.startswith("http"))
            except json.JSONDecodeError:
                pass
            if row["story_image"]:
                referenced.add(row["story_image"])
    cutoff = datetime.now(timezone.utc) - retention
    deleted = 0
    for media in UPLOAD_DIR.iterdir():
        if not media.is_file() or media.name in referenced:
            continue
        if datetime.fromtimestamp(media.stat().st_mtime, timezone.utc) < cutoff:
            media.unlink(missing_ok=True)
            deleted += 1
    if deleted:
        logger.info("Removed %s orphaned media files", deleted)
    return deleted
