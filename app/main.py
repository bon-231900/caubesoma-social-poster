import os
import json
import secrets
import mimetypes
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, Depends, Header, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
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
    if not token and request and request.cookies.get("session_token"):
        token = request.cookies.get("session_token")
    if not token or not session_is_valid(token):
        raise HTTPException(status_code=401, detail="Chưa xác thực hoặc phiên đăng nhập đã hết hạn.")
    role = get_session_role(token)
    return {"token": token, "role": role}

def verify_admin_auth(auth: dict = Depends(verify_auth)) -> dict:
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Quản trị viên (Admin) mới có quyền truy cập cấu hình.")
    return auth

app = FastAPI(title="Auto Social Poster", version="10.5")
init_db()

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".html", ".js", ".css")) or path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.on_event("startup")
def startup_event():
    configure_logging()
    start_scheduler()

@app.on_event("shutdown")
def shutdown_event():
    shutdown_scheduler()

class LoginRequest(BaseModel):
    password: str

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
    google_location_id: Optional[str] = None
    google_location_name: Optional[str] = None

class TestSettingsRequest(BaseModel):
    fb_page_id: Optional[str] = None
    fb_page_access_token: Optional[str] = None
    ig_business_account_id: Optional[str] = None

class MetaExchangeRequest(BaseModel):
    user_access_token: str
    app_id: str
    app_secret: str
    target_page_id: Optional[str] = None

class PostCreateRequest(BaseModel):
    title: Optional[str] = ""
    fb_caption: Optional[str] = ""
    ig_caption: Optional[str] = ""
    google_caption: Optional[str] = ""
    images: Optional[List[str]] = []
    target_fb: Optional[bool] = True
    target_ig: Optional[bool] = True
    target_story: Optional[bool] = False
    target_google: Optional[bool] = False
    google_action_type: Optional[str] = "LEARN_MORE"
    google_action_url: Optional[str] = ""
    story_image: Optional[str] = None
    story_template: Optional[str] = "glassmorphism"
    story_hook: Optional[str] = ""
    story_link: Optional[str] = ""
    action: Optional[str] = "now"
    scheduled_time: Optional[str] = None

class GenerateCaptionsRequest(BaseModel):
    prompt: str
    brand_voice: Optional[str] = "Thân thiện"
    include_emojis: Optional[bool] = True
    generate_hashtags: Optional[bool] = True
    model_name: Optional[str] = None
    aspect_ratio: Optional[str] = "1:1"

class GenerateStoryRequest(BaseModel):
    image_filename: str
    template_name: Optional[str] = "glassmorphism"
    hook_text: Optional[str] = ""
    product_name: Optional[str] = ""
    price_tag: Optional[str] = ""
    badge_text: Optional[str] = ""
    call_to_action: Optional[str] = ""

class BulkImportRequest(BaseModel):
    posts: List[dict]

class HashtagGroupRequest(BaseModel):
    name: str
    hashtags: str
    category: Optional[str] = "Chung"

class CaptionTemplateRequest(BaseModel):
    name: str
    content: str
    category: Optional[str] = "Sản phẩm"
    brand_voice: Optional[str] = "Bán hàng"

class ApprovalActionRequest(BaseModel):
    action: Optional[str] = "publish_now"

class RejectionActionRequest(BaseModel):
    reason: Optional[str] = ""

@app.get("/api/auth/check")
def api_auth_check(request: Request):
    token = request.cookies.get("session_token")
    if token and session_is_valid(token):
        role = get_session_role(token)
        return {"authenticated": True, "role": role}
    return {"authenticated": False, "role": ""}

@app.post("/api/auth/login")
def api_login(req: LoginRequest, response: Response):
    settings = get_settings()
    role = verify_user_role(req.password, settings)
    if not role:
        raise HTTPException(status_code=401, detail="Mật khẩu không chính xác.")
    token = create_session_token(role=role)
    response.set_cookie("session_token", token, httponly=True, samesite="lax", max_age=604800)
    return {"success": True, "role": role, "token": token}

@app.post("/api/auth/logout")
def api_logout(response: Response, auth: dict = Depends(verify_auth)):
    delete_session(auth["token"])
    response.delete_cookie("session_token")
    return {"success": True}

