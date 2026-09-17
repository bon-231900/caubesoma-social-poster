import requests
import json
import time
from typing import Optional, List, Dict
from app.config import get_settings, update_settings
from app.meta_service import resolve_public_image_url

GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_MYBUSINESS_BASE = "https://mybusiness.googleapis.com/v4"
GOOGLE_ACCOUNT_MGMT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
GOOGLE_BUSINESS_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"

SCOPES = [
    "https://www.googleapis.com/auth/business.manage"
]

def get_google_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Generate OAuth2 consent URL for Google Business Profile."""
    scope_str = " ".join(SCOPES)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    req = requests.Request("GET", GOOGLE_AUTH_BASE, params=params)
    return req.prepare().url

def exchange_google_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    res = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=30)
    data = res.json()
    if res.status_code != 200 or "access_token" not in data:
        err = data.get("error_description", data.get("error", "Lỗi xác thực Google"))
        raise RuntimeError(f"Google OAuth Error: {err}")
    
    refresh_token = data.get("refresh_token")
    access_token = data.get("access_token")
    expires_in = data.get("expires_in", 3600)
    
    # Save refresh token and initial access token to settings
    updates = {
        "google_refresh_token": refresh_token,
        "google_access_token": access_token,
        "google_token_expiry": str(time.time() + expires_in)
    }
    update_settings(updates)
    
    # Try to auto-discover and select location (e.g. ROOTS)
    locations = get_google_locations(access_token)
    if locations:
        loc = locations[0]
        acc_name = loc.get("account_name", "")
        loc_id = loc.get("location_id", "")
        loc_title = loc.get("title", "ROOTS - Organic Store & Juice Bar")
        meta = fetch_google_location_metadata(access_token, acc_name, loc_id)
        update_settings({
            "google_account_id": loc.get("account_id", ""),
            "google_location_id": loc_id,
            "google_location_name": loc_title,
            "google_logo_url": meta.get("logo_url", "https://roots.vn/images/favicon-180x180.png"),
            "google_rating": meta.get("rating", "4.9"),
            "google_review_count": meta.get("review_count", "150+")
        })
        
    return {
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "locations": locations
    }

def fetch_google_location_metadata(access_token: str, account_name: str, location_id: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    clean_acc = account_name if str(account_name).startswith("accounts/") else f"accounts/{account_name}"
    clean_loc = location_id if str(location_id).startswith("locations/") else f"locations/{location_id}"
    
    details = {
        "logo_url": "https://roots.vn/images/favicon-180x180.png",
        "rating": "4.9",
        "review_count": "150+"
    }
    
    # 1. Fetch Profile Photo / Media from Google My Business API
    try:
        media_url = f"{GOOGLE_MYBUSINESS_BASE}/{clean_acc}/{clean_loc}/media"
        res = requests.get(media_url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            items = data.get("mediaItems", [])
            for item in items:
                category = (item.get("locationAssociation") or {}).get("category", "")
                if category in ["PROFILE", "LOGO"] and item.get("googleUrl"):
                    details["logo_url"] = item.get("googleUrl")
                    break
            # If no PROFILE tag found, take first photo if exists
            if details["logo_url"] == "https://roots.vn/images/favicon-180x180.png" and items:
                first_url = items[0].get("googleUrl")
                if first_url:
                    details["logo_url"] = first_url
    except Exception as e:
        print(f"Error fetching Google media: {e}")

    # 2. Fetch Reviews & Rating from Google My Business API
    try:
        rev_url = f"{GOOGLE_MYBUSINESS_BASE}/{clean_acc}/{clean_loc}/reviews"
        res = requests.get(rev_url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            avg = data.get("averageRating")
            count = data.get("totalReviewCount")
            if avg:
                details["rating"] = str(round(float(avg), 1))
            if count is not None:
                details["review_count"] = str(count)
    except Exception as e:
        print(f"Error fetching Google reviews: {e}")

    return details

def sync_google_business_profile() -> dict:
    access_token = get_valid_google_access_token()
    settings = get_settings()
    account_id = settings.get("google_account_id")
    location_id = settings.get("google_location_id")
    
    if not location_id:
        locs = get_google_locations(access_token)
        if locs:
            account_id = locs[0].get("account_id")
            location_id = locs[0].get("location_id")
            settings["google_location_name"] = locs[0].get("title", "ROOTS - Organic Store & Juice Bar")
        else:
            raise ValueError("Không tìm thấy địa điểm Google Business nào trong tài khoản của bạn.")
    
    acc_name = f"accounts/{account_id}" if account_id and not str(account_id).startswith("accounts/") else (account_id or "")
    meta = fetch_google_location_metadata(access_token, acc_name, location_id)
    
    updates = {
        "google_account_id": account_id,
        "google_location_id": location_id,
        "google_location_name": settings.get("google_location_name", "ROOTS - Organic Store & Juice Bar"),
        "google_logo_url": meta.get("logo_url", "https://roots.vn/images/favicon-180x180.png"),
        "google_rating": meta.get("rating", "4.9"),
        "google_review_count": meta.get("review_count", "150+")
    }
    update_settings(updates)
    return updates

def get_valid_google_access_token() -> str:
    """Get a valid access token, auto-refreshing if expired."""
    settings = get_settings()
    client_id = settings.get("google_client_id")
    client_secret = settings.get("google_client_secret")
    refresh_token = settings.get("google_refresh_token")
    access_token = settings.get("google_access_token")
    expiry = float(settings.get("google_token_expiry", 0) or 0)
    
    if not refresh_token or not client_id or not client_secret:
        raise ValueError("Chưa kết nối Google Business Account (Thiếu Client ID / Secret / Refresh Token).")

    # If token still valid for more than 2 minutes, return it
    if access_token and time.time() < (expiry - 120):
        return access_token

    # Refresh the token
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    res = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=30)
    data = res.json()
    if res.status_code == 200 and "access_token" in data:
        new_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        update_settings({
            "google_access_token": new_token,
            "google_token_expiry": str(time.time() + expires_in)
        })
        return new_token
    else:
        err = data.get("error_description", data.get("error", "Lỗi làm mới token Google"))
        raise RuntimeError(f"Lỗi refresh Google token: {err}")

def get_google_locations(access_token: str = None) -> list:
    """Retrieve all locations managed by the authenticated Google account."""
    if not access_token:
        try:
            access_token = get_valid_google_access_token()
        except Exception:
            return []

    headers = {"Authorization": f"Bearer {access_token}"}
    locations = []

    # 1. Fetch Accounts
    try:
        acc_res = requests.get(f"{GOOGLE_ACCOUNT_MGMT_BASE}/accounts", headers=headers, timeout=20)
        acc_data = acc_res.json()
        accounts = acc_data.get("accounts", [])
        
        for acc in accounts:
            acc_name = acc.get("name") # e.g. accounts/123456789
            acc_id = acc_name.split("/")[-1] if acc_name else ""
            
            # Fetch locations for this account
            loc_url = f"{GOOGLE_MYBUSINESS_BASE}/{acc_name}/locations"
            loc_res = requests.get(loc_url, headers=headers, timeout=20)
            loc_data = loc_res.json()
            
            for loc in loc_data.get("locations", []):
                loc_id = loc.get("name", "").split("/")[-1]
                locations.append({
                    "account_name": acc_name,
                    "account_id": acc_id,
                    "location_name": loc.get("name"),
                    "location_id": loc_id,
                    "title": loc.get("locationName") or loc.get("title") or "Địa điểm Google Business",
                    "address": loc.get("address", {}).get("addressLines", [""])[0] if loc.get("address") else ""
                })
    except Exception as e:
        print(f"Error fetching Google locations: {e}")

    return locations

def publish_to_google_business(
    summary: str,
    images: list,
    action_type: str = "LEARN_MORE",
    action_url: str = None,
    imgbb_api_key: str = None
) -> dict:
    """
    Publish Local Post (Update) to Google Business Profile location.
    """
    settings = get_settings()
    account_id = settings.get("google_account_id")
    location_id = settings.get("google_location_id")
    
    if not location_id:
        # Fallback: try fetching location dynamically
        token = get_valid_google_access_token()
        locs = get_google_locations(token)
        if locs:
            account_id = locs[0]["account_id"]
            location_id = locs[0]["location_id"]
            update_settings({
                "google_account_id": account_id,
                "google_location_id": location_id,
                "google_location_name": locs[0]["title"]
            })
        else:
            raise ValueError("Chưa cấu hình Location ID của Google Business. Vui lòng nhập Business Profile ID trong Cài đặt hoặc bỏ chọn Google Maps.")

    access_token = get_valid_google_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Prepare media (Google requires public URLs)
    media_items = []
    if images:
        for img in images[:1]: # Google Business Post accepts 1 primary image/video
            public_url = resolve_public_image_url(img, imgbb_api_key)
            media_items.append({
                "mediaFormat": "PHOTO",
                "sourceUrl": public_url
            })

    # Prepare payload
    post_payload = {
        "languageCode": "vi-VN",
        "summary": summary[:1500] if summary else "",
        "topicType": "STANDARD"
    }

    if media_items:
        post_payload["media"] = media_items

    # Call To Action Button (optional)
    if action_type and action_url and action_type != "NONE":
        post_payload["callToAction"] = {
            "actionType": action_type,
            "url": action_url
        }

    clean_loc_id = str(location_id).replace("locations/", "").strip()
    if account_id:
        clean_acc_id = str(account_id).replace("accounts/", "").strip()
        post_url = f"{GOOGLE_MYBUSINESS_BASE}/accounts/{clean_acc_id}/locations/{clean_loc_id}/localPosts"
    else:
        post_url = f"{GOOGLE_MYBUSINESS_BASE}/locations/{clean_loc_id}/localPosts"

    res = requests.post(post_url, headers=headers, json=post_payload, timeout=30)
    data = res.json()

    if res.status_code in [200, 201] and ("name" in data or "localPostId" in data):
        post_name = data.get("name", "")
        post_id = data.get("localPostId") or (post_name.split("/")[-1] if post_name else "google_post_ok")
        search_url = data.get("searchUrl") or f"https://www.google.com/search?q={settings.get('google_location_name', 'ROOTS')}"
        return {
            "success": True,
            "post_id": post_id,
            "url": search_url,
            "data": data
        }
    else:
        if res.status_code == 429 or "RESOURCE_EXHAUSTED" in str(data):
            raise RuntimeError("Google Cloud Project của bạn đang bị giới hạn Quota API = 0 (cần gửi yêu cầu tăng Quota trên Google Cloud Console). Nếu chỉ đăng Facebook & Instagram, vui lòng bỏ tích ô Google Maps.")
        err = data.get("error", {}).get("message", str(data))
        raise RuntimeError(f"Lỗi đăng bài Google Business: {err}")
