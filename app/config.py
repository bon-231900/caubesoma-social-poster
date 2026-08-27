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
        "admin_password": _value(values, "ADMIN_PASSWORD"),
        "admin_password_hash": _value(values, "ADMIN_PASSWORD_HASH"),
        "staff_password": _value(values, "STAFF_PASSWORD"),
        "staff_password_hash": _value(values, "STAFF_PASSWORD_HASH"),
        "gemini_api_key": _value(values, "GEMINI_API_KEY"),
        "gemini_model": _value(values, "GEMINI_MODEL", "gemini-flash-latest"),
        "google_client_id": _value(values, "GOOGLE_CLIENT_ID"),
        "google_client_secret": _value(values, "GOOGLE_CLIENT_SECRET", "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"),
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

def check_single_password(password: str, raw_pass: str, hash_pass: str) -> bool:
    if hash_pass:
        try:
            algorithm, rounds, salt_hex, digest_hex = hash_pass.split("$", 3)
            if algorithm == "pbkdf2_sha256":
                candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
                if hmac.compare_digest(candidate.hex(), digest_hex):
                    return True
        except (TypeError, ValueError):
            pass
    if raw_pass and hmac.compare_digest(password, raw_pass):
        return True
    return False

def verify_user_role(password: str, settings: dict) -> str:
    """
    Returns 'admin', 'staff', or '' (invalid).
    """
    clean_p = str(password or "").strip()
    if not clean_p:
        return ""

    # 1. Check Admin password
    admin_raw = (settings.get("admin_password") or os.environ.get("ADMIN_PASSWORD") or "").strip()
    admin_hash = (settings.get("admin_password_hash") or os.environ.get("ADMIN_PASSWORD_HASH") or "").strip()
    if admin_raw or admin_hash:
        if check_single_password(clean_p, admin_raw, admin_hash):
            return "admin"
    else:
        # Fallback to APP_PASSWORD as admin if no separate admin password
        app_raw = (settings.get("app_password") or os.environ.get("APP_PASSWORD") or "").strip()
        app_hash = (settings.get("app_password_hash") or os.environ.get("APP_PASSWORD_HASH") or "").strip()
        if (app_raw or app_hash) and check_single_password(clean_p, app_raw, app_hash):
            return "admin"

    # 2. Check Staff password
    staff_raw = (settings.get("staff_password") or os.environ.get("STAFF_PASSWORD") or "").strip()
    staff_hash = (settings.get("staff_password_hash") or os.environ.get("STAFF_PASSWORD_HASH") or "").strip()
    if staff_raw or staff_hash:
        if check_single_password(clean_p, staff_raw, staff_hash):
            return "staff"

    return ""

def verify_password(password: str, settings: dict) -> bool:
    return bool(verify_user_role(password, settings))

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
    if updates.get("admin_password"):
        set_key(str(ENV_PATH), "ADMIN_PASSWORD_HASH", hash_password(str(updates["admin_password"])))
        set_key(str(ENV_PATH), "ADMIN_PASSWORD", "")
    if updates.get("staff_password"):
        set_key(str(ENV_PATH), "STAFF_PASSWORD_HASH", hash_password(str(updates["staff_password"])))
        set_key(str(ENV_PATH), "STAFF_PASSWORD", "")
    return get_settings()
