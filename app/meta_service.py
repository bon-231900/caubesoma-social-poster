import os
import requests
import json
import base64
import time
import logging
from pathlib import Path
from urllib.parse import urlparse
from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"

def exchange_for_permanent_page_token(short_token: str, app_id: str, app_secret: str, page_id: str = None) -> dict:
    """
    Exchange a short-lived user token (1-2 hours) for a permanent, never-expiring Page Access Token.
    1. Short-lived User Token -> 60-day Long-Lived User Token (via oauth/access_token)
    2. Long-lived User Token -> Permanent Page Access Token (via me/accounts)
    """
    if not short_token or not app_id or not app_secret:
        raise ValueError("Vui lòng cung cấp Access Token, App ID và App Secret.")

    # 1. Exchange for 60-day Long-Lived User Token
    url1 = f"{GRAPH_API_BASE}/oauth/access_token"
    params1 = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id.strip(),
        "client_secret": app_secret.strip(),
        "fb_exchange_token": short_token.strip()
    }
    res1 = requests.get(url1, params=params1, timeout=25)
    data1 = res1.json()
    if "access_token" not in data1:
        err = data1.get("error", {}).get("message", str(data1))
        raise RuntimeError(f"Lỗi đổi Token dài hạn từ Meta: {err}")

    long_user_token = data1["access_token"]

    # 2. Query me/accounts using Long-Lived User Token
    url2 = f"{GRAPH_API_BASE}/me/accounts"
    res2 = requests.get(url2, params={"access_token": long_user_token}, timeout=25)
    data2 = res2.json()

    accounts = data2.get("data", [])
    if not accounts:
        # Fallback: Query page directly if page_id is known
        if page_id:
            url_p = f"{GRAPH_API_BASE}/{page_id}"
            resp_p = requests.get(url_p, params={"fields": "access_token,name,id,instagram_business_account", "access_token": long_user_token}, timeout=25)
            datap = resp_p.json()
            if "access_token" in datap:
                ig_info = datap.get("instagram_business_account", {})
                return {
                    "success": True,
                    "page_access_token": datap["access_token"],
                    "page_id": datap.get("id", page_id),
                    "page_name": datap.get("name", ""),
                    "ig_business_account_id": ig_info.get("id", "")
                }
        err = data2.get("error", {}).get("message", "Không tìm thấy Fanpage nào được quản lý bởi tài khoản Facebook này.")
        raise RuntimeError(f"Lỗi lấy Page Token: {err}")

    selected_page = None
    if page_id:
        for acc in accounts:
            if str(acc.get("id")) == str(page_id):
                selected_page = acc
                break
    if not selected_page:
        selected_page = accounts[0]

    # Look up linked Instagram business account for convenience
    p_id = selected_page["id"]
    p_token = selected_page["access_token"]
    ig_id = ""
    try:
        ig_res = requests.get(f"{GRAPH_API_BASE}/{p_id}", params={"fields": "instagram_business_account", "access_token": p_token}, timeout=15)
        ig_id = ig_res.json().get("instagram_business_account", {}).get("id", "")
    except Exception:
        pass

    return {
        "success": True,
        "page_access_token": p_token,
        "page_id": p_id,
        "page_name": selected_page.get("name", ""),
        "ig_business_account_id": ig_id
    }

