import os
import time
import json
import logging
import requests
from typing import Optional, List, Dict
from app.config import get_settings, update_settings
from app.meta_service import resolve_public_image_url

logger = logging.getLogger(__name__)

THREADS_GRAPH_BASE = "https://graph.threads.net/v1.0"
THREADS_OAUTH_BASE = "https://threads.net/oauth/authorize"
THREADS_TOKEN_URL = "https://graph.threads.net/oauth/access_token"

THREADS_SCOPES = [
    "threads_basic",
    "threads_content_publish",
    "threads_read_replies"
]

def get_threads_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Generate OAuth2 consent URL for Meta Threads."""
    scope_str = ",".join(THREADS_SCOPES)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope_str,
        "response_type": "code",
        "state": state,
    }
    req = requests.Request("GET", THREADS_OAUTH_BASE, params=params)
    return req.prepare().url

def exchange_threads_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for a short-lived token, then upgrade to long-lived token."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code
    }
    res = requests.post(THREADS_TOKEN_URL, data=payload, timeout=30)
    data = res.json()
    if res.status_code != 200 or "access_token" not in data:
        err = data.get("error_message", data.get("error", "Lỗi đổi authorization code Threads"))
        raise RuntimeError(f"Threads OAuth Error: {err}")

    short_token = data["access_token"]
    user_id = str(data.get("user_id", ""))

    # Upgrade to 60-day long-lived access token
    long_lived_data = exchange_for_long_lived_threads_token(short_token, client_secret)
    long_token = long_lived_data["access_token"]
    expires_in = long_lived_data.get("expires_in", 5184000)

    profile = get_threads_profile(user_id=user_id, token=long_token)

    updates = {
        "threads_access_token": long_token,
        "threads_user_id": user_id,
        "threads_username": profile.get("username", "roots.vn"),
        "threads_token_expiry": str(time.time() + expires_in)
    }
    update_settings(updates)

    return {
        "success": True,
        "user_id": user_id,
        "username": profile.get("username", "roots.vn"),
        "profile": profile
    }

def exchange_for_long_lived_threads_token(short_token: str, client_secret: str) -> dict:
    """Upgrade a short-lived Threads token to a 60-day long-lived token."""
    url = f"{THREADS_GRAPH_BASE}/access_token"
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": client_secret,
        "access_token": short_token
    }
    res = requests.get(url, params=params, timeout=30)
    data = res.json()
    if res.status_code != 200 or "access_token" not in data:
        err = data.get("error", {}).get("message", "Không thể nâng cấp lên token Threads dài hạn")
        raise RuntimeError(f"Threads Long-lived Token Error: {err}")
    return data

def refresh_threads_token(long_token: str) -> dict:
    """Refresh an unexpired long-lived Threads token (resets 60 days validity)."""
    url = f"{THREADS_GRAPH_BASE}/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": long_token
    }
    res = requests.get(url, params=params, timeout=30)
    data = res.json()
    if res.status_code != 200 or "access_token" not in data:
        err = data.get("error", {}).get("message", "Lỗi làm mới token Threads")
        raise RuntimeError(f"Threads Token Refresh Error: {err}")
    return data

def get_valid_threads_token() -> tuple:
    """Retrieve a valid access token and user_id, auto-refreshing if nearing expiry."""
    settings = get_settings()
    token = settings.get("threads_access_token") or settings.get("fb_page_access_token")
    user_id = settings.get("threads_user_id") or "me"
    expiry = float(settings.get("threads_token_expiry", 0) or 0)

    if not token:
        raise ValueError("Chưa kết nối Threads (Thiếu Threads Access Token). Vui lòng cấu hình trong Cài Đặt.")

    if expiry and time.time() > (expiry - 7 * 86400):
        try:
            refreshed = refresh_threads_token(token)
            token = refreshed["access_token"]
            new_expiry = time.time() + refreshed.get("expires_in", 5184000)
            update_settings({
                "threads_access_token": token,
                "threads_token_expiry": str(new_expiry)
            })
            logger.info("Đã tự động gia hạn Threads Access Token thành công.")
        except Exception as e:
            logger.warning(f"Không thể tự động gia hạn Threads token: {e}")

    return user_id, token

def get_threads_profile(user_id: str = None, token: str = None) -> dict:
    """Get Threads profile info (username, name, profile_picture_url, biography)."""
    if not token or not user_id:
        try:
            user_id, token = get_valid_threads_token()
        except Exception as e:
            return {"connected": False, "error": str(e)}

    url = f"{THREADS_GRAPH_BASE}/{user_id}"
    params = {
        "fields": "id,username,name,threads_profile_picture_url,threads_biography",
        "access_token": token
    }
    try:
        res = requests.get(url, params=params, timeout=20)
        data = res.json()
        if res.status_code == 200 and "id" in data:
            return {
                "connected": True,
                "user_id": data.get("id"),
                "username": data.get("username", "roots.vn"),
                "name": data.get("name", "Roots in Saigon"),
                "profile_picture": data.get("threads_profile_picture_url", ""),
                "biography": data.get("threads_biography", "")
            }
        else:
            return {"connected": False, "error": data.get("error", {}).get("message", "Không thể lấy thông tin Threads")}
    except Exception as e:
        return {"connected": False, "error": str(e)}

def wait_for_threads_container(creation_id: str, token: str, max_wait: int = 15) -> bool:
    """Poll Threads container status until FINISHED or ERROR."""
    url = f"{THREADS_GRAPH_BASE}/{creation_id}"
    params = {
        "fields": "status,error_message",
        "access_token": token
    }
    for _ in range(max_wait):
        try:
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            status = data.get("status", "FINISHED")
            if status == "FINISHED":
                return True
            elif status == "ERROR":
                err = data.get("error_message", "Lỗi xử lý ảnh trên máy chủ Threads")
                raise RuntimeError(f"Threads Container {creation_id} thất bại: {err}")
        except Exception as e:
            if "thất bại" in str(e):
                raise
        time.sleep(2)
    return True

def publish_to_threads(
    user_id: str = None,
    token: str = None,
    text: str = "",
    images: list = None,
    imgbb_api_key: str = None
) -> dict:
    """
    Publish text, single photo, or carousel to Meta Threads.
    Supports up to 500 characters of text and up to 10 images.
    """
    if not user_id or not token:
        user_id, token = get_valid_threads_token()

    images = images or []
    clean_text = (text or "").strip()

    if len(clean_text) > 500:
        clean_text = clean_text[:497] + "..."

    if not clean_text and not images:
        raise ValueError("Bài đăng Threads cần có ít nhất nội dung văn bản hoặc hình ảnh.")

    container_url = f"{THREADS_GRAPH_BASE}/{user_id}/threads"

    # Case 1: Text-only post
    if not images:
        payload = {
            "media_type": "TEXT",
            "text": clean_text,
            "access_token": token
        }
        res = requests.post(container_url, data=payload, timeout=30)
        data = res.json()
        if res.status_code != 200 or "id" not in data:
            err = data.get("error", {}).get("message", str(data))
            raise RuntimeError(f"Lỗi tạo Threads Container (Text): {err}")
        creation_id = data["id"]

    # Case 2: Single image post
    elif len(images) == 1:
        public_url = resolve_public_image_url(images[0], imgbb_api_key)
        payload = {
            "media_type": "IMAGE",
            "image_url": public_url,
            "text": clean_text,
            "access_token": token
        }
        res = requests.post(container_url, data=payload, timeout=30)
        data = res.json()
        if res.status_code != 200 or "id" not in data:
            err = data.get("error", {}).get("message", str(data))
            raise RuntimeError(f"Lỗi tạo Threads Container (Image): {err}")
        creation_id = data["id"]
        wait_for_threads_container(creation_id, token)

    # Case 3: Carousel post (2 to 10 images)
    else:
        capped_images = images[:10]
        public_urls = [resolve_public_image_url(img, imgbb_api_key) for img in capped_images]

        child_ids = []
        for idx, p_url in enumerate(public_urls):
            item_payload = {
                "media_type": "IMAGE",
                "image_url": p_url,
                "is_carousel_item": "true",
                "access_token": token
            }
            c_res = requests.post(container_url, data=item_payload, timeout=30)
            c_data = c_res.json()
            if c_res.status_code != 200 or "id" not in c_data:
                err = c_data.get("error", {}).get("message", str(c_data))
                raise RuntimeError(f"Lỗi tạo Carousel Item Threads ({idx+1}): {err}")
            child_ids.append(c_data["id"])
            time.sleep(1)

        for cid in child_ids:
            wait_for_threads_container(cid, token)

        carousel_payload = {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "text": clean_text,
            "access_token": token
        }
        car_res = requests.post(container_url, data=carousel_payload, timeout=30)
        car_data = car_res.json()
        if car_res.status_code != 200 or "id" not in car_data:
            err = car_data.get("error", {}).get("message", str(car_data))
            raise RuntimeError(f"Lỗi tạo Carousel Threads: {err}")
        creation_id = car_data["id"]
        wait_for_threads_container(creation_id, token)

    # Step 4: Publish container
    publish_url = f"{THREADS_GRAPH_BASE}/{user_id}/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": token
    }
    pub_res = requests.post(publish_url, data=pub_payload, timeout=30)
    pub_data = pub_res.json()
    if pub_res.status_code != 200 or "id" not in pub_data:
        err = pub_data.get("error", {}).get("message", str(pub_data))
        raise RuntimeError(f"Lỗi xuất bản Threads: {err}")

    thread_id = pub_data["id"]
    return {
        "success": True,
        "thread_id": thread_id,
        "url": f"https://www.threads.net/@roots.vn/post/{thread_id}"
    }
