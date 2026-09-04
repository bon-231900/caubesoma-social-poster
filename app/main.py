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
from app.threads_service import (get_threads_auth_url, exchange_threads_code,
                                 exchange_for_long_lived_threads_token, get_threads_profile)
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

app = FastAPI(title="ROOTS Social Poster", lifespan=lifespan)
logger = logging.getLogger(__name__)

# Models
class LoginRequest(BaseModel):
    password: str

class PostCreateRequest(BaseModel):
    title: Optional[str] = ""
    target_fb: bool = True
    target_ig: bool = True
    target_story: bool = False
    target_google: bool = False
    target_threads: bool = False
    fb_caption: Optional[str] = ""
    ig_caption: Optional[str] = ""
    story_hook: Optional[str] = ""
    story_template: Optional[str] = "glassmorphism"
    story_link: Optional[str] = ""
    story_image: Optional[str] = None
    google_caption: Optional[str] = ""
    google_action_type: Optional[str] = "LEARN_MORE"
    google_action_url: Optional[str] = ""
    threads_caption: Optional[str] = ""
    images: List[str] = []
    scheduled_at: Optional[str] = None
    status: Optional[str] = "draft"

class PostUpdateRequest(BaseModel):
    title: Optional[str] = None
    target_fb: Optional[bool] = None
    target_ig: Optional[bool] = None
    target_story: Optional[bool] = None
    target_google: Optional[bool] = None
    target_threads: Optional[bool] = None
    fb_caption: Optional[str] = None
    ig_caption: Optional[str] = None
    story_hook: Optional[str] = None
    story_template: Optional[str] = None
    story_link: Optional[str] = None
    story_image: Optional[str] = None
    google_caption: Optional[str] = None
    google_action_type: Optional[str] = None
    google_action_url: Optional[str] = None
    threads_caption: Optional[str] = None
    images: Optional[List[str]] = None
    scheduled_at: Optional[str] = None
    status: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    fb_page_id: Optional[str] = None
    fb_page_access_token: Optional[str] = None
    ig_business_account_id: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    imgbb_api_key: Optional[str] = None
    google_account_id: Optional[str] = None
    google_location_id: Optional[str] = None
    google_refresh_token: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    threads_user_id: Optional[str] = None
    threads_username: Optional[str] = None
    threads_access_token: Optional[str] = None
    threads_app_id: Optional[str] = None
    threads_app_secret: Optional[str] = None
    admin_password: Optional[str] = None

class AICaptionRequest(BaseModel):
    images: List[str]
    user_hint: Optional[str] = ""

class AIComboCampaignRequest(BaseModel):
    products: List[dict]
    user_hint: Optional[str] = ""

class QuickPostRequest(BaseModel):
    product: dict
    custom_hint: Optional[str] = ""
    auto_schedule: bool = False
    schedule_delay_hours: Optional[int] = 2

class PermanentTokenExchangeRequest(BaseModel):
    user_access_token: str

class RejectRequest(BaseModel):
    reason: Optional[str] = "Nội dung cần chỉnh sửa thêm"

class TemplateApplyRequest(BaseModel):
    template_content: str
    custom_variables: Optional[dict] = {}

class MediaTagUpdateRequest(BaseModel):
    tags: str

class HashtagGroupCreateRequest(BaseModel):
    name: str
    tags: str

class CaptionTemplateCreateRequest(BaseModel):
    name: str
    content: str

# Auth Endpoints
@app.post("/api/auth/login")
def login(req: LoginRequest):
    auth_result = verify_password(req.password)
    if not auth_result.get("authenticated"):
        raise HTTPException(status_code=401, detail="Sai mật khẩu truy cập.")
    role = auth_result.get("role", "admin")
    token = create_session_token(role=role)
    response = JSONResponse({
        "success": True, 
        "token": token, 
        "role": role,
        "is_default_admin": auth_result.get("is_default", False)
    })
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400 * 7, samesite="lax")
    return response