def test_meta_connection(page_id: str, page_token: str, ig_account_id: str = None) -> dict:
    result = {
        "facebook": {"connected": False, "page_name": None, "page_id": None, "picture": None, "error": None},
        "instagram": {"connected": False, "username": None, "account_id": None, "profile_picture": None, "error": None}
    }
    
    if not page_id or not page_token:
        result["facebook"]["error"] = "Thiếu Page ID hoặc Page Access Token."
        return result
        
    # Test Facebook Page
    try:
        fb_url = f"{GRAPH_API_BASE}/{page_id}"
        fb_params = {
            "fields": "id,name,link,picture{url}",
            "access_token": page_token
        }
        res = requests.get(fb_url, params=fb_params, timeout=15)
        fb_data = res.json()
        
        if res.status_code == 200 and "id" in fb_data:
            result["facebook"]["connected"] = True
            result["facebook"]["page_name"] = fb_data.get("name")
            result["facebook"]["page_id"] = fb_data.get("id")
            picture_data = fb_data.get("picture", {}).get("data", {})
            result["facebook"]["picture"] = picture_data.get("url")
        else:
            err_msg = fb_data.get("error", {}).get("message", "Không thể xác thực Facebook Page.")
            result["facebook"]["error"] = err_msg
    except Exception as e:
        result["facebook"]["error"] = str(e)

    # Test Instagram
    if ig_account_id:
        try:
            ig_url = f"{GRAPH_API_BASE}/{ig_account_id}"
            ig_params = {
                "fields": "id,name,username,profile_picture_url",
                "access_token": page_token
            }
            res = requests.get(ig_url, params=ig_params, timeout=15)
            ig_data = res.json()
            
            if res.status_code == 200 and "id" in ig_data:
                result["instagram"]["connected"] = True
                result["instagram"]["username"] = ig_data.get("username")
                result["instagram"]["account_id"] = ig_data.get("id")
                result["instagram"]["profile_picture"] = ig_data.get("profile_picture_url")
            else:
                err_msg = ig_data.get("error", {}).get("message", "Không thể xác thực Instagram Account ID.")
                result["instagram"]["error"] = err_msg
        except Exception as e:
            result["instagram"]["error"] = str(e)
    else:
        result["instagram"]["error"] = "Chưa cung cấp Instagram Business Account ID."
        
    return result

def get_server_public_url() -> str:
    """Return public base URL of the application if hosted publicly (e.g. on Render)."""
    # 1. Check RENDER_EXTERNAL_URL (Render always injects this)
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url and render_url.strip().startswith("https://"):
        return render_url.strip().rstrip("/")
    
    # 2. Check settings / env variables
    try:
        from app.config import get_settings
        settings = get_settings()
        for k in ("public_base_url", "app_url", "PUBLIC_BASE_URL", "APP_URL"):
            val = os.environ.get(k) or settings.get(k)
            if val and str(val).strip().startswith("https://"):
                return str(val).strip().rstrip("/")
    except Exception:
        pass
        
    # 3. If running on Render (RENDER env var set) or Postgres active, default to known production domain
    if os.environ.get("RENDER") or os.environ.get("DATABASE_URL"):
        return "https://caubesoma-poster.onrender.com"
        
    return ""

def ensure_clean_jpeg(image_path: Path) -> Path:
    """
    Ensures an image file is a clean RGB JPEG for 100% compliance with Instagram Graph API,
    Threads API, and Google Business API (avoids format and alpha channel errors).
    """
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            if im.format == "JPEG" and im.mode == "RGB":
                return image_path
            
            rgb_im = im.convert("RGB")
            clean_name = f"clean_{image_path.stem}.jpg"
            clean_path = image_path.parent / clean_name
            rgb_im.save(clean_path, format="JPEG", quality=92, optimize=True)
            return clean_path
    except Exception as e:
        logger.warning(f"Failed to normalize image to clean JPEG {image_path}: {e}")
        return image_path

def upload_to_imgbb(image_path: Path, api_key: str) -> str:
    """Upload local image to ImgBB and return public URL.
    Converts to clean RGB JPEG to guarantee 100% compliance with Instagram Graph API.
    """
    if not api_key:
        raise ValueError("Chưa cấu hình ImgBB API Key để tự động lấy URL công khai.")
    
    from PIL import Image
    import io

    try:
        with Image.open(image_path) as im:
            rgb_im = im.convert("RGB")
            buf = io.BytesIO()
            rgb_im.save(buf, format="JPEG", quality=92, optimize=True)
            raw_bytes = buf.getvalue()
    except Exception:
        with open(image_path, "rb") as f:
            raw_bytes = f.read()

    image_data = base64.b64encode(raw_bytes).decode("utf-8")
        
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": api_key,
        "image": image_data,
        "name": Path(image_path).stem
    }
    response = requests.post(url, data=payload, timeout=35)
    try:
        data = response.json()
    except Exception:
        data = {}
    
    if response.status_code == 200 and data.get("success"):
        return data["data"]["url"]
    else:
        err = data.get("error", {}).get("message") or response.text or "Lỗi upload ảnh lên ImgBB"
        if "forbidden" in str(err).lower():
            err = "ImgBB chặn IP máy chủ đám mây (Cloudflare 403 Forbidden). Hệ thống tự động chuyển sang dùng Direct Public URL."
        raise RuntimeError(f"Lỗi ImgBB: {err}")