@app.get("/api/settings", dependencies=[Depends(verify_admin_auth)])
def api_get_settings():
    s = get_settings()
    token = s.get("fb_page_access_token", "")
    masked_token = (token[:6] + "..." + token[-4:]) if len(token) > 10 else ("***" if token else "")
    secret = s.get("google_client_secret", "")
    masked_secret = (secret[:3] + "..." + secret[-3:]) if len(secret) > 6 else ("***" if secret else "")
    return {
        "fb_page_id": s.get("fb_page_id", ""),
        "fb_page_access_token": "",
        "masked_token": masked_token,
        "ig_business_account_id": s.get("ig_business_account_id", ""),
        "imgbb_api_key": s.get("imgbb_api_key", ""),
        "has_imgbb_api_key": bool(s.get("imgbb_api_key")),
        "has_gemini_api_key": bool(s.get("gemini_api_key")),
        "gemini_model": s.get("gemini_model", "gemini-flash-latest"),
        "google_client_id": s.get("google_client_id", ""),
        "has_google_client_secret": bool(secret),
        "masked_google_client_secret": masked_secret,
        "google_connected": bool(s.get("google_refresh_token")),
        "google_location_id": s.get("google_location_id", ""),
        "google_location_name": s.get("google_location_name", ""),
        "has_admin_password": bool(s.get("admin_password") or s.get("admin_password_hash") or s.get("app_password") or s.get("app_password_hash")),
        "has_staff_password": bool(s.get("staff_password") or s.get("staff_password_hash")),
        "app_password": ""
    }

@app.post("/api/settings", dependencies=[Depends(verify_admin_auth)])
def api_update_settings(req: SettingsUpdateRequest):
    updates = req.dict(exclude_unset=True)
    update_settings(updates)
    return {"success": True, "message": "Đã lưu cài đặt thành công."}

@app.post("/api/settings/test", dependencies=[Depends(verify_admin_auth)])
def api_test_settings(req: TestSettingsRequest):
    s = get_settings()
    page_id = req.fb_page_id or s.get("fb_page_id")
    token = req.fb_page_access_token or s.get("fb_page_access_token")
    ig_id = req.ig_business_account_id or s.get("ig_business_account_id")
    if not page_id or not token:
        raise HTTPException(status_code=400, detail="Thiếu Facebook Page ID hoặc Access Token.")
    result = test_meta_connection(page_id, token, ig_id)
    return result

@app.post("/api/meta/exchange-permanent-token", dependencies=[Depends(verify_admin_auth)])
def api_exchange_permanent_token(req: MetaExchangeRequest):
    res = exchange_for_permanent_page_token(
        req.user_access_token,
        req.app_id,
        req.app_secret,
        req.target_page_id
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Không thể lấy Permanent Token."))
    update_settings({
        "fb_page_access_token": res["page_access_token"],
        "fb_page_id": res["page_id"]
    })
    return res

@app.post("/api/media/upload", dependencies=[Depends(verify_auth)])
async def api_upload_media(files: List[UploadFile] = File(...)):
    saved_files = []
    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail=f"Định dạng file không được hỗ trợ: {ext}")
        unique_name = f"{secrets.token_hex(16)}{ext}"
        target_path = UPLOAD_DIR / unique_name
        content = await file.read()
        target_path.write_bytes(content)
        register_media_file(target_path, original_name=file.filename)
        saved_files.append(unique_name)
    return {"success": True, "files": saved_files, "uploaded": saved_files}

@app.post("/api/posts")
@app.post("/api/posts/create")
def api_create_post(req: PostCreateRequest, auth: dict = Depends(verify_auth)):
    if not req.fb_caption and not req.ig_caption and not req.google_caption and not req.story_hook:
        raise HTTPException(status_code=400, detail="Vui lòng nhập ít nhất một nội dung đăng bài.")
    if req.action == "schedule" and not req.scheduled_time:
        raise HTTPException(status_code=400, detail="Vui lòng chọn thời gian lên lịch.")

    if req.target_ig and not req.images:
        raise HTTPException(status_code=400, detail="Instagram yêu cầu ít nhất một ảnh.")
    if req.target_story and not req.images and not req.story_image:
        raise HTTPException(status_code=400, detail="Story yêu cầu ít nhất một ảnh hoặc ảnh Story đã tạo.")
    if req.action not in {"now", "schedule"}:
        raise HTTPException(status_code=400, detail="Hành động đăng không hợp lệ.")

    user_role = auth.get("role", "admin")
    if user_role == "staff":
        initial_status = "pending_approval"
    else:
        initial_status = "draft" if req.action == "now" else "scheduled"

    scheduled_time = None
    if req.action == "schedule" or req.scheduled_time:
        scheduled_time = normalize_schedule(req.scheduled_time) if req.scheduled_time else None

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
        status=initial_status,
        scheduled_time=scheduled_time,
        title=req.title,
        story_image=req.story_image,
        story_template=req.story_template,
        story_hook=req.story_hook,
        story_link=req.story_link
    )

    if user_role == "staff":
        return {
            "success": True,
            "status": "pending_approval",
            "message": "Bài viết đã được gửi vào hàng đợi chờ Quản trị viên (Admin) phê duyệt.",
            "post": get_post_by_id(post_id)
        }

    if req.action == "now":
        result = publish_single_post(post_id)
        return {
            "success": result["success"],
            "status": "published" if result["success"] else "failed",
            "post": get_post_by_id(post_id),
            "result": result
        }

    return {
        "success": True,
        "status": "scheduled",
        "post": get_post_by_id(post_id)
    }

