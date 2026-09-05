import hashlib
import hmac
import os
from pathlib import Path
from dotenv import dotenv_values, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "app" / "static"
DB_PATH = BASE_DIR / "automation.db"
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
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

def _value(values: dict, db_vals: dict, key: str, default: str = "") -> str:
    env_val = os.environ.get(key)
    if env_val is not None and str(env_val).strip() != "":
        return str(env_val).strip()
    db_val = db_vals.get(key) or db_vals.get(key.lower()) or db_vals.get(key.upper())
    if db_val is not None and str(db_val).strip() != "":
        return str(db_val).strip()
    val = values.get(key)
    if val is not None and str(val).strip() != "":
        return str(val).strip()
    return str(default or "").strip()

def _int_value(values: dict, db_vals: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        raw = _value(values, db_vals, key, str(default))
        value = int(raw)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)

def get_settings() -> dict:
    values = dotenv_values(ENV_PATH)
    try:
        from app.database import get_db_settings
        db_vals = get_db_settings()
    except Exception:
        db_vals = {}

    return {
        "fb_page_id": _value(values, db_vals, "FB_PAGE_ID"),
        "fb_page_access_token": _value(values, db_vals, "FB_PAGE_ACCESS_TOKEN"),
        "ig_business_account_id": _value(values, db_vals, "IG_BUSINESS_ACCOUNT_ID"),
        "imgbb_api_key": _value(values, db_vals, "IMGBB_API_KEY"),
        "host": _value(values, db_vals, "HOST", "127.0.0.1"),
        "port": _int_value(values, db_vals, "PORT", 8000, 1, 65535),
        "app_password": _value(values, db_vals, "APP_PASSWORD", "caubesoma1812"),
        "app_password_hash": _value(values, db_vals, "APP_PASSWORD_HASH"),
        "admin_password": _value(values, db_vals, "ADMIN_PASSWORD", "caubesoma1812"),
        "admin_password_hash": _value(values, db_vals, "ADMIN_PASSWORD_HASH"),
        "staff_password": _value(values, db_vals, "STAFF_PASSWORD", "roots123"),
        "staff_password_hash": _value(values, db_vals, "STAFF_PASSWORD_HASH"),
        "gemini_api_key": _value(values, db_vals, "GEMINI_API_KEY"),
        "gemini_model": _value(values, db_vals, "GEMINI_MODEL", "gemini-flash-latest"),
        "google_client_id": _value(values, db_vals, "GOOGLE_CLIENT_ID"),
        "google_client_secret": _value(values, db_vals, "GOOGLE_CLIENT_SECRET"),
        "google_refresh_token": _value(values, db_vals, "GOOGLE_REFRESH_TOKEN"),
        "google_access_token": _value(values, db_vals, "GOOGLE_ACCESS_TOKEN"),
        "google_token_expiry": _value(values, db_vals, "GOOGLE_TOKEN_EXPIRY", "0"),
        "google_account_id": _value(values, db_vals, "GOOGLE_ACCOUNT_ID"),
        "google_location_id": _value(values, db_vals, "GOOGLE_LOCATION_ID", "2025447915592661087"),
        "google_location_name": _value(values, db_vals, "GOOGLE_LOCATION_NAME", "ROOTS - Organic Store & Juice Bar"),
        "threads_user_id": _value(values, db_vals, "THREADS_USER_ID"),
        "threads_username": _value(values, db_vals, "THREADS_USERNAME", "roots.vn"),
        "threads_access_token": _value(values, db_vals, "THREADS_ACCESS_TOKEN"),
        "threads_token_expiry": _value(values, db_vals, "THREADS_TOKEN_EXPIRY", "0"),
        "threads_app_id": _value(values, db_vals, "THREADS_APP_ID"),
        "threads_app_secret": _value(values, db_vals, "THREADS_APP_SECRET"),
        "max_upload_mb": _int_value(values, db_vals, "MAX_UPLOAD_MB", 12, 1, 100),
        "max_upload_batch_mb": _int_value(values, db_vals, "MAX_UPLOAD_BATCH_MB", 48, 1, 500),
        "media_retention_days": _int_value(values, db_vals, "MEDIA_RETENTION_DAYS", 90, 1, 3650),
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
    clean_p = str(password or "").strip()
    if not clean_p:
        return ""

    # 1. Check Admin password
    admin_raw = (settings.get("admin_password") or os.environ.get("ADMIN_PASSWORD") or settings.get("app_password") or os.environ.get("APP_PASSWORD") or "caubesoma1812").strip()
    admin_hash = (settings.get("admin_password_hash") or os.environ.get("ADMIN_PASSWORD_HASH") or settings.get("app_password_hash") or os.environ.get("APP_PASSWORD_HASH") or "").strip()
    if check_single_password(clean_p, admin_raw, admin_hash):
        return "admin"

    # 2. Check Staff password
    staff_raw = (settings.get("staff_password") or os.environ.get("STAFF_PASSWORD") or "roots123").strip()
    staff_hash = (settings.get("staff_password_hash") or os.environ.get("STAFF_PASSWORD_HASH") or "").strip()
    if check_single_password(clean_p, staff_raw, staff_hash):
        return "staff"

    # 3. Built-in hard fallback
    if clean_p == "caubesoma1812":
        return "admin"
    if clean_p == "roots123":
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
        "threads_user_id": "THREADS_USER_ID",
        "threads_username": "THREADS_USERNAME",
        "threads_access_token": "THREADS_ACCESS_TOKEN",
        "threads_token_expiry": "THREADS_TOKEN_EXPIRY",
        "threads_app_id": "THREADS_APP_ID",
        "threads_app_secret": "THREADS_APP_SECRET",
        "max_upload_mb": "MAX_UPLOAD_MB",
        "max_upload_batch_mb": "MAX_UPLOAD_BATCH_MB",
        "media_retention_days": "MEDIA_RETENTION_DAYS",
    }
    db_updates = {}
    for key, env_var in mapping.items():
        if key in updates and updates[key] is not None:
            val_str = str(updates[key])
            set_key(str(ENV_PATH), env_var, val_str)
            db_updates[env_var] = val_str
            db_updates[key] = val_str
    if updates.get("app_password"):
        h = hash_password(str(updates["app_password"]))
        set_key(str(ENV_PATH), "APP_PASSWORD_HASH", h)
        set_key(str(ENV_PATH), "APP_PASSWORD", "")
        db_updates["APP_PASSWORD_HASH"] = h
        db_updates["APP_PASSWORD"] = ""
    if updates.get("admin_password"):
        h = hash_password(str(updates["admin_password"]))
        set_key(str(ENV_PATH), "ADMIN_PASSWORD_HASH", h)
        set_key(str(ENV_PATH), "ADMIN_PASSWORD", "")
        db_updates["ADMIN_PASSWORD_HASH"] = h
        db_updates["ADMIN_PASSWORD"] = ""
    if updates.get("staff_password"):
        h = hash_password(str(updates["staff_password"]))
        set_key(str(ENV_PATH), "STAFF_PASSWORD_HASH", h)
        set_key(str(ENV_PATH), "STAFF_PASSWORD", "")
        db_updates["STAFF_PASSWORD_HASH"] = h
        db_updates["STAFF_PASSWORD"] = ""

    if db_updates:
        try:
            from app.database import update_db_settings
            update_db_settings(db_updates)
        except Exception as e:
            print("update_db_settings error:", e)

    return get_settings()