def resolve_public_image_url(image_item: str, imgbb_api_key: str = None) -> str:
    """If image_item is an HTTP URL, return as is. If local file, return direct public server URL or upload to ImgBB."""
    if image_item.startswith("http://") or image_item.startswith("https://"):
        parsed = urlparse(image_item)
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("URL ảnh phải là HTTPS công khai hợp lệ.")
        return image_item
        
    # Local file in uploads dir
    if Path(image_item).name != image_item:
        raise ValueError("Tên file ảnh không hợp lệ.")
    local_file = UPLOAD_DIR / image_item
    if not local_file.exists():
        try:
            from app.database import restore_media_file_if_missing
            restore_media_file_if_missing(image_item)
        except Exception:
            pass

    if not local_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_item}")
        
    clean_file = ensure_clean_jpeg(local_file)
    clean_name = clean_file.name

    # Priority 1: Direct public URL on Render or custom domain (100% reliable, zero 3rd party rate limits)
    server_public_url = get_server_public_url()
    if server_public_url:
        return f"{server_public_url}/uploads/{clean_name}"

    # Priority 2: ImgBB upload for local development
    if imgbb_api_key:
        return upload_to_imgbb(clean_file, imgbb_api_key)

    raise ValueError("Hệ thống chưa cấu hình Public Base URL và chưa có ImgBB API Key để xuất URL công khai.")

def publish_to_facebook(page_id: str, page_token: str, caption: str, images: list) -> dict:
    """
    Publish multi-photo post or single photo or text to Facebook Fanpage.
    """
    if not page_id or not page_token:
        raise ValueError("Thiếu Facebook Page ID hoặc Page Access Token")
        
    if not images:
        # Text-only post
        url = f"{GRAPH_API_BASE}/{page_id}/feed"
        data = {
            "message": caption,
            "access_token": page_token
        }
        res = requests.post(url, data=data, timeout=30)
        res_data = res.json()
        if res.status_code == 200 and "id" in res_data:
            return {"post_id": res_data["id"], "url": f"https://facebook.com/{res_data['id']}"}
        else:
            raise RuntimeError(res_data.get("error", {}).get("message", str(res_data)))
            
    # Upload unpublished photos
    photo_ids = []
    for img in images:
        photo_url = f"{GRAPH_API_BASE}/{page_id}/photos"
        
        if img.startswith("http://") or img.startswith("https://"):
            payload = {
                "url": img,
                "published": "false",
                "access_token": page_token
            }
            res = requests.post(photo_url, data=payload, timeout=30)
        else:
            local_path = UPLOAD_DIR / img
            if not local_path.exists():
                raise FileNotFoundError(f"Không tìm thấy file {img}")
            with open(local_path, "rb") as file_bytes:
                files = {"source": file_bytes}
                payload = {
                    "published": "false",
                    "access_token": page_token
                }
                res = requests.post(photo_url, data=payload, files=files, timeout=60)
                
        res_data = res.json()
        if res.status_code == 200 and "id" in res_data:
            photo_ids.append(res_data["id"])
        else:
            raise RuntimeError(f"Lỗi tải ảnh lên FB: {res_data.get('error', {}).get('message', str(res_data))}")

    # Create Feed Post with attached media
    feed_url = f"{GRAPH_API_BASE}/{page_id}/feed"
    attached_media = [{"media_fbid": pid} for pid in photo_ids]
    feed_payload = {
        "message": caption,
        "attached_media": json.dumps(attached_media),
        "access_token": page_token
    }
    feed_res = requests.post(feed_url, data=feed_payload, timeout=30)
    feed_data = feed_res.json()
    
    if feed_res.status_code == 200 and "id" in feed_data:
        post_id = feed_data["id"]
        return {"post_id": post_id, "url": f"https://facebook.com/{post_id}"}
    else:
        raise RuntimeError(f"Lỗi đăng bài FB: {feed_data.get('error', {}).get('message', str(feed_data))}")

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_meta_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def publish_facebook_story(page_id: str, page_token: str, story_image_name: str, link_url: str = None, imgbb_api_key: str = None) -> dict:
    """
    Publish photo story to Facebook Page with optional interactive Call To Action link.
    """
    if not page_id or not page_token:
        raise ValueError("Thiếu Facebook Page ID hoặc Page Access Token")
        
    photo_url = f"{GRAPH_API_BASE}/{page_id}/photos"
    session = get_meta_session()
    
    # 1. If public URL or can convert to public URL, use URL method (avoids SSL drops)
    public_url = None
    if story_image_name.startswith("http://") or story_image_name.startswith("https://"):
        public_url = story_image_name
    else:
        try:
            public_url = resolve_public_image_url(story_image_name, imgbb_api_key)
        except Exception:
            public_url = None

    if public_url:
        payload = {
            "url": public_url,
            "published": "false",
            "temporary": "true",
            "access_token": page_token
        }
        res = session.post(photo_url, data=payload, timeout=40)
    else:
        local_path = UPLOAD_DIR / story_image_name
        if not local_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file story: {story_image_name}")
        last_err = None
        res = None
        for attempt in range(3):
            try:
                with open(local_path, "rb") as file_bytes:
                    files = {"source": file_bytes}
                    payload = {
                        "published": "false",
                        "temporary": "true",
                        "access_token": page_token
                    }
                    res = session.post(photo_url, data=payload, files=files, timeout=60)
                    if res.status_code == 200:
                        break
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        if res is None:
            raise RuntimeError(f"Lỗi kết nối SSL/mạng khi tải ảnh lên Facebook Story: {str(last_err)}")
            
    res_data = res.json()
    if res.status_code != 200 or "id" not in res_data:
        raise RuntimeError(f"Lỗi tải ảnh tạm cho FB Story: {res_data.get('error', {}).get('message', str(res_data))}")
        
    photo_id = res_data["id"]
    
    # Create Photo Story
    story_url = f"{GRAPH_API_BASE}/{page_id}/photo_stories"
    story_payload = {
        "photo_id": photo_id,
        "access_token": page_token
    }
    
    if link_url and link_url.strip().startswith("http"):
        story_payload["call_to_action"] = json.dumps({
            "type": "OPEN_LINK",
            "value": {
                "link": link_url.strip()
            }
        })
        
    story_res = session.post(story_url, data=story_payload, timeout=30)
    story_data = story_res.json()
    
    if story_res.status_code == 200 and ("id" in story_data or story_data.get("success")):
        story_id = story_data.get("id") or photo_id
        return {"story_id": story_id, "url": f"https://facebook.com/{page_id}"}
    else:
        # If call_to_action failed (some page types might restrict CTA), retry without CTA
        if "call_to_action" in story_payload:
            story_payload.pop("call_to_action")
            retry_res = session.post(story_url, data=story_payload, timeout=30)
            retry_data = retry_res.json()
            if retry_res.status_code == 200 and ("id" in retry_data or retry_data.get("success")):
                return {"story_id": retry_data.get("id") or photo_id, "url": f"https://facebook.com/{page_id}"}
                
        raise RuntimeError(f"Lỗi đăng FB Story: {story_data.get('error', {}).get('message', str(story_data))}")

