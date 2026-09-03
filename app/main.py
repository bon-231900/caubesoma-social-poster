import os
import uuid
import io
import asyncio
import secrets
import logging
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError

from app.config import UPLOAD_DIR, STATIC_DIR, get_settings, update_settings, verify_password, verify_user_role
from app.database import (init_db, create_post, get_posts, get_post_by_id, update_post, delete_post,
                          create_session, session_is_valid, delete_session, get_session_role,
                          approve_post, reject_post, save_oauth_state,
                          consume_oauth_state, create_media_item, get_media_items, update_media_tags,
                          delete_media_item, get_hashtag_groups, create_hashtag_group, delete_hashtag_group,
                          get_caption_templates, create_caption_template, delete_caption_template)
from app.scheduler import start_scheduler, shutdown_scheduler, publish_single_post
from app.meta_service import test_meta_connection, exchange_for_permanent_page_token
from app.ai_service import generate_social_captions, generate_combo_campaign_and_prompts
from app.bulk_service import generate_bulk_excel_template, parse_bulk_file, import_bulk_posts
from app.story_service import create_story_image
from app.google_service import get_google_auth_url, exchange_google_code, get_google_locations, publish_to_google_business
from app.roots_service import fetch_roots_categories, fetch_roots_products, fetch_roots_flash_sale, quick_generate_post_from_product
from app.job_manager import job_manager, run_1click_studio_job
from app.media_service import register_media_file, THUMB_DIR, create_thumbnail
from app.template_service import DEFAULT_VARIABLES, resolve_caption_variables
from app.time_utils import normalize_schedule
from app.maintenance import configure_logging, backup_database, cleanup_orphaned_media

