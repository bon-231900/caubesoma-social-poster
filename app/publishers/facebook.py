import requests
from typing import Dict, Any, List
from app.publishers.base import BasePublisher
from app.config import get_settings, UPLOAD_DIR
from app.meta_service import publish_to_facebook

class FacebookPublisher(BasePublisher):
    platform_name = "facebook"

    def validate_content(self, post_data: Dict[str, Any]) -> List[str]:
        errors = []
        caption = post_data.get("fb_caption", "")
        images = post_data.get("images", [])
        if not caption and not images:
            errors.append("Facebook yêu cầu ít nhất một nội dung văn bản hoặc hình ảnh.")
        if len(images) > 10:
            errors.append("Facebook cho phép đăng tối đa 10 ảnh trong một bài.")
        return errors

    def check_connection(self) -> Dict[str, Any]:
        settings = get_settings()
        page_id = settings.get("fb_page_id")
        token = settings.get("fb_page_access_token")
        if not page_id or not token:
            return {"connected": False, "error": "Chưa cấu hình Facebook Page ID hoặc Page Access Token."}
        try:
            r = requests.get(f"https://graph.facebook.com/v19.0/{page_id}?fields=name,picture&access_token={token}", timeout=8)
            if r.status_code == 200:
                data = r.json()
                return {"connected": True, "page_name": data.get("name"), "page_id": page_id}
            return {"connected": False, "error": r.json().get("error", {}).get("message", "Lỗi kết nối Facebook")}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        settings = get_settings()
        page_id = settings.get("fb_page_id")
        token = settings.get("fb_page_access_token")
        imgbb_key = settings.get("imgbb_api_key")
        caption = post_data.get("fb_caption", "")
        images = post_data.get("images", [])
        return publish_to_facebook(page_id, token, caption, images, imgbb_key)