def publish_to_instagram(ig_account_id: str, page_token: str, caption: str, images: list, imgbb_api_key: str = None) -> dict:
    """
    Publish carousel or single image to Instagram Business Account with robust CDN propagation retry and container readiness checks.
    """
    if not ig_account_id or not page_token:
        raise ValueError("Thiếu Instagram Account ID hoặc Page Access Token")
        
    if not images:
        raise ValueError("Instagram Graph API yêu cầu phải có ít nhất 1 hình ảnh hoặc video để đăng bài.")

    # Convert all images to public URLs (automatically converted to clean RGB JPEG)
    public_urls = [resolve_public_image_url(img, imgbb_api_key) for img in images]

    def create_container_with_retry(payload: dict, desc: str) -> str:
        container_url = f"{GRAPH_API_BASE}/{ig_account_id}/media"
        last_error = None
        for attempt in range(4):
            if attempt > 0:
                time.sleep(2 * attempt)
            res = requests.post(container_url, data=payload, timeout=30)
            data = res.json()
            if res.status_code == 200 and "id" in data:
                return data["id"]
            err_msg = data.get("error", {}).get("message", str(data))
            last_error = err_msg
            if any(k in err_msg.lower() for k in ["media type", "download", "fetch", "temporary", "timeout"]):
                continue
            else:
                break
        raise RuntimeError(f"Lỗi tạo {desc}: {last_error}")

    def wait_for_container_finished(cid: str, max_wait: int = 15):
        for _ in range(max_wait):
            status_url = f"{GRAPH_API_BASE}/{cid}"
            status_res = requests.get(status_url, params={"fields": "status_code", "access_token": page_token}, timeout=15)
            status_data = status_res.json()
            status_code = status_data.get("status_code", "FINISHED")
            if status_code == "FINISHED":
                return True
            elif status_code == "ERROR":
                raise RuntimeError(f"Instagram Container {cid} bị lỗi xử lý hình ảnh.")
            time.sleep(2)
        return True

    if len(public_urls) == 1:
        # Single Image Post
        container_payload = {
            "image_url": public_urls[0],
            "caption": caption,
            "access_token": page_token
        }
        creation_id = create_container_with_retry(container_payload, "Instagram Container")
    else:
        # Carousel Post (2 - 10 images)
        if len(public_urls) > 10:
            public_urls = public_urls[:10]
            
        # Step 1: Create child item containers
        child_ids = []
        for idx, url in enumerate(public_urls):
            item_payload = {
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": page_token
            }
            cid = create_container_with_retry(item_payload, f"Carousel Item {idx+1}")
            child_ids.append(cid)
            time.sleep(1)

        # Step 1b: Ensure all child items are FINISHED before creating carousel
        for cid in child_ids:
            wait_for_container_finished(cid, max_wait=8)

        # Step 2: Create Carousel Parent Container
        carousel_url = f"{GRAPH_API_BASE}/{ig_account_id}/media"
        carousel_payload = {
            "media_type": "CAROUSEL",
            "children": json.dumps(child_ids),
            "caption": caption,
            "access_token": page_token
        }
        res = requests.post(carousel_url, data=carousel_payload, timeout=30)
        carousel_data = res.json()
        if res.status_code != 200 or "id" not in carousel_data:
            carousel_payload["children"] = ",".join(child_ids)
            res2 = requests.post(carousel_url, data=carousel_payload, timeout=30)
            carousel_data = res2.json()
            if res2.status_code != 200 or "id" not in carousel_data:
                raise RuntimeError(f"Lỗi tạo Carousel Container: {carousel_data.get('error', {}).get('message', str(carousel_data))}")
        creation_id = carousel_data["id"]

    # Step 3: Wait / Check main container ready status
    wait_for_container_finished(creation_id, max_wait=12)

    # Step 4: Publish container
    publish_url = f"{GRAPH_API_BASE}/{ig_account_id}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": page_token
    }
    pub_res = requests.post(publish_url, data=publish_payload, timeout=30)
    pub_data = pub_res.json()
    
    if pub_res.status_code == 200 and "id" in pub_data:
        ig_post_id = pub_data["id"]
        return {"post_id": ig_post_id, "url": f"https://www.instagram.com/"}
    else:
        raise RuntimeError(f"Lỗi Publish Instagram: {pub_data.get('error', {}).get('message', str(pub_data))}")

