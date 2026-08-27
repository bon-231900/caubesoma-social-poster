import requests
from typing import Dict, Any, List
from app.publishers.base import BasePublisher
from app.config import get_settings
from app.meta_service import publish_to_instagram, publish_instagram_story

class InstagramPublisher(BasePublisher):
    platform_name = "instagram"

    def validate_content(self, post_data: Dict[str, Any]) -> List[str]:
        errors = []
        images = post_data.get("images", [])
        if not images:
            errors.append("Instagram yêu cầu ít nhất 1 hình ảnh để tạo bài đăng feed.")
        if len(images) > 10:
            errors.append("Instagram cho phép tối đa 10 ảnh dạng carousel.")
        return errors

    def check_connection(self) -> Dict[str, Any]:
        settings = get_settings()
        ig_id = settings.get("ig_business_account_id")
        token = settings.get("fb_page_access_token")
        if not ig_id or not token:
            return {"connected": False, "error": "Chưa cấu hình Instagram Business Account ID."}
        try:
            r = requests.get(f"https://graph.facebook.com/v19.0/{ig_id}?fields=username,profile_picture_url&access_token={token}", timeout=8)
            if r.status_code == 200:
                data = r.json()
                return {"connected": True, "username": data.get("username"), "account_id": ig_id}
            return {"connected": False, "error": r.json().get("error", {}).get("message", "Lỗi kết nối Instagram")}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        settings = get_settings()
        ig_id = settings.get("ig_business_account_id")
        token = settings.get("fb_page_access_token")
        imgbb_key = settings.get("imgbb_api_key")
        caption = post_data.get("ig_caption", "")
        images = post_data.get("images", [])
        return publish_to_instagram(ig_id, token, caption, images, imgbb_key)

    def publish_story(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        settings = get_settings()
        ig_id = settings.get("ig_business_account_id")
        token = settings.get("fb_page_access_token")
        imgbb_key = settings.get("imgbb_api_key")
        story_img = post_data.get("story_image")
        return publish_instagram_story(ig_id, token, story_img, imgbb_key)