@app.post("/api/posts/{post_id}/approve", dependencies=[Depends(verify_admin_auth)])
def api_approve_post(post_id: int, req: ApprovalActionRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    
    if req.action == "publish_now":
        approve_post(post_id, action="publish_now")
        result = publish_single_post(post_id)
        return {
            "success": result["success"],
            "message": "Đã duyệt và xuất bản bài viết thành công!" if result["success"] else "Duyệt thành công nhưng đăng thất bại.",
            "post": get_post_by_id(post_id),
            "result": result
        }
    else:
        approve_post(post_id, action="keep_schedule")
        return {
            "success": True,
            "message": "Đã duyệt bài viết vào lịch đăng tự động!",
            "post": get_post_by_id(post_id)
        }

@app.post("/api/posts/{post_id}/reject", dependencies=[Depends(verify_admin_auth)])
def api_reject_post(post_id: int, req: RejectionActionRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    reject_post(post_id, reason=req.reason)
    return {"success": True, "message": "Đã từ chối bài viết.", "post": get_post_by_id(post_id)}

@app.get("/api/posts", dependencies=[Depends(verify_auth)])
def api_get_posts(filter_type: Optional[str] = "all"):
    if filter_type == "scheduled":
        posts = get_posts(status="scheduled")
    elif filter_type == "pending":
        posts = get_posts(status="pending_approval")
    elif filter_type == "history":
        all_p = get_posts()
        posts = [p for p in all_p if p["status"] not in ["scheduled", "pending_approval"]]
    else:
        posts = get_posts()
    return {"posts": posts}

@app.delete("/api/posts/{post_id}", dependencies=[Depends(verify_auth)])
def api_delete_post(post_id: int):
    delete_post(post_id)
    return {"success": True}

@app.post("/api/posts/{post_id}/publish-now", dependencies=[Depends(verify_auth)])
def api_publish_now(post_id: int):
    result = publish_single_post(post_id)
    return result

@app.post("/api/ai/generate", dependencies=[Depends(verify_auth)])
def api_generate_captions(req: GenerateCaptionsRequest):
    s = get_settings()
    api_key = s.get("gemini_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="Chưa cấu hình GEMINI_API_KEY trong Cài đặt.")
    model = req.model_name or s.get("gemini_model") or "gemini-flash-latest"
    result = generate_social_captions(
        prompt=req.prompt,
        brand_voice=req.brand_voice,
        include_emojis=req.include_emojis,
        generate_hashtags=req.generate_hashtags,
        api_key=api_key,
        model_name=model
    )
    return result

@app.post("/api/story/render", dependencies=[Depends(verify_auth)])
def api_render_story(req: GenerateStoryRequest):
    source_path = UPLOAD_DIR / req.image_filename
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file ảnh gốc.")
    output_filename = f"story_{secrets.token_hex(12)}.png"
    out_path = UPLOAD_DIR / output_filename
    created = create_story_image(
        source_image_path=str(source_path),
        output_image_path=str(out_path),
        template=req.template_name,
        hook_text=req.hook_text,
        product_name=req.product_name,
        price_tag=req.price_tag,
        badge_text=req.badge_text,
        call_to_action=req.call_to_action
    )
    register_media_file(out_path, original_name=f"Story - {req.image_filename}")
    return {"success": True, "story_image": output_filename, "url": f"/api/media/{output_filename}"}

@app.get("/api/media/{filename}")
def api_serve_media(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại.")
    return FileResponse(str(file_path))

@app.get("/api/media/thumbnail/{filename}")
def api_serve_thumbnail(filename: str):
    thumb_path = THUMB_DIR / filename
    if not thumb_path.exists():
        orig_path = UPLOAD_DIR / filename
        if orig_path.exists():
            thumb_path = create_thumbnail(orig_path)
    if thumb_path and thumb_path.exists():
        return FileResponse(str(thumb_path))
    return FileResponse(str(UPLOAD_DIR / filename))

@app.get("/api/media/library", dependencies=[Depends(verify_auth)])
def api_get_media_library(search: Optional[str] = "", tag: Optional[str] = "all", page: int = 1, page_size: int = 40):
    offset = (page - 1) * page_size
    items = get_media_items(search=search, tag=tag, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}

@app.get("/api/roots/categories", dependencies=[Depends(verify_auth)])
def api_roots_categories():
    cats = fetch_roots_categories()
    return {"categories": cats}

@app.get("/api/roots/products", dependencies=[Depends(verify_auth)])
def api_roots_products(category: Optional[str] = None, page: int = 1, page_size: int = 20):
    products = fetch_roots_products(category=category or "", page=page, page_size=page_size)
    return products

@app.post("/api/roots/1click-post", dependencies=[Depends(verify_auth)])
def api_roots_1click(product: dict):
    res = quick_generate_post_from_product(product)
    return res

@app.get("/api/hashtag-groups", dependencies=[Depends(verify_auth)])
def api_get_hashtag_groups():
    return {"groups": get_hashtag_groups()}

@app.post("/api/hashtag-groups", dependencies=[Depends(verify_auth)])
def api_create_hashtag_group(req: HashtagGroupRequest):
    gid = create_hashtag_group(req.name, req.hashtags, req.category)
    return {"success": True, "id": gid}

@app.delete("/api/hashtag-groups/{group_id}", dependencies=[Depends(verify_auth)])
def api_delete_hashtag_group(group_id: int):
    delete_hashtag_group(group_id)
    return {"success": True}

@app.get("/api/caption-templates", dependencies=[Depends(verify_auth)])
def api_get_caption_templates():
    return {"templates": get_caption_templates()}

@app.post("/api/caption-templates", dependencies=[Depends(verify_auth)])
def api_create_caption_template(req: CaptionTemplateRequest):
    tid = create_caption_template(req.name, req.content, req.category, req.brand_voice)
    return {"success": True, "id": tid}

@app.delete("/api/caption-templates/{template_id}", dependencies=[Depends(verify_auth)])
def api_delete_caption_template(template_id: int):
    delete_caption_template(template_id)
    return {"success": True}

@app.get("/api/calendar/events", dependencies=[Depends(verify_auth)])
def api_get_calendar_events():
    posts = get_posts(limit=300)
    events = []
    for p in posts:
        time_val = p.get("scheduled_time") or p.get("created_at")
        events.append({
            "id": p["id"],
            "title": p.get("title") or (p.get("fb_caption", "")[:30] + "..."),
            "start": time_val,
            "status": p.get("status"),
            "target_fb": bool(p.get("target_fb")),
            "target_ig": bool(p.get("target_ig")),
            "target_google": bool(p.get("target_google")),
            "target_story": bool(p.get("target_story"))
        })
    return {"events": events}

@app.get("/api/google/auth-url", dependencies=[Depends(verify_admin_auth)])
def api_google_auth_url():
    s = get_settings()
    client_id = s.get("google_client_id")
    client_secret = s.get("google_client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Vui lòng cấu hình Google Client ID và Secret.")
    url = get_google_auth_url(client_id)
    return {"auth_url": url}

@app.get("/api/google/oauth2callback")
def api_google_oauth_callback(code: str, state: Optional[str] = None):
    exchange_google_code(code)
    return HTMLResponse("<html><body style='font-family:sans-serif;text-align:center;padding:50px;'><h2>✅ Đã liên kết Google Business thành công!</h2><p>Bạn có thể đóng tab này và quay lại trang chính.</p><script>setTimeout(()=>{window.location.href='/';}, 2000);</script></body></html>")

@app.get("/api/bulk/template")
def api_download_bulk_template():
    buf = generate_bulk_excel_template()
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=roots_social_template.xlsx"}
    )

@app.post("/api/bulk/preview", dependencies=[Depends(verify_auth)])
async def api_preview_bulk(file: UploadFile = File(...)):
    content = await file.read()
    posts = parse_bulk_file(content, file.filename)
    return {"posts": posts}

@app.post("/api/bulk/import", dependencies=[Depends(verify_auth)])
def api_import_bulk(req: BulkImportRequest):
    count = import_bulk_posts(req.posts)
    return {"success": True, "count": count}

@app.get("/api/jobs/{job_id}", dependencies=[Depends(verify_auth)])
def api_get_job(job_id: str):
    res = job_manager.get_job_status(job_id)
    if not res:
        raise HTTPException(status_code=404, detail="Job not found")
    return res

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))