@app.post("/api/auth/logout")
def logout(auth: dict = Depends(verify_auth)):
    delete_session(auth["token"])
    response = JSONResponse({"success": True})
    response.delete_cookie(key="session_token")
    return response

@app.get("/api/auth/me")
def get_current_user(auth: dict = Depends(verify_auth)):
    settings = get_settings()
    is_default_admin = (auth.get("role") == "admin" and not settings.get("admin_password"))
    return {
        "authenticated": True, 
        "role": auth.get("role"),
        "is_default_admin": is_default_admin
    }

# Posts Endpoints
@app.get("/api/posts")
def list_posts(status: Optional[str] = None, limit: int = 50, offset: int = 0, auth: dict = Depends(verify_auth)):
    return get_posts(status=status, limit=limit, offset=offset)

@app.get("/api/posts/{post_id}")
def get_post(post_id: int, auth: dict = Depends(verify_auth)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    return post

@app.post("/api/posts")
def add_post(req: PostCreateRequest, auth: dict = Depends(verify_auth)):
    if not req.target_fb and not req.target_ig and not req.target_google and not req.target_threads:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một kênh đăng (Facebook, Instagram, Google Maps hoặc Threads).")
    
    # Non-admins submitting a post must go through approval workflow
    user_role = auth.get("role")
    post_status = req.status
    if user_role == "editor" and post_status in ["scheduled", "publishing"]:
        post_status = "pending_approval"
        
    scheduled_iso = None
    if req.scheduled_at:
        try:
            scheduled_iso = normalize_schedule(req.scheduled_at)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    post_id = create_post(
        title=req.title,
        target_fb=req.target_fb,
        target_ig=req.target_ig,
        target_story=req.target_story,
        target_google=req.target_google,
        target_threads=req.target_threads,
        fb_caption=req.fb_caption,
        ig_caption=req.ig_caption,
        story_hook=req.story_hook,
        story_template=req.story_template,
        story_link=req.story_link,
        story_image=req.story_image,
        google_caption=req.google_caption,
        google_action_type=req.google_action_type,
        google_action_url=req.google_action_url,
        threads_caption=req.threads_caption,
        images=req.images,
        scheduled_at=scheduled_iso,
        status=post_status
    )
    return {"id": post_id, "success": True, "status": post_status}

@app.put("/api/posts/{post_id}")
def edit_post(post_id: int, req: PostUpdateRequest, auth: dict = Depends(verify_auth)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
        
    update_data = {}
    for k, v in req.model_dump().items():
        if v is not None:
            if k == "scheduled_at" and v:
                try:
                    update_data[k] = normalize_schedule(v)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
            else:
                update_data[k] = v
                
    # If an editor changes status to scheduled, move to pending_approval instead
    if auth.get("role") == "editor" and update_data.get("status") in ["scheduled", "publishing"]:
        update_data["status"] = "pending_approval"

    update_post(post_id, **update_data)
    return {"success": True}

@app.delete("/api/posts/{post_id}")
def remove_post(post_id: int, auth: dict = Depends(verify_auth)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    delete_post(post_id)
    return {"success": True}

@app.post("/api/posts/{post_id}/publish")
def trigger_publish(post_id: int, auth: dict = Depends(verify_admin_auth)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    res = publish_single_post(post_id)
    return res

# Post Approval Workflow
@app.post("/api/posts/{post_id}/approve")
def approve_post_endpoint(post_id: int, auth: dict = Depends(verify_admin_auth)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    approve_post(post_id)
    return {"success": True, "status": "scheduled" if post.get("scheduled_at") else "draft"}

@app.post("/api/posts/{post_id}/reject")
def reject_post_endpoint(post_id: int, req: RejectRequest, auth: dict = Depends(verify_admin_auth)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    reject_post(post_id, reason=req.reason)
    return {"success": True, "status": "rejected"}

# Media Uploads & Assets
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...), auth: dict = Depends(verify_auth)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Định dạng ảnh không được hỗ trợ ({ext}). Chỉ hỗ trợ JPG, PNG, WEBP.")

    raw_data = await file.read()
    if len(raw_data) > MAX_IMAGE_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá giới hạn cho phép (tối đa 15MB).")

    # Sanitize and verify image integrity
    try:
        img = Image.open(io.BytesIO(raw_data))
        img.verify()
        
        # Re-open for format and dimension reading since verify() invalidates the object
        img = Image.open(io.BytesIO(raw_data))
        width, height = img.size
    except (UnidentifiedImageError, Exception):
        raise HTTPException(status_code=400, detail="File tải lên không phải là ảnh hợp lệ hoặc bị lỗi dữ liệu.")

    # Unique sanitized filename
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}{ext}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(raw_data)

    # Automatically create thumbnail and register in Media Library
    thumb_name = create_thumbnail(safe_name)
    media_id = register_media_file(
        filename=safe_name,
        original_name=file.filename,
        file_size=len(raw_data),
        width=width,
        height=height,
        thumb_filename=thumb_name
    )

    return {
        "filename": safe_name,
        "media_id": media_id,
        "original_name": file.filename,
        "size": len(raw_data),
        "width": width,
        "height": height,
        "thumb_url": f"/uploads/thumbs/{thumb_name}" if thumb_name else f"/uploads/{safe_name}",
        "url": f"/uploads/{safe_name}"
    }

# Media Library Management
@app.get("/api/media")
def list_media(tag: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0, auth: dict = Depends(verify_auth)):
    return get_media_items(tag=tag, search=search, limit=limit, offset=offset)

@app.put("/api/media/{media_id}/tags")
def update_tags(media_id: int, req: MediaTagUpdateRequest, auth: dict = Depends(verify_auth)):
    update_media_tags(media_id, req.tags)
    return {"success": True}

@app.delete("/api/media/{media_id}")
def remove_media(media_id: int, auth: dict = Depends(verify_admin_auth)):
    delete_media_item(media_id)
    return {"success": True}

# Hashtag Groups
@app.get("/api/hashtag-groups")
def list_hashtag_groups(auth: dict = Depends(verify_auth)):
    return get_hashtag_groups()

@app.post("/api/hashtag-groups")
def add_hashtag_group(req: HashtagGroupCreateRequest, auth: dict = Depends(verify_auth)):
    group_id = create_hashtag_group(req.name, req.tags)
    return {"id": group_id, "success": True}

@app.delete("/api/hashtag-groups/{group_id}")
def remove_hashtag_group(group_id: int, auth: dict = Depends(verify_auth)):
    delete_hashtag_group(group_id)
    return {"success": True}

# Caption Templates
@app.get("/api/caption-templates")
def list_caption_templates(auth: dict = Depends(verify_auth)):
    return get_caption_templates()

@app.post("/api/caption-templates")
def add_caption_template(req: CaptionTemplateCreateRequest, auth: dict = Depends(verify_auth)):
    tmpl_id = create_caption_template(req.name, req.content)
    return {"id": tmpl_id, "success": True}

@app.delete("/api/caption-templates/{template_id}")
def remove_caption_template(template_id: int, auth: dict = Depends(verify_auth)):
    delete_caption_template(template_id)
    return {"success": True}

@app.post("/api/caption-templates/preview")
def preview_caption_template(req: TemplateApplyRequest, auth: dict = Depends(verify_auth)):
    resolved = resolve_caption_variables(req.template_content, req.custom_variables)
    return {"resolved_content": resolved, "default_variables": DEFAULT_VARIABLES}

# AI Services
@app.post("/api/ai/captions")
def ai_captions(req: AICaptionRequest, auth: dict = Depends(verify_auth)):
    try:
        captions = generate_social_captions(req.images, req.user_hint)
        return captions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai/combo-campaign")
def ai_combo_campaign(req: AIComboCampaignRequest, auth: dict = Depends(verify_auth)):
    if not req.products:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một sản phẩm để tạo chiến dịch Combo.")
    try:
        res = generate_combo_campaign_and_prompts(req.products, req.user_hint)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Settings & Credentials
@app.get("/api/settings")
def read_settings(auth: dict = Depends(verify_auth)):
    settings = get_settings()
    is_admin = (auth.get("role") == "admin")
    
    # Mask sensitive API keys and tokens for privacy and security
    def mask_key(k: Optional[str]) -> str:
        if not k:
            return ""
        if len(k) <= 8:
            return "******"
        return f"{k[:4]}****{k[-4:]}"

    masked = {
        "fb_page_id": settings.get("fb_page_id", ""),
        "fb_page_access_token": mask_key(settings.get("fb_page_access_token")) if not is_admin else (settings.get("fb_page_access_token") or ""),
        "has_fb_token": bool(settings.get("fb_page_access_token")),
        "ig_business_account_id": settings.get("ig_business_account_id", ""),
        "gemini_api_key": mask_key(settings.get("gemini_api_key")) if not is_admin else (settings.get("gemini_api_key") or ""),
        "has_gemini_key": bool(settings.get("gemini_api_key")),
        "gemini_model": settings.get("gemini_model", "gemini-3.5-flash-lite"),
        "imgbb_api_key": mask_key(settings.get("imgbb_api_key")) if not is_admin else (settings.get("imgbb_api_key") or ""),
        "has_imgbb_key": bool(settings.get("imgbb_api_key")),
        "google_account_id": settings.get("google_account_id", ""),
        "google_location_id": settings.get("google_location_id", ""),
        "has_google_refresh_token": bool(settings.get("google_refresh_token")),
        "google_client_id": settings.get("google_client_id", ""),
        "has_google_client_secret": bool(settings.get("google_client_secret")),
        "threads_user_id": settings.get("threads_user_id", ""),
        "threads_username": settings.get("threads_username", ""),
        "has_threads_token": bool(settings.get("threads_access_token")),
        "threads_token_expiry": settings.get("threads_token_expiry", ""),
        "threads_app_id": settings.get("threads_app_id", ""),
        "has_threads_app_secret": bool(settings.get("threads_app_secret")),
        "is_admin": is_admin
    }
    return masked

@app.post("/api/settings")
def write_settings(req: SettingsUpdateRequest, auth: dict = Depends(verify_admin_auth)):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    update_settings(update_data)
    return {"success": True}

@app.post("/api/settings/test-meta")
def check_meta_connection(auth: dict = Depends(verify_admin_auth)):
    res = test_meta_connection()
    return res

@app.post("/api/settings/exchange-permanent-token")
def exchange_token_endpoint(req: PermanentTokenExchangeRequest, auth: dict = Depends(verify_admin_auth)):
    settings = get_settings()
    page_id = settings.get("fb_page_id")
    if not page_id:
        raise HTTPException(status_code=400, detail="Chưa cấu hình Facebook Page ID. Vui lòng điền Page ID trước.")
    try:
        perm_token = exchange_for_permanent_page_token(req.user_access_token, page_id)
        update_settings({"fb_page_access_token": perm_token})
        return {"success": True, "message": "Đã đổi thành công sang Access Token vĩnh viễn và lưu vào Cài đặt!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Google Business OAuth & Locations
@app.get("/api/google/auth-url")
def google_auth_url(request: Request, auth: dict = Depends(verify_admin_auth)):
    state = secrets.token_urlsafe(32)
    save_oauth_state(state)
    
    # Dynamically build redirect_uri based on server base URL
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/google/callback"
    
    try:
        url = get_google_auth_url(redirect_uri, state=state)
        return {"auth_url": url, "redirect_uri": redirect_uri}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/google/callback")
def google_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None, request: Request = None):
    if error:
        return RedirectResponse(url="/#settings?google_error=" + error)
    if not code or not state:
        return RedirectResponse(url="/#settings?google_error=missing_code_or_state")
        
    if not consume_oauth_state(state):
        return RedirectResponse(url="/#settings?google_error=invalid_or_expired_state")
        
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/google/callback"
    
    try:
        token_data = exchange_google_code(code, redirect_uri)
        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            update_settings({"google_refresh_token": refresh_token})
        return RedirectResponse(url="/#settings?google_success=connected")
    except Exception as e:
        logger.error(f"Google OAuth exchange error: {e}")
        return RedirectResponse(url=f"/#settings?google_error={str(e)}")

@app.get("/api/google/locations")
def list_google_locations(auth: dict = Depends(verify_admin_auth)):
    try:
        data = get_google_locations()
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Meta Threads OAuth & Status Endpoints
@app.get("/api/threads/status")
def threads_status(auth: dict = Depends(verify_auth)):
    settings = get_settings()
    user_id = settings.get("threads_user_id", "")
    username = settings.get("threads_username", "")
    token = settings.get("threads_access_token", "")
    expiry = settings.get("threads_token_expiry", "")
    connected = bool(token and user_id)
    return {
        "connected": connected,
        "user_id": user_id,
        "username": username,
        "token_expiry": expiry,
        "profile_url": f"https://www.threads.com/@{username}" if username else "https://www.threads.com/@roots.vn"
    }

@app.get("/api/threads/auth-url")
def threads_auth_url(request: Request, auth: dict = Depends(verify_admin_auth)):
    state = secrets.token_urlsafe(32)
    save_oauth_state(state)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/threads/callback"
    try:
        url = get_threads_auth_url(redirect_uri, state=state)
        return {"auth_url": url, "redirect_uri": redirect_uri}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/threads/callback")
def threads_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None, request: Request = None):
    if error:
        return RedirectResponse(url=f"/#settings?threads_error={error}")
    if not code or not state:
        return RedirectResponse(url="/#settings?threads_error=missing_code_or_state")
    if not consume_oauth_state(state):
        return RedirectResponse(url="/#settings?threads_error=invalid_or_expired_state")
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/threads/callback"
    try:
        short_token_data = exchange_threads_code(code, redirect_uri)
        short_token = short_token_data.get("access_token")
        user_id = str(short_token_data.get("user_id", ""))
        long_token_data = exchange_for_long_lived_threads_token(short_token)
        long_token = long_token_data.get("access_token")
        expires_in = long_token_data.get("expires_in", 5184000)
        from datetime import datetime, timedelta, timezone
        expiry_iso = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        profile = get_threads_profile(long_token)
        username = profile.get("username", "roots.vn")
        update_settings({
            "threads_user_id": user_id or str(profile.get("id", "")),
            "threads_username": username,
            "threads_access_token": long_token,
            "threads_token_expiry": expiry_iso
        })
        return RedirectResponse(url="/#settings?threads_success=connected")
    except Exception as e:
        logger.error(f"Threads OAuth exchange error: {e}")
        return RedirectResponse(url=f"/#settings?threads_error={str(e)}")

@app.post("/api/threads/test-connection")
def threads_test_connection(auth: dict = Depends(verify_admin_auth)):
    settings = get_settings()
    token = settings.get("threads_access_token")
    if not token:
        raise HTTPException(status_code=400, detail="Chưa có Threads Access Token. Vui lòng kết nối OAuth hoặc nhập Token.")
    try:
        profile = get_threads_profile(token)
        return {
            "success": True,
            "profile": profile,
            "message": f"Kết nối Threads thành công với tài khoản @{profile.get('username', 'roots.vn')}!"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi kiểm tra Threads API: {str(e)}")

# Story Visual Maker
class StoryMakerRequest(BaseModel):
    image_name: str
    caption_hint: Optional[str] = ""
    template: Optional[str] = "glassmorphism"
    story_link: Optional[str] = "https://roots.vn"

@app.post("/api/story/generate")
def generate_story(req: StoryMakerRequest, auth: dict = Depends(verify_auth)):
    try:
        story_file = create_story_image(
            image_name=req.image_name,
            caption_hint=req.caption_hint,
            template=req.template,
            story_link=req.story_link
        )
        return {"success": True, "story_image": story_file, "url": f"/uploads/{story_file}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Bulk Import & Export Endpoints
@app.get("/api/bulk/template")
def download_bulk_template(auth: dict = Depends(verify_auth)):
    stream = generate_bulk_excel_template()
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=roots_social_template.xlsx"}
    )

@app.post("/api/bulk/preview")
async def preview_bulk(file: UploadFile = File(...), auth: dict = Depends(verify_auth)):
    ext = Path(file.filename).suffix.lower()
    if ext not in [".xlsx", ".csv"]:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng .xlsx hoặc .csv.")
        
    content = await file.read()
    try:
        parsed_posts = parse_bulk_file(content, file.filename)
        return {"total": len(parsed_posts), "posts": parsed_posts}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class BulkImportRequest(BaseModel):
    posts: List[dict]

@app.post("/api/bulk/import")
def execute_bulk_import(req: BulkImportRequest, auth: dict = Depends(verify_auth)):
    if not req.posts:
        raise HTTPException(status_code=400, detail="Không có bài viết nào để nhập.")
        
    # Non-admins import as draft or pending_approval
    default_status = "draft" if auth.get("role") == "editor" else "draft"
    imported_ids = import_bulk_posts(req.posts, default_status=default_status)
    return {"success": True, "imported_count": len(imported_ids), "ids": imported_ids}

# ROOTS Catalog Integration
@app.get("/api/roots/categories")
def get_categories(auth: dict = Depends(verify_auth)):
    try:
        cats = fetch_roots_categories()
        return cats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/roots/products")
def get_products(category_slug: Optional[str] = None, search: Optional[str] = None, page: int = 1, limit: int = 24, auth: dict = Depends(verify_auth)):
    try:
        data = fetch_roots_products(category_slug=category_slug, search=search, page=page, limit=limit)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/roots/flash-sale")
def get_flash_sale(auth: dict = Depends(verify_auth)):
    try:
        data = fetch_roots_flash_sale()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/roots/quick-post")
def create_quick_post(req: QuickPostRequest, auth: dict = Depends(verify_auth)):
    try:
        post_data = quick_generate_post_from_product(
            product=req.product,
            custom_hint=req.custom_hint,
            auto_schedule=req.auto_schedule,
            schedule_delay_hours=req.schedule_delay_hours
        )
        post_id = create_post(**post_data)
        return {"success": True, "post_id": post_id, "post": post_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 1-Click Studio Background Jobs
class StudioJobCreateRequest(BaseModel):
    selected_products: List[dict]
    channel_selection: dict
    custom_hint: Optional[str] = ""
    auto_generate_prompts: bool = True

@app.post("/api/studio/start-job")
def start_studio_job(req: StudioJobCreateRequest, auth: dict = Depends(verify_auth)):
    if not req.selected_products:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một sản phẩm.")
    
    # Dispatch non-blocking background task
    job_id = job_manager.create_job()
    asyncio.create_task(run_1click_studio_job(
        job_id=job_id,
        selected_products=req.selected_products,
        channel_selection=req.channel_selection,
        custom_hint=req.custom_hint,
        auto_generate_prompts=req.auto_generate_prompts
    ))
    return {"job_id": job_id, "status": "running"}

@app.get("/api/studio/job-status/{job_id}")
def check_studio_job(job_id: str, auth: dict = Depends(verify_auth)):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy tiến trình làm việc.")
    return job

# Serve Static Uploads and UI
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ROOTS Social Poster Backend Running"}