def create_session_token(role: str = "admin") -> str:
    token = secrets.token_urlsafe(48)
    create_session(token, (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(), role=role)
    return token

def verify_auth(authorization: Optional[str] = Header(None), request: Request = None) -> dict:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif request and "session_token" in request.cookies:
        token = request.cookies["session_token"]
        
    if not token or not session_is_valid(token):
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên làm việc đã hết hạn.")
    role = get_session_role(token)
    return {"token": token, "role": role}

def verify_admin_auth(auth: dict = Depends(verify_auth)) -> dict:
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chức năng này chỉ dành riêng cho Quản trị viên (Admin).")
    return auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(title="Social Auto Poster", lifespan=lifespan)

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.get("/")
def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        resp = FileResponse(str(index_file))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return {"message": "Social Auto Poster API running"}

@app.get("/api/health")
def api_health():
    """Unauthenticated, non-sensitive status endpoint for local monitoring."""
    return {"status": "ok", "service": "social-auto-poster"}

# --- MODELS ---
class LoginRequest(BaseModel):
    password: str

class PostCreateRequest(BaseModel):
    fb_caption: str = ""
    ig_caption: str = ""
    google_caption: str = ""
    images: List[str] = []
    target_fb: bool = True
    target_ig: bool = True
    target_story: bool = False
    target_google: bool = False
    google_action_type: str = "LEARN_MORE"
    google_action_url: Optional[str] = None
    story_image: Optional[str] = None
    story_template: str = "glassmorphism"
    story_hook: str = ""
    story_link: str = ""
    action: str = "now"
    scheduled_time: Optional[str] = None

class StoryPreviewRequest(BaseModel):
    image_name: str
    caption: str = ""
    template: str = "glassmorphism"
    hook: str = ""
    link: str = ""

class AICaptionRequest(BaseModel):
    images: List[str] = []
    user_hint: str = ""

class BulkImportRequest(BaseModel):
    posts: List[dict]

class SettingsUpdateRequest(BaseModel):
    fb_page_id: Optional[str] = None
    fb_page_access_token: Optional[str] = None
    ig_business_account_id: Optional[str] = None
    imgbb_api_key: Optional[str] = None
    app_password: Optional[str] = None
    admin_password: Optional[str] = None
    staff_password: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_account_id: Optional[str] = None
    google_location_id: Optional[str] = None
    google_location_name: Optional[str] = None
    max_upload_mb: Optional[int] = None
    max_upload_batch_mb: Optional[int] = None
    media_retention_days: Optional[int] = None

class SettingsTestRequest(BaseModel):
    fb_page_id: Optional[str] = None
    fb_page_access_token: Optional[str] = None
    ig_business_account_id: Optional[str] = None

# --- AUTH ROUTES ---

@app.post("/api/auth/login")
def api_login(req: LoginRequest, request: Request):
    settings = get_settings()
    has_any_pass = (
        settings.get("admin_password") or settings.get("admin_password_hash") or
        settings.get("staff_password") or settings.get("staff_password_hash") or
        settings.get("app_password") or settings.get("app_password_hash")
    )
    if not has_any_pass:
        raise HTTPException(status_code=503, detail="Chưa cấu hình mật khẩu. Hãy đặt ADMIN_PASSWORD hoặc APP_PASSWORD trong .env rồi khởi động lại.")
    
    role = verify_user_role(req.password, settings)
    if not role:
        raise HTTPException(status_code=401, detail="Mật khẩu nội bộ không chính xác!")
        
    token = create_session_token(role=role)
    response = JSONResponse({"success": True, "message": "Đăng nhập thành công", "role": role})
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie("session_token", token, max_age=7 * 86400, httponly=True, samesite="lax", secure=is_https)
    return response

@app.get("/api/auth/check")
def api_auth_check(auth: dict = Depends(verify_auth)):
    return {"authenticated": True, "role": auth.get("role", "staff")}

@app.post("/api/auth/logout")
def api_logout(authorization: Optional[str] = Header(None), request: Request = None):
    token = request.cookies.get("session_token") if request else None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if token:
        delete_session(token)
    response = JSONResponse({"success": True, "message": "Đã đăng xuất"})
    response.delete_cookie("session_token")
    return response

# --- GOOGLE BUSINESS ROUTES ---

@app.get("/api/google/auth-url", dependencies=[Depends(verify_auth)])
def api_google_auth_url(request: Request):
    settings = get_settings()
    client_id = settings.get("google_client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Vui lòng nhập Google Client ID trong Cài đặt trước.")
    
    redirect_uri = "http://localhost:8000/api/google/callback"
    state = secrets.token_urlsafe(32)
    save_oauth_state(state, (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat())
    url = get_google_auth_url(client_id, redirect_uri, state)
    return {"auth_url": url}

@app.get("/api/google/callback")
def api_google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return RedirectResponse(url=f"/?google_error={error}")
    if not code:
        return RedirectResponse(url="/?google_error=missing_code")
    if not state or not consume_oauth_state(state):
        return RedirectResponse(url="/?google_error=invalid_state")

    settings = get_settings()
    client_id = settings.get("google_client_id")
    client_secret = settings.get("google_client_secret")
    redirect_uri = "http://localhost:8000/api/google/callback"

    try:
        exchange_google_code(code, client_id, client_secret, redirect_uri)
        return RedirectResponse(url="/?google_connected=1")
    except Exception:
        return RedirectResponse(url="/?google_error=connection_failed")

@app.get("/api/google/locations", dependencies=[Depends(verify_auth)])
def api_google_locations():
    try:
        locs = get_google_locations()
        return {"locations": locs}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- AI ROUTES ---

@app.post("/api/ai/generate-caption", dependencies=[Depends(verify_auth)])
def api_generate_caption(req: AICaptionRequest):
    try:
        result = generate_social_captions(req.images, req.user_hint)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- BULK UPLOAD ROUTES ---

@app.get("/api/bulk/template", dependencies=[Depends(verify_auth)])
def api_bulk_template():
    stream = generate_bulk_excel_template()
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="sample_bulk_posts.xlsx"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@app.post("/api/bulk/preview", dependencies=[Depends(verify_auth)])
async def api_bulk_preview(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in [".xlsx", ".xls", ".csv"]:
        raise HTTPException(status_code=400, detail="Vui lòng tải lên file định dạng .xlsx, .xls hoặc .csv")
    content = await file.read()
    try:
        posts = parse_bulk_file(content, file.filename)
        return {"success": True, "posts": posts, "count": len(posts)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đọc file Excel/CSV: {str(e)}")

@app.post("/api/bulk/import", dependencies=[Depends(verify_auth)])
def api_bulk_import(req: BulkImportRequest):
    if not req.posts:
        raise HTTPException(status_code=400, detail="Danh sách bài viết trống.")
    result = import_bulk_posts(req.posts)
    return result

# --- STORY ROUTES ---

@app.post("/api/story/preview-generate", dependencies=[Depends(verify_auth)])
def api_story_preview_generate(req: StoryPreviewRequest):
    try:
        story_filename = create_story_image(
            req.image_name,
            caption_hint=req.hook or req.caption,
            template=req.template or "organic",
            story_link=req.link or "https://roots.vn"
        )
        return {"success": True, "story_image": story_filename, "url": f"/api/media/{story_filename}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- POSTS ROUTES ---

def _safe_media_name(filename: str) -> str:
    if not filename or Path(filename).name != filename or not all(c.isalnum() or c in "._-" for c in filename):
        raise HTTPException(status_code=404, detail="Không tìm thấy file media.")
    return filename

def _validate_media_references(images: List[str]):
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Mỗi bài đăng tối đa 10 ảnh.")
    for image in images:
        if image.startswith(("http://", "https://")):
            parsed = urlparse(image)
            if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
                raise HTTPException(status_code=400, detail="URL ảnh phải là HTTPS công khai hợp lệ.")
        else:
            name = _safe_media_name(image)
            if not (UPLOAD_DIR / name).is_file():
                raise HTTPException(status_code=400, detail=f"Không tìm thấy ảnh: {name}")

# ─────────────────────────────────────────────────────────────
# MEDIA LIBRARY (MIXPOST PATTERN)
# ─────────────────────────────────────────────────────────────
@app.get("/api/media/library", dependencies=[Depends(verify_auth)])
def api_get_media_library(search: Optional[str] = None, tag: Optional[str] = None, limit: int = 50, offset: int = 0):
    items = get_media_items(search=search or "", tag=tag or "", limit=limit, offset=offset)
    return {"success": True, "media": items}

@app.get("/api/media/thumbnail/{filename}")
def api_get_media_thumbnail(filename: str):
    safe_name = _safe_media_name(filename)
    thumb_path = THUMB_DIR / f"thumb_{safe_name}"
    if thumb_path.is_file():
        return FileResponse(thumb_path)
    orig_path = UPLOAD_DIR / safe_name
    if orig_path.is_file():
        return FileResponse(orig_path)
    raise HTTPException(status_code=404, detail="Không tìm thấy thumbnail.")

class MediaTagUpdateRequest(BaseModel):
    filename: str
    tags: List[str]

@app.post("/api/media/tags", dependencies=[Depends(verify_auth)])
def api_update_media_tags(req: MediaTagUpdateRequest):
    update_media_tags(req.filename, req.tags)
    return {"success": True, "message": "Đã cập nhật tag ảnh"}

class MediaBatchDeleteRequest(BaseModel):
    filenames: List[str]

@app.post("/api/media/batch-delete", dependencies=[Depends(verify_auth)])
def api_batch_delete_media(req: MediaBatchDeleteRequest):
    deleted_count = 0
    for filename in req.filenames:
        try:
            safe_name = _safe_media_name(filename)
            delete_media_item(safe_name)
            p = UPLOAD_DIR / safe_name
            if p.is_file():
                p.unlink()
            thumb = THUMB_DIR / f"thumb_{safe_name}"
            if thumb.is_file():
                thumb.unlink()
            deleted_count += 1
        except Exception:
            pass
    return {"success": True, "deleted_count": deleted_count}

@app.delete("/api/media/{filename}", dependencies=[Depends(verify_auth)])
def api_delete_media(filename: str):
    safe_name = _safe_media_name(filename)
    delete_media_item(safe_name)
    p = UPLOAD_DIR / safe_name
    if p.is_file():
        p.unlink()
    thumb = THUMB_DIR / f"thumb_{safe_name}"
    if thumb.is_file():
        thumb.unlink()
    return {"success": True, "message": "Đã xóa ảnh thành công"}

@app.get("/api/media/{filename}")
def get_media(filename: str):
    path = UPLOAD_DIR / _safe_media_name(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file media.")
    return FileResponse(path)

@app.post("/api/upload", dependencies=[Depends(verify_auth)])
@app.post("/api/media/upload", dependencies=[Depends(verify_auth)])
async def upload_images(files: List[UploadFile] = File(...)):
    settings = get_settings()
    per_file_limit = settings["max_upload_mb"] * 1024 * 1024
    batch_limit = settings["max_upload_batch_mb"] * 1024 * 1024
    saved_files = []
    batch_size = 0
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail=f"{file.filename}: chỉ hỗ trợ JPG, PNG hoặc WEBP.")
        content = await file.read()
        if not content or len(content) > per_file_limit:
            raise HTTPException(status_code=400, detail=f"{file.filename}: file trống hoặc vượt quá {settings['max_upload_mb']} MB.")
        batch_size += len(content)
        if batch_size > batch_limit:
            raise HTTPException(status_code=400, detail=f"Tổng dung lượng ảnh vượt quá {settings['max_upload_batch_mb']} MB.")
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(status_code=400, detail=f"{file.filename}: nội dung không phải ảnh hợp lệ.")
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = UPLOAD_DIR / unique_name
        with open(dest_path, "wb") as buffer:
            buffer.write(content)
        try:
            from app.media_service import register_media_file
            register_media_file(unique_name, original_name=file.filename)
        except Exception:
            pass
        saved_files.append({
            "filename": unique_name,
            "url": f"/api/media/{unique_name}"
        })
    return {
        "success": True,
        "filenames": [f["filename"] for f in saved_files],
        "uploaded": saved_files
    }

@app.post("/api/posts")
@app.post("/api/posts/create")
def api_create_post(req: PostCreateRequest, auth: dict = Depends(verify_auth)):
    if not req.fb_caption and not req.ig_caption and not req.google_caption and not req.story_hook and not req.story_image:
        raise HTTPException(status_code=400, detail="Vui lòng nhập ít nhất một nội dung đăng bài hoặc chọn ảnh Story.")
    if req.action == "schedule" and not req.scheduled_time:
        raise HTTPException(status_code=400, detail="Vui lòng chọn thời gian lên lịch.")

    if req.target_ig and not req.images:
        raise HTTPException(status_code=400, detail="Instagram yêu cầu ít nhất một ảnh.")
    if req.target_story and not req.images and not req.story_image:
        raise HTTPException(status_code=400, detail="Story yêu cầu ít nhất một ảnh hoặc ảnh Story đã tạo.")
    if req.action not in {"now", "schedule"}:
        raise HTTPException(status_code=400, detail="Hành động đăng không hợp lệ.")
    _validate_media_references(req.images)
    if req.story_image:
        _safe_media_name(req.story_image)
        
    is_staff = (auth.get("role") == "staff")
    try:
        scheduled_time = normalize_schedule(req.scheduled_time) if (req.action == "schedule" and req.scheduled_time) else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    if is_staff:
        # Staff posts ALWAYS go to pending approval queue first
        initial_status = "pending_approval"
    else:
        initial_status = "scheduled" if req.action == "schedule" else "draft"

    post_id = create_post(
        fb_caption=req.fb_caption,
        ig_caption=req.ig_caption,
        google_caption=req.google_caption,
        images=req.images,
        target_fb=req.target_fb,
        target_ig=req.target_ig,
        target_story=req.target_story,
        target_google=req.target_google,
        google_action_type=req.google_action_type,
        google_action_url=req.google_action_url,
        story_image=req.story_image,
        story_template=req.story_template,
        story_hook=req.story_hook,
        story_link=req.story_link,
        status=initial_status,
        scheduled_time=scheduled_time
    )

    if is_staff:
        post_data = get_post_by_id(post_id)
        return {
            "post": post_data, 
            "status": "pending_approval", 
            "message": "Bài viết đã được gửi vào Hàng đợi chờ Admin phê duyệt trước khi đăng!"
        }

    if req.action == "now":
        result = publish_single_post(post_id)
        post_data = get_post_by_id(post_id)
        return {"post": post_data, "result": result}
    else:
        post_data = get_post_by_id(post_id)
        return {"post": post_data, "message": "Đã lên lịch thành công"}

@app.get("/api/posts", dependencies=[Depends(verify_auth)])
def api_get_posts(filter_type: Optional[str] = None):
    all_posts = get_posts(limit=200)
    if filter_type == "scheduled":
        filtered = [p for p in all_posts if p["status"] == "scheduled"]
    elif filter_type == "pending":
        filtered = [p for p in all_posts if p["status"] == "pending_approval"]
    elif filter_type == "history":
        filtered = [p for p in all_posts if p["status"] in ["success", "partial_failed", "failed", "publishing", "rejected"]]
    else:
        filtered = all_posts
    return {"posts": filtered}

@app.get("/api/posts/{post_id}", dependencies=[Depends(verify_auth)])
def api_get_post(post_id: int):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    return {"post": post}

class PostApproveRequest(BaseModel):
    action: Optional[str] = "publish_now"  # "publish_now" or "keep_schedule"

@app.post("/api/posts/{post_id}/approve", dependencies=[Depends(verify_admin_auth)])
def api_approve_post(post_id: int, req: PostApproveRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    if req.action == "publish_now":
        approve_post(post_id, action="publish_now")
        result = publish_single_post(post_id)
        updated = get_post_by_id(post_id)
        return {"success": True, "post": updated, "result": result, "message": "Đã phê duyệt và xuất bản bài viết thành công!"}
    else:
        approve_post(post_id, action="keep_schedule")
        updated = get_post_by_id(post_id)
        return {"success": True, "post": updated, "message": "Đã phê duyệt và đưa vào Lịch đăng tự động!"}

class PostRejectRequest(BaseModel):
    reason: Optional[str] = ""

@app.post("/api/posts/{post_id}/reject", dependencies=[Depends(verify_admin_auth)])
def api_reject_post(post_id: int, req: PostRejectRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    reject_post(post_id, reason=req.reason or "Bị từ chối bởi Admin")
    updated = get_post_by_id(post_id)
    return {"success": True, "post": updated, "message": "Đã từ chối bài viết."}

@app.post("/api/posts/{post_id}/publish-now", dependencies=[Depends(verify_auth)])
def api_publish_now(post_id: int, auth: dict = Depends(verify_auth)):
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Quản trị viên mới có quyền xuất bản bài trực tiếp.")
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    result = publish_single_post(post_id)
    updated = get_post_by_id(post_id)
    return {"post": updated, "result": result}

@app.delete("/api/posts/{post_id}", dependencies=[Depends(verify_auth)])
def api_delete_post(post_id: int):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    delete_post(post_id)
    return {"success": True, "message": "Đã xóa bài viết"}

@app.post("/api/maintenance/run", dependencies=[Depends(verify_admin_auth)])
def api_run_maintenance():
    backup = backup_database()
    deleted_media = cleanup_orphaned_media()
    return {"success": True, "backup": backup.name, "deleted_orphaned_media": deleted_media}

@app.get("/api/settings", dependencies=[Depends(verify_admin_auth)])
def api_get_settings():
    s = get_settings()
    token = s.get("fb_page_access_token", "")
    masked_token = f"{token[:8]}...{token[-6:]}" if len(token) > 14 else token
    return {
        "fb_page_id": s.get("fb_page_id"),
        "masked_token": masked_token,
        "ig_business_account_id": s.get("ig_business_account_id"),
        "has_imgbb_api_key": bool(s.get("imgbb_api_key")),
        "has_gemini_api_key": bool(s.get("gemini_api_key")),
        "gemini_model": s.get("gemini_model", "gemini-3.5-flash-lite"),
        "google_client_id": s.get("google_client_id", ""),
        "has_google_client_secret": bool(s.get("google_client_secret")),
        "google_connected": bool(s.get("google_refresh_token")),
        "google_location_name": s.get("google_location_name", ""),
        "google_location_id": s.get("google_location_id", ""),
        "host": s.get("host"),
        "port": s.get("port"),
        "has_password": bool(s.get("app_password") or s.get("app_password_hash") or s.get("admin_password")),
        "has_admin_password": bool(s.get("admin_password") or s.get("admin_password_hash") or s.get("app_password") or s.get("app_password_hash")),
        "has_staff_password": bool(s.get("staff_password") or s.get("staff_password_hash")),
        "max_upload_mb": s.get("max_upload_mb"),
        "max_upload_batch_mb": s.get("max_upload_batch_mb"),
        "media_retention_days": s.get("media_retention_days"),
    }

@app.post("/api/settings", dependencies=[Depends(verify_admin_auth)])
def api_save_settings(req: SettingsUpdateRequest):
    updates = req.model_dump(exclude_unset=True)
    secret_fields = ["app_password", "admin_password", "staff_password", "fb_page_access_token", "imgbb_api_key", "gemini_api_key", "google_client_secret"]
    for field in secret_fields:
        val = updates.get(field)
        if val is None or not str(val).strip() or "..." in str(val) or "•" in str(val):
            updates.pop(field, None)
    if "admin_password" in updates and len(updates["admin_password"]) < 4:
        raise HTTPException(status_code=400, detail="Mật khẩu Admin mới cần ít nhất 4 ký tự.")
    if "staff_password" in updates and len(updates["staff_password"]) < 4:
        raise HTTPException(status_code=400, detail="Mật khẩu Nhân viên mới cần ít nhất 4 ký tự.")
    if "app_password" in updates and len(updates["app_password"]) < 4:
        raise HTTPException(status_code=400, detail="Mật khẩu mới cần ít nhất 4 ký tự.")
    new_settings = update_settings(updates)
    return {"success": True, "settings": {k: v for k, v in new_settings.items() if not k.endswith("_password")}}

class ExchangeTokenRequest(BaseModel):
    short_token: str
    app_id: str
    app_secret: str
    page_id: Optional[str] = None

@app.post("/api/meta/exchange-permanent-token", dependencies=[Depends(verify_admin_auth)])
def api_exchange_permanent_token(req: ExchangeTokenRequest):
    try:
        res = exchange_for_permanent_page_token(
            short_token=req.short_token,
            app_id=req.app_id,
            app_secret=req.app_secret,
            page_id=req.page_id
        )
        updates = {
            "fb_page_access_token": res["page_access_token"],
            "fb_page_id": res["page_id"]
        }
        if res.get("ig_business_account_id"):
            updates["ig_business_account_id"] = res["ig_business_account_id"]
        update_settings(updates)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/settings/test", dependencies=[Depends(verify_auth)])
@app.get("/api/meta/status", dependencies=[Depends(verify_auth)])
def api_test_settings(req: Optional[SettingsTestRequest] = None):
    settings = get_settings()
    page_id = (req.fb_page_id if req else None) or settings.get("fb_page_id")
    page_token = (req.fb_page_access_token if req else None)
    if not page_token or "..." in page_token:
        page_token = settings.get("fb_page_access_token")
    ig_account_id = (req.ig_business_account_id if req else None) or settings.get("ig_business_account_id")
    
    test_result = test_meta_connection(page_id, page_token, ig_account_id)
    return test_result

# ─────────────────────────────────────────────────────────────
# ROOTS.VN PRODUCT CATALOG & QUICK GENERATE
# ─────────────────────────────────────────────────────────────
@app.get("/api/roots/categories", dependencies=[Depends(verify_auth)])
def api_get_roots_categories():
    return {"categories": fetch_roots_categories()}

@app.get("/api/roots/products", dependencies=[Depends(verify_auth)])
def api_get_roots_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 30
):
    return fetch_roots_products(search=search or "", category=category or "", page=page, page_size=page_size)

@app.get("/api/roots/flash-sale", dependencies=[Depends(verify_auth)])
def api_get_roots_flash_sale(page: int = 1, page_size: int = 30):
    return fetch_roots_flash_sale(page=page, page_size=page_size)

class RootsQuickGenerateRequest(BaseModel):
    product: dict
    aspect_ratio: Optional[str] = "4:5"

@app.post("/api/roots/quick-generate", dependencies=[Depends(verify_auth)])
async def api_roots_quick_generate(req: RootsQuickGenerateRequest):
    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, quick_generate_post_from_product, req.product, req.aspect_ratio or "4:5")
        return {"success": True, "data": data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo bài tự động: {str(e)}")

class RootsComboGenerateRequest(BaseModel):
    products: List[dict]
    user_hint: Optional[str] = ""
    campaign_angle: Optional[str] = ""

@app.post("/api/roots/combo-generate", dependencies=[Depends(verify_auth)])
@app.post("/api/roots/combo-campaign", dependencies=[Depends(verify_auth)])
async def api_roots_combo_generate(req: RootsComboGenerateRequest):
    if not req.products or len(req.products) == 0:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 1 sản phẩm để tạo combo.")
    loop = asyncio.get_running_loop()
    try:
        hint = req.campaign_angle or req.user_hint or ""
        data = await loop.run_in_executor(None, generate_combo_campaign_and_prompts, req.products, hint)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo chiến dịch combo: {str(e)}")

@app.get("/api/roots/download-product-image")
def api_download_roots_product_image(img: str, name: Optional[str] = "product"):
    import unicodedata
    safe_img = img.split("?")[0].strip()
    if not safe_img:
        raise HTTPException(status_code=400, detail="Thiếu tên ảnh.")
    roots_url = safe_img if safe_img.startswith(("http://", "https://")) else f"https://img.roots.vn/products/{safe_img}"
    try:
        res = requests.get(roots_url, timeout=20)
        if res.status_code == 200:
            # Strip Vietnamese accents to ensure 100% valid ASCII HTTP header
            raw_name = str(name or "product").replace("Đ", "D").replace("đ", "d")
            nfkd = unicodedata.normalize("NFKD", raw_name)
            ascii_name = "".join([c for c in nfkd if not unicodedata.combining(c)])
            clean_ascii = "".join([c if (c.isalnum() or c in "._- ") else "_" for c in ascii_name]).strip()
            while "__" in clean_ascii:
                clean_ascii = clean_ascii.replace("__", "_")
            clean_ascii = clean_ascii[:60].strip(" _") or "product"

            ext = ".webp"
            if ".jpg" in safe_img.lower() or ".jpeg" in safe_img.lower():
                ext = ".jpg"
            elif ".png" in safe_img.lower():
                ext = ".png"
            filename = f"{clean_ascii}{ext}" if not clean_ascii.lower().endswith(ext) else clean_ascii
            
            return StreamingResponse(
                io.BytesIO(res.content),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải ảnh: {str(e)}")
    raise HTTPException(status_code=404, detail="Không thể tải ảnh sản phẩm từ roots.vn")

# ─────────────────────────────────────────────────────────────
# BACKGROUND JOB MANAGEMENT (DRAMATIQ / ASYNC WORKER PATTERN)
# ─────────────────────────────────────────────────────────────
@app.post("/api/roots/start-quick-generate", dependencies=[Depends(verify_auth)])
async def api_roots_start_quick_generate(req: RootsQuickGenerateRequest):
    """
    Creates an asynchronous background job and immediately returns job_id (< 50ms).
    Frontend polls /api/jobs/{job_id} for live progress 0-100%.
    """
    if not isinstance(req.product, dict):
        raise HTTPException(status_code=400, detail="Dữ liệu sản phẩm không hợp lệ.")
    
    prod_name = req.product.get("TenSanPham", "Sản phẩm")
    ratio = req.aspect_ratio or "4:5"
    job_id = job_manager.create_job(job_type="1click_studio", metadata={"product_name": prod_name, "aspect_ratio": ratio})
    asyncio.create_task(run_1click_studio_job(job_id, req.product, ratio))
    return {"success": True, "job_id": job_id, "message": "Đã khởi tạo tác vụ nền thành công"}

@app.get("/api/jobs/{job_id}", dependencies=[Depends(verify_auth)])
def api_get_job_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job or job.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ.")
    return job

@app.post("/api/jobs/{job_id}/cancel", dependencies=[Depends(verify_auth)])
def api_cancel_job(job_id: str):
    job_manager.cancel_job(job_id)
    return {"success": True, "message": "Đã gửi yêu cầu hủy tác vụ"}

# ─────────────────────────────────────────────────────────────
# MEDIA LIBRARY DELETE (MIXPOST PATTERN)
# ─────────────────────────────────────────────────────────────

@app.delete("/api/media/{filename}", dependencies=[Depends(verify_auth)])
def api_delete_media_file(filename: str):
    delete_media_item(filename)
    orig_path = UPLOAD_DIR / filename
    if orig_path.is_file():
        orig_path.unlink(missing_ok=True)
    thumb_path = THUMB_DIR / f"thumb_{filename}"
    if thumb_path.is_file():
        thumb_path.unlink(missing_ok=True)
    return {"success": True, "message": "Đã xóa ảnh khỏi thư viện"}

# ─────────────────────────────────────────────────────────────
# HASHTAG GROUPS & CAPTION TEMPLATES (MIXPOST PATTERN)
# ─────────────────────────────────────────────────────────────
@app.get("/api/hashtag-groups", dependencies=[Depends(verify_auth)])
def api_get_hashtag_groups():
    return {"success": True, "groups": get_hashtag_groups()}

class CreateHashtagGroupRequest(BaseModel):
    name: str
    hashtags: str
    category: str = "Chung"

@app.post("/api/hashtag-groups", dependencies=[Depends(verify_auth)])
def api_create_hashtag_group(req: CreateHashtagGroupRequest):
    gid = create_hashtag_group(req.name, req.hashtags, req.category)
    return {"success": True, "id": gid, "message": "Đã tạo nhóm hashtag mới"}

@app.delete("/api/hashtag-groups/{group_id}", dependencies=[Depends(verify_auth)])
def api_delete_hashtag_group(group_id: int):
    delete_hashtag_group(group_id)
    return {"success": True, "message": "Đã xóa nhóm hashtag"}

@app.get("/api/caption-templates", dependencies=[Depends(verify_auth)])
def api_get_caption_templates():
    return {"success": True, "templates": get_caption_templates()}

class CreateCaptionTemplateRequest(BaseModel):
    name: str
    content: str
    category: str = "Sản phẩm"
    brand_voice: str = "Bán hàng"

@app.post("/api/caption-templates", dependencies=[Depends(verify_auth)])
def api_create_caption_template(req: CreateCaptionTemplateRequest):
    tid = create_caption_template(req.name, req.content, req.category, req.brand_voice)
    return {"success": True, "id": tid, "message": "Đã lưu mẫu nội dung mới"}

@app.delete("/api/caption-templates/{template_id}", dependencies=[Depends(verify_auth)])
def api_delete_caption_template(template_id: int):
    delete_caption_template(template_id)
    return {"success": True, "message": "Đã xóa mẫu nội dung"}

@app.get("/api/variables", dependencies=[Depends(verify_auth)])
def api_get_variables():
    return {"success": True, "variables": DEFAULT_VARIABLES}

class ResolveTemplateRequest(BaseModel):
    template: str
    context: dict

@app.post("/api/caption-templates/resolve", dependencies=[Depends(verify_auth)])
def api_resolve_caption_template(req: ResolveTemplateRequest):
    resolved = resolve_caption_variables(req.template, req.context)
    return {"success": True, "resolved_content": resolved}

# ─────────────────────────────────────────────────────────────
# CONTENT CALENDAR & DUPLICATE (MIXPOST PATTERN)
# ─────────────────────────────────────────────────────────────
@app.get("/api/calendar/events", dependencies=[Depends(verify_auth)])
def api_get_calendar_events():
    posts = get_posts()
    events = []
    for p in posts:
        target_time = p.get("scheduled_time") or p.get("published_at") or p.get("created_at")
        events.append({
            "id": p["id"],
            "title": p.get("title") or (p.get("fb_caption") or p.get("ig_caption") or "Bài viết")[:45],
            "fb_caption": p.get("fb_caption", ""),
            "ig_caption": p.get("ig_caption", ""),
            "google_caption": p.get("google_caption", ""),
            "images": p.get("images", []),
            "target_fb": bool(p.get("target_fb")),
            "target_ig": bool(p.get("target_ig")),
            "target_story": bool(p.get("target_story")),
            "target_google": bool(p.get("target_google")),
            "status": p.get("status"),
            "time": target_time,
            "story_image": p.get("story_image")
        })
    return {"success": True, "events": events}

class DuplicatePostRequest(BaseModel):
    new_scheduled_time: Optional[str] = None

@app.post("/api/posts/{post_id}/duplicate", dependencies=[Depends(verify_auth)])
def api_duplicate_post(post_id: int, req: DuplicatePostRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết để nhân bản.")
    
    new_id = create_post(
        fb_caption=post.get("fb_caption", ""),
        ig_caption=post.get("ig_caption", ""),
        google_caption=post.get("google_caption", ""),
        images=post.get("images", []),
        target_fb=bool(post.get("target_fb")),
        target_ig=bool(post.get("target_ig")),
        target_story=bool(post.get("target_story")),
        target_google=bool(post.get("target_google")),
        google_action_type=post.get("google_action_type", "LEARN_MORE"),
        google_action_url=post.get("google_action_url"),
        story_image=post.get("story_image"),
        story_template=post.get("story_template", "organic"),
        story_hook=post.get("story_hook", ""),
        story_link=post.get("story_link", ""),
        scheduled_time=req.new_scheduled_time or post.get("scheduled_time"),
        status="scheduled" if (req.new_scheduled_time or post.get("scheduled_time")) else "draft"
    )
    return {"success": True, "new_post_id": new_id, "message": "Đã nhân bản bài viết thành công"}
