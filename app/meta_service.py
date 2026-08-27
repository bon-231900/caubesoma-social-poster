import requests
import json
import base64
import time
from pathlib import Path
from urllib.parse import urlparse
from app.config import UPLOAD_DIR

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

def upload_to_imgbb(image_path: Path, api_key: str) -> str:
    """Upload local image to ImgBB and return public URL"""
    if not api_key:
        raise ValueError("Chưa cấu hình ImgBB API Key để tự động lấy URL công khai cho Instagram.")
    
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
        
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": api_key,
        "image": image_data
    }
    response = requests.post(url, data=payload, timeout=30)
    data = response.json()
    
    if response.status_code == 200 and data.get("success"):
        return data["data"]["url"]
    else:
        err = data.get("error", {}).get("message", "Lỗi upload ảnh lên ImgBB")
        raise RuntimeError(f"Lỗi ImgBB: {err}")

def resolve_public_image_url(image_item: str, imgbb_api_key: str = None) -> str:
    """If image_item is an HTTP URL, return as is. If local file, upload to ImgBB or host."""
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
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_item}")
        
    return upload_to_imgbb(local_file, imgbb_api_key)

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

def publish_facebook_story(page_id: str, page_token: str, story_image_name: str, link_url: str = None) -> dict:
    """
    Publish photo story to Facebook Page with optional interactive Call To Action link.
    """
    if not page_id or not page_token:
        raise ValueError("Thiếu Facebook Page ID hoặc Page Access Token")
        
    photo_url = f"{GRAPH_API_BASE}/{page_id}/photos"
    
    if story_image_name.startswith("http://") or story_image_name.startswith("https://"):
        payload = {
            "url": story_image_name,
            "published": "false",
            "temporary": "true",
            "access_token": page_token
        }
        res = requests.post(photo_url, data=payload, timeout=30)
    else:
        local_path = UPLOAD_DIR / story_image_name
        if not local_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file story: {story_image_name}")
        with open(local_path, "rb") as file_bytes:
            files = {"source": file_bytes}
            payload = {
                "published": "false",
                "temporary": "true",
                "access_token": page_token
            }
            res = requests.post(photo_url, data=payload, files=files, timeout=60)
            
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
        
    story_res = requests.post(story_url, data=story_payload, timeout=30)
    story_data = story_res.json()
    
    if story_res.status_code == 200 and ("id" in story_data or story_data.get("success")):
        story_id = story_data.get("id") or photo_id
        return {"story_id": story_id, "url": f"https://facebook.com/{page_id}"}
    else:
        # If call_to_action failed (some page types might restrict CTA), retry without CTA
        if "call_to_action" in story_payload:
            story_payload.pop("call_to_action")
            retry_res = requests.post(story_url, data=story_payload, timeout=30)
            retry_data = retry_res.json()
            if retry_res.status_code == 200 and ("id" in retry_data or retry_data.get("success")):
                return {"story_id": retry_data.get("id") or photo_id, "url": f"https://facebook.com/{page_id}"}
                
        raise RuntimeError(f"Lỗi đăng FB Story: {story_data.get('error', {}).get('message', str(story_data))}")

def publish_to_instagram(ig_account_id: str, page_token: str, caption: str, images: list, imgbb_api_key: str = None) -> dict:
    """
    Publish carousel or single image to Instagram Business Account.
    """
    if not ig_account_id or not page_token:
        raise ValueError("Thiếu Instagram Account ID hoặc Page Access Token")
        
    if not images:
        raise ValueError("Instagram Graph API yêu cầu phải có ít nhất 1 hình ảnh hoặc video để đăng bài.")

    # Convert all images to public URLs
    public_urls = [resolve_public_image_url(img, imgbb_api_key) for img in images]

    if len(public_urls) == 1:
        # Single Image Post
        container_url = f"{GRAPH_API_BASE}/{ig_account_id}/media"
        container_payload = {
            "image_url": public_urls[0],
            "caption": caption,
            "access_token": page_token
        }
        res = requests.post(container_url, data=container_payload, timeout=30)
        data = res.json()
        if res.status_code != 200 or "id" not in data:
            raise RuntimeError(f"Lỗi tạo Instagram Container: {data.get('error', {}).get('message', str(data))}")
        creation_id = data["id"]
    else:
        # Carousel Post (2 - 10 images)
        if len(public_urls) > 10:
            public_urls = public_urls[:10]
            
        # Step 1: Create child item containers
        child_ids = []
        for url in public_urls:
            item_url = f"{GRAPH_API_BASE}/{ig_account_id}/media"
            item_payload = {
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": page_token
            }
            res = requests.post(item_url, data=item_payload, timeout=30)
            item_data = res.json()
            if res.status_code != 200 or "id" not in item_data:
                raise RuntimeError(f"Lỗi tạo Carousel Item: {item_data.get('error', {}).get('message', str(item_data))}")
            child_ids.append(item_data["id"])

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
            raise RuntimeError(f"Lỗi tạo Carousel Container: {carousel_data.get('error', {}).get('message', str(carousel_data))}")
        creation_id = carousel_data["id"]

    # Step 3: Wait / Check container ready status
    for _ in range(10):
        status_url = f"{GRAPH_API_BASE}/{creation_id}"
        status_res = requests.get(status_url, params={"fields": "status_code", "access_token": page_token}, timeout=15)
        status_data = status_res.json()
        status_code = status_data.get("status_code", "FINISHED")
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            raise RuntimeError("Instagram Container bị lỗi xử lý hình ảnh.")
        time.sleep(2)

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
