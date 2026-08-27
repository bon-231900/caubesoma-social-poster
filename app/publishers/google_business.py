from typing import Dict, Any, List
from app.publishers.base import BasePublisher
from app.config import get_settings
from app.google_service import publish_to_google_business

class GoogleBusinessPublisher(BasePublisher):
    platform_name = "google_business"

    def validate_content(self, post_data: Dict[str, Any]) -> List[str]:
        errors = []
        caption = post_data.get("google_caption", "") or post_data.get("fb_caption", "")
        if not caption:
            errors.append("Google Business yêu cầu nội dung cập nhật (Summary caption).")
        if len(caption) > 1500:
            errors.append("Google Business giới hạn tối đa 1.500 ký tự.")
        return errors

    def check_connection(self) -> Dict[str, Any]:
        settings = get_settings()
        has_client = bool(settings.get("google_client_id") and settings.get("google_client_secret"))
        has_refresh = bool(settings.get("google_refresh_token"))
        location_id = settings.get("google_location_id")
        if has_client and has_refresh and location_id:
            return {"connected": True, "location_id": location_id, "location_name": settings.get("google_location_name", "ROOTS")}
        return {"connected": False, "error": "Chưa kết nối Google Business hoặc chưa chọn chi nhánh."}

    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        caption = post_data.get("google_caption", "") or post_data.get("fb_caption", "")
        images = post_data.get("images", [])
        action_type = post_data.get("google_action_type", "LEARN_MORE")
        action_url = post_data.get("google_action_url")
        return publish_to_google_business(caption, images, action_type, action_url)
