import json
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from app.config import DB_PATH
from app.time_utils import normalize_schedule

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT DEFAULT '',
                fb_caption TEXT DEFAULT '',
                ig_caption TEXT DEFAULT '',
                google_caption TEXT DEFAULT '',
                images TEXT DEFAULT '[]',
                target_fb INTEGER DEFAULT 1,
                target_ig INTEGER DEFAULT 1,
                target_story INTEGER DEFAULT 0,
                target_google INTEGER DEFAULT 0,
                google_action_type TEXT DEFAULT 'LEARN_MORE',
                google_action_url TEXT DEFAULT '',
                story_image TEXT,
                story_template TEXT DEFAULT 'glassmorphism',
                story_hook TEXT DEFAULT '',
                story_link TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                scheduled_time TEXT,
                created_at TEXT NOT NULL,
                published_at TEXT,
                fb_post_id TEXT,
                ig_post_id TEXT,
                google_post_id TEXT,
                story_fb_id TEXT,
                story_ig_id TEXT,
                error_log TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_attempt_at TEXT,
                platform_results TEXT DEFAULT '{}'
            )
        """)
        
        # Upgrade existing database schema if columns are missing
        cursor.execute("PRAGMA table_info(posts)")
        existing_cols = [r["name"] for r in cursor.fetchall()]
        cols_to_add = [
            ("target_story", "INTEGER DEFAULT 0"),
            ("story_image", "TEXT"),
            ("story_template", "TEXT DEFAULT 'glassmorphism'"),
            ("story_hook", "TEXT DEFAULT ''"),
            ("story_link", "TEXT DEFAULT ''"),
            ("story_fb_id", "TEXT"),
            ("story_ig_id", "TEXT"),
            ("google_caption", "TEXT DEFAULT ''"),
            ("target_google", "INTEGER DEFAULT 0"),
            ("google_action_type", "TEXT DEFAULT 'LEARN_MORE'"),
            ("google_action_url", "TEXT DEFAULT ''"),
            ("google_post_id", "TEXT"),
            ("attempt_count", "INTEGER DEFAULT 0"),
            ("last_attempt_at", "TEXT"),
            ("platform_results", "TEXT DEFAULT '{}'")
        ]
        for col_name, col_type in cols_to_add:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                role TEXT DEFAULT 'admin',
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("PRAGMA table_info(sessions)")
        sess_cols = [r["name"] for r in cursor.fetchall()]
        if "role" not in sess_cols:
            cursor.execute("ALTER TABLE sessions ADD COLUMN role TEXT DEFAULT 'admin'")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                state_hash TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL
            )
        """)

        # Media Library Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                original_name TEXT DEFAULT '',
                file_hash TEXT DEFAULT '',
                mime_type TEXT DEFAULT 'image/jpeg',
                file_size INTEGER DEFAULT 0,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)

        # Hashtag Groups Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hashtag_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hashtags TEXT NOT NULL,
                category TEXT DEFAULT 'Chung',
                created_at TEXT NOT NULL
            )
        """)

        # Caption Templates Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS caption_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'Sản phẩm',
                brand_voice TEXT DEFAULT 'Bán hàng',
                created_at TEXT NOT NULL
            )
        """)

        # Product AI Cache Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_ai_cache (
                product_id TEXT PRIMARY KEY,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Background Jobs Table (Dramatiq / Task Queue Pattern)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                current_step TEXT DEFAULT '',
                result_json TEXT DEFAULT '{}',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_due ON posts(status, scheduled_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_hash ON media_items(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON background_jobs(status)")

        # Seed default hashtag groups if empty
        cursor.execute("SELECT count(*) FROM hashtag_groups")
        if cursor.fetchone()[0] == 0:
            defaults_ht = [
                ("🌿 Sống Khỏe & Hữu Cơ", "#ROOTSOrganic #OrganicFood #HealthyLifestyle #CleanEating #EatCleanVN #ThucPhamHuuCo", "Hữu cơ"),
                ("🍹 Nước Ép & Detox", "#ROOTSJuiceBar #ColdPressedJuice #DetoxJuice #NuocEpHuuCo #FreshJuice #JuiceCleanse", "Đồ uống"),
                ("🔥 Deal Hot & Flash Sale", "#ROOTSFlashSale #SieuUuDai #GiaTotMoiNgay #HotDeal #KhuyenMaiHot #DealChopNhoang", "Khuyến mãi"),
                ("🍞 Bánh & Đồ Ăn Sáng", "#OrganicBakery #BanhMiHuuCo #BreakfastHealthy #HealthySnacks #EatFresh", "Bánh ngọt")
            ]
            for name, tags, cat in defaults_ht:
                cursor.execute(
                    "INSERT INTO hashtag_groups (name, hashtags, category, created_at) VALUES (?, ?, ?, ?)",
                    (name, tags, cat, utc_now_iso())
                )

        # Seed default caption templates if empty
        cursor.execute("SELECT count(*) FROM caption_templates")
        if cursor.fetchone()[0] == 0:
            defaults_tpl = [
                (
                    "Bán Hàng Thuyết Phục (Direct Sales)",
                    "🌿 {product_name} - Lựa chọn hữu cơ tươi ngon chuẩn quốc tế tại ROOTS!\n\n✨ Xuất xứ: {origin} | Thương hiệu: {brand}\n💰 Giá ưu đãi: {price} {discount}\n\n👉 Đặt ngay tại: {product_url} hoặc ghé trải nghiệm trực tiếp tại siêu thị ROOTS!",
                    "Sản phẩm",
                    "Bán hàng"
                ),
                (
                    "Góc Dinh Dưỡng & Sức Khỏe (Nutrition Expert)",
                    "✨ BẬT MÍ DINH DƯỠNG CÙNG {product_name}\n\nBạn có biết {product_name} giữ trọn vẹn enzyme và vitamin tự nhiên giúp thanh lọc cơ thể và nạp đầy năng lượng tươi mới mỗi ngày?\n\n🌱 100% hữu cơ, an toàn tuyệt đối cho cả gia đình.\n👉 Trải nghiệm ngay: {product_url}",
                    "Sức khỏe",
                    "Chuyên gia"
                ),
                (
                    "Thân Thiện & Đời Thường (Friendly Daily)",
                    "Một ngày mới tràn đầy năng lượng cùng {product_name}! ☀️\n\nChỉ một chút thanh mát từ {brand}, mọi mệt mỏi đều tan biến để bạn sẵn sàng cho những trải nghiệm tuyệt vời.\n\n❤️ Ghé thăm ROOTS hoặc đặt giao tận nhà ngay nhé: {product_url}",
                    "Đời sống",
                    "Thân thiện"
                ),
                (
                    "Bắt Trend & Sôi Động (Gen Z Viral)",
                    "🔥 HOT HIT CẬP BẾN ROOTS: {product_name}! 🚀\n\nVisual xinh xỉu, chất lượng 10/10 chuẩn organic không tì vết. Team healthy mau mau chốt đơn kẻo lỡ deal hời nha!\n\n🛒 Mua ngay tại: {product_url}",
                    "Khuyến mãi",
                    "Gen Z"
                )
            ]
            for name, content, cat, voice in defaults_tpl:
                cursor.execute(
                    "INSERT INTO caption_templates (name, content, category, brand_voice, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, content, cat, voice, utc_now_iso())
                )

        # Migrate historical local-time strings to timezone-aware UTC values once.
        for row in cursor.execute("SELECT id, scheduled_time FROM posts WHERE scheduled_time IS NOT NULL").fetchall():
            try:
                normalized = normalize_schedule(row["scheduled_time"])
            except ValueError:
                continue
            if normalized != row["scheduled_time"]:
                cursor.execute("UPDATE posts SET scheduled_time = ? WHERE id = ?", (normalized, row["id"]))
        conn.commit()

def create_post(
    fb_caption: str = "",
    ig_caption: str = "",
    google_caption: str = "",
    images: list = None,
    target_fb: bool = True,
    target_ig: bool = True,
    target_story: bool = False,
    target_google: bool = False,
    google_action_type: str = "LEARN_MORE",
    google_action_url: str = "",
    status: str = "draft",
    scheduled_time: str = None,
    title: str = "",
    story_image: str = None,
    story_template: str = "glassmorphism",
    story_hook: str = "",
    story_link: str = ""
) -> int:
    created_at = utc_now_iso()
    images_json = json.dumps(images or [])
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posts (
                title, fb_caption, ig_caption, google_caption, images,
                target_fb, target_ig, target_story, target_google,
                google_action_type, google_action_url,
                status, scheduled_time, created_at,
                story_image, story_template, story_hook, story_link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, fb_caption, ig_caption, google_caption, images_json,
            1 if target_fb else 0, 1 if target_ig else 0, 1 if target_story else 0, 1 if target_google else 0,
            google_action_type, google_action_url,
            status, scheduled_time, created_at,
            story_image, story_template, story_hook, story_link
        ))
        conn.commit()
        return cursor.lastrowid

def get_posts(limit: int = 100, status: str = None) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM posts WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            cursor.execute("SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d['images'] = json.loads(d['images'])
            except Exception:
                d['images'] = []
            try:
                d['platform_results'] = json.loads(d.get('platform_results') or '{}')
            except Exception:
                d['platform_results'] = {}
            result.append(d)
        return result

def get_post_by_id(post_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['images'] = json.loads(d['images'])
        except Exception:
            d['images'] = []
        try:
            d['platform_results'] = json.loads(d.get('platform_results') or '{}')
        except Exception:
            d['platform_results'] = {}
        return d

def update_post(post_id: int, **kwargs):
    fields = []
    values = []
    for k, v in kwargs.items():
        if k == 'images' and isinstance(v, list):
            v = json.dumps(v)
        if k == 'platform_results' and isinstance(v, dict):
            v = json.dumps(v)
        fields.append(f"{k} = ?")
        values.append(v)
    values.append(post_id)
    query = f"UPDATE posts SET {', '.join(fields)} WHERE id = ?"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()

def delete_post(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()

def get_due_scheduled_posts(now_iso: str = None) -> list:
    if not now_iso:
        now_iso = utc_now_iso()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM posts 
            WHERE status = 'scheduled' AND scheduled_time IS NOT NULL AND scheduled_time <= ?
            ORDER BY scheduled_time ASC
        """, (now_iso,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d['images'] = json.loads(d['images'])
            except Exception:
                d['images'] = []
            result.append(d)
    return result

def get_scheduled_posts() -> list:
    return get_due_scheduled_posts()

def claim_post_for_publish(post_id: int) -> bool:
    """Atomically reserve a post so UI clicks and scheduler cannot double-publish it."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE posts
            SET status = 'publishing', attempt_count = COALESCE(attempt_count, 0) + 1,
                last_attempt_at = ?
            WHERE id = ? AND status IN ('draft', 'scheduled', 'failed', 'partial_failed', 'approved')
        """, (utc_now_iso(), post_id))
        conn.commit()
        return cursor.rowcount == 1

def create_session(token: str, expires_at: str, role: str = "admin"):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions(token_hash, role, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), role, expires_at, utc_now_iso()),
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utc_now_iso(),))
        conn.commit()

def session_is_valid(token: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE token_hash = ? AND expires_at > ?",
            (hashlib.sha256(token.encode()).hexdigest(), utc_now_iso()),
        ).fetchone()
        return row is not None

def get_session_role(token: str) -> str:
    with get_db() as conn:
        row = conn.execute(
            "SELECT role FROM sessions WHERE token_hash = ? AND expires_at > ?",
            (hashlib.sha256(token.encode()).hexdigest(), utc_now_iso()),
        ).fetchone()
        if row and row["role"]:
            return str(row["role"])
        return "admin"

def approve_post(post_id: int, action: str = "publish_now") -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        if action == "publish_now":
            cursor.execute("UPDATE posts SET status = 'draft', scheduled_time = NULL WHERE id = ?", (post_id,))
        else:
            cursor.execute("UPDATE posts SET status = 'scheduled' WHERE id = ?", (post_id,))
        conn.commit()
        return cursor.rowcount > 0

def reject_post(post_id: int, reason: str = "") -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET status = 'rejected', error_log = ? WHERE id = ?", (reason or "Bị từ chối bởi Admin", post_id))
        conn.commit()
        return cursor.rowcount > 0

def delete_session(token: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()

def save_oauth_state(state: str, expires_at: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO oauth_states(state_hash, expires_at) VALUES (?, ?)",
                     (hashlib.sha256(state.encode()).hexdigest(), expires_at))
        conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (utc_now_iso(),))
        conn.commit()

def consume_oauth_state(state: str) -> bool:
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oauth_states WHERE state_hash = ? AND expires_at > ?", (state_hash, utc_now_iso()))
        conn.commit()
        return cursor.rowcount == 1

# ─────────────────────────────────────────────────────────────
# MEDIA LIBRARY CRUD
# ─────────────────────────────────────────────────────────────
def create_media_item(filename: str, original_name: str = "", file_hash: str = "", mime_type: str = "image/jpeg", file_size: int = 0, width: int = 0, height: int = 0, tags: list = None):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO media_items (filename, original_name, file_hash, mime_type, file_size, width, height, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (filename, original_name, file_hash, mime_type, file_size, width, height, json.dumps(tags or []), utc_now_iso()))
        conn.commit()

def get_media_items(search: str = "", tag: str = "", limit: int = 50, offset: int = 0) -> list:
    with get_db() as conn:
        query = "SELECT * FROM media_items WHERE 1=1"
        params = []
        if search:
            query += " AND (original_name LIKE ? OR filename LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if tag and tag != "all":
            query += " AND tags LIKE ?"
            params.append(f"%\"{tag}\"%")
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d['tags'] = json.loads(d['tags'])
            except Exception:
                d['tags'] = []
            result.append(d)
        return result

def get_media_by_hash(file_hash: str) -> dict:
    if not file_hash:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM media_items WHERE file_hash = ? LIMIT 1", (file_hash,)).fetchone()
        if row:
            d = dict(row)
            try:
                d["tags"] = json.loads(d.get("tags") or "[]")
            except Exception:
                d["tags"] = []
            return d
    return None

def update_media_tags(filename: str, tags: list):
    with get_db() as conn:
        conn.execute("UPDATE media_items SET tags = ? WHERE filename = ?", (json.dumps(tags or []), filename))
        conn.commit()

def delete_media_item(filename: str):
    with get_db() as conn:
        conn.execute("DELETE FROM media_items WHERE filename = ?", (filename,))
        conn.commit()

# ─────────────────────────────────────────────────────────────
# HASHTAG GROUPS & CAPTION TEMPLATES CRUD
# ─────────────────────────────────────────────────────────────
def get_hashtag_groups() -> list:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM hashtag_groups ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]

def create_hashtag_group(name: str, hashtags: str, category: str = "Chung") -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO hashtag_groups (name, hashtags, category, created_at) VALUES (?, ?, ?, ?)",
                       (name, hashtags, category, utc_now_iso()))
        conn.commit()
        return cursor.lastrowid

def delete_hashtag_group(group_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM hashtag_groups WHERE id = ?", (group_id,))
        conn.commit()

def get_caption_templates() -> list:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM caption_templates ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]

def create_caption_template(name: str, content: str, category: str = "Sản phẩm", brand_voice: str = "Bán hàng") -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO caption_templates (name, content, category, brand_voice, created_at) VALUES (?, ?, ?, ?, ?)",
                       (name, content, category, brand_voice, utc_now_iso()))
        conn.commit()
        return cursor.lastrowid

def delete_caption_template(template_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM caption_templates WHERE id = ?", (template_id,))
        conn.commit()

# ─────────────────────────────────────────────────────────────
# PRODUCT AI CACHE
# ─────────────────────────────────────────────────────────────
def get_product_ai_cache(product_id: str) -> dict:
    if not product_id:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT payload_json FROM product_ai_cache WHERE product_id = ?", (str(product_id),)).fetchone()
        if row:
            try:
                return json.loads(row["payload_json"])
            except Exception:
                return None
    return None

def set_product_ai_cache(product_id: str, cache_key: str, payload: dict):
    if not product_id:
        return
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO product_ai_cache (product_id, cache_key, payload_json, updated_at) VALUES (?, ?, ?, ?)",
            (str(product_id), cache_key, json.dumps(payload, ensure_ascii=False), utc_now_iso())
        )
        conn.commit()

# ─────────────────────────────────────────────────────────────
# BACKGROUND JOBS CRUD
# ─────────────────────────────────────────────────────────────
def create_job_record(job_id: str, job_type: str, status: str = "pending", progress: int = 0, current_step: str = "") -> dict:
    now = utc_now_iso()
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO background_jobs (job_id, job_type, status, progress, current_step, result_json, error_message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, '{}', '', ?, ?)
        """, (job_id, job_type, status, progress, current_step, now, now))
        conn.commit()
    return get_job_record(job_id)

def update_job_record(job_id: str, status: str = None, progress: int = None, current_step: str = None, result: dict = None, error: str = None):
    updates = []
    params = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if progress is not None:
        updates.append("progress = ?")
        params.append(progress)
    if current_step is not None:
        updates.append("current_step = ?")
        params.append(current_step)
    if result is not None:
        updates.append("result_json = ?")
        params.append(json.dumps(result, ensure_ascii=False))
    if error is not None:
        updates.append("error_message = ?")
        params.append(error)
    
    updates.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(job_id)

    with get_db() as conn:
        conn.execute(f"UPDATE background_jobs SET {', '.join(updates)} WHERE job_id = ?", params)
        conn.commit()

def get_job_record(job_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM background_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row:
            d = dict(row)
            try:
                d["result"] = json.loads(d.get("result_json") or "{}")
            except Exception:
                d["result"] = {}
            return d
    return None
