import hashlib
import hmac
import os
from pathlib import Path
from dotenv import dotenv_values, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "app" / "static"
DB_PATH = BASE_DIR / "automation.db"
ENV_PATH = BASE_DIR / ".env"
LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backups"

for directory in (UPLOAD_DIR, LOG_DIR, BACKUP_DIR):
    directory.mkdir(parents=True, exist_ok=True)

if not ENV_PATH.exists():
    example_path = BASE_DIR / ".env.example"
    if example_path.exists():
        ENV_PATH.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        ENV_PATH.write_text("", encoding="utf-8")

def _value(values: dict, key: str, default: str = "") -> str:
    val = values.get(key)
    if val is None or str(val).strip() == "":
        val = os.environ.get(key, default)
    return str(val or "").strip()

def _int_value(values: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        raw = _value(values, key, str(default))
        value = int(raw)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)

def get_settings() -> dict:
    values = dotenv_values(ENV_PATH)
    return {
        "fb_page_id": _value(values, "FB_PAGE_ID"),
        "fb_page_access_token": _value(values, "FB_PAGE_ACCESS_TOKEN"),
        "ig_business_account_id": _value(values, "IG_BUSINESS_ACCOUNT_ID"),
        "imgbb_api_key": _value(values, "IMGBB_API_KEY"),
        "host": _value(values, "HOST", "127.0.0.1"),
        "port": _int_value(values, "PORT", 8000, 1, 65535),
        "app_password": _value(values, "APP_PASSWORD"),
        "app_password_hash": _value(values, "APP_PASSWORD_HASH"),
        "gemini_api_key": _value(values, "GEMINI_API_KEY"),
        "gemini_model": _value(values, "GEMINI_MODEL", "gemini-flash-latest"),
        "google_client_id": _value(values, "GOOGLE_CLIENT_ID"),
        "google_client_secret": _value(values, "GOOGLE_CLIENT_SECRET"),
        "google_refresh_token": _value(values, "GOOGLE_REFRESH_TOKEN"),
        "google_access_token": _value(values, "GOOGLE_ACCESS_TOKEN"),
        "google_token_expiry": _value(values, "GOOGLE_TOKEN_EXPIRY", "0"),
        "google_account_id": _value(values, "GOOGLE_ACCOUNT_ID"),
        "google_location_id": _value(values, "GOOGLE_LOCATION_ID"),
        "google_location_name": _value(values, "GOOGLE_LOCATION_NAME"),
        "max_upload_mb": _int_value(values, "MAX_UPLOAD_MB", 12, 1, 100),
        "max_upload_batch_mb": _int_value(values, "MAX_UPLOAD_BATCH_MB", 48, 1, 500),
        "media_retention_days": _int_value(values, "MEDIA_RETENTION_DAYS", 90, 1, 3650),
    }

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    rounds = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"

def verify_password(password: str, settings: dict) -> bool:
    stored = settings.get("app_password_hash", "")
    if stored:
        try:
            algorithm, rounds, salt_hex, digest_hex = stored.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
            return hmac.compare_digest(candidate.hex(), digest_hex)
        except (TypeError, ValueError):
            return False
    return bool(settings.get("app_password")) and hmac.compare_digest(password, settings["app_password"])

def update_settings(updates: dict):
    mapping = {
        "fb_page_id": "FB_PAGE_ID",
        "fb_page_access_token": "FB_PAGE_ACCESS_TOKEN",
        "ig_business_account_id": "IG_BUSINESS_ACCOUNT_ID",
        "imgbb_api_key": "IMGBB_API_KEY",
        "host": "HOST",
        "port": "PORT",
        "gemini_api_key": "GEMINI_API_KEY",
        "gemini_model": "GEMINI_MODEL",
        "google_client_id": "GOOGLE_CLIENT_ID",
        "google_client_secret": "GOOGLE_CLIENT_SECRET",
        "google_refresh_token": "GOOGLE_REFRESH_TOKEN",
        "google_access_token": "GOOGLE_ACCESS_TOKEN",
        "google_token_expiry": "GOOGLE_TOKEN_EXPIRY",
        "google_account_id": "GOOGLE_ACCOUNT_ID",
        "google_location_id": "GOOGLE_LOCATION_ID",
        "google_location_name": "GOOGLE_LOCATION_NAME",
        "max_upload_mb": "MAX_UPLOAD_MB",
        "max_upload_batch_mb": "MAX_UPLOAD_BATCH_MB",
        "media_retention_days": "MEDIA_RETENTION_DAYS",
    }
    for key, env_var in mapping.items():
        if key in updates and updates[key] is not None:
            set_key(str(ENV_PATH), env_var, str(updates[key]))
    if updates.get("app_password"):
        set_key(str(ENV_PATH), "APP_PASSWORD_HASH", hash_password(str(updates["app_password"])))
        set_key(str(ENV_PATH), "APP_PASSWORD", "")
    return get_settings()