def publish_instagram_story(ig_account_id: str, page_token: str, story_image_name: str, imgbb_api_key: str = None) -> dict:
    """
    Publish photo story (9:16) to Instagram Business Account.
    """
    if not ig_account_id or not page_token:
        raise ValueError("Thiếu Instagram Account ID hoặc Page Access Token")
        
    public_url = resolve_public_image_url(story_image_name, imgbb_api_key)
    
    # 1. Create Story Container
    container_url = f"{GRAPH_API_BASE}/{ig_account_id}/media"
    container_payload = {
        "image_url": public_url,
        "media_type": "STORIES",
        "access_token": page_token
    }
    res = requests.post(container_url, data=container_payload, timeout=30)
    data = res.json()
    if res.status_code != 200 or "id" not in data:
        raise RuntimeError(f"Lỗi tạo Instagram Story Container: {data.get('error', {}).get('message', str(data))}")
    creation_id = data["id"]
    
    # 2. Wait for Story ready
    for _ in range(12):
        status_url = f"{GRAPH_API_BASE}/{creation_id}"
        status_res = requests.get(status_url, params={"fields": "status_code", "access_token": page_token}, timeout=15)
        status_data = status_res.json()
        status_code = status_data.get("status_code", "FINISHED")
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            raise RuntimeError("Instagram Story Container bị lỗi xử lý hình ảnh.")
        time.sleep(2)
        
    # 3. Publish Story
    publish_url = f"{GRAPH_API_BASE}/{ig_account_id}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": page_token
    }
    pub_res = requests.post(publish_url, data=publish_payload, timeout=30)
    pub_data = pub_res.json()
    
    if pub_res.status_code == 200 and "id" in pub_data:
        story_id = pub_data["id"]
        return {"story_id": story_id, "url": f"https://www.instagram.com/"}
    else:
        raise RuntimeError(f"Lỗi Publish Instagram Story: {pub_data.get('error', {}).get('message', str(pub_data))}")
