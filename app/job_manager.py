import asyncio
import uuid
import logging
from typing import Dict, Any, Optional
from app.database import create_job_record, update_job_record, get_job_record
from app.roots_service import download_and_fit_to_square_1_1, create_social_feed_creative, select_story_template
from app.story_service import create_story_image
from app.ai_service import generate_social_captions
from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._cancelled_jobs = set()

    def create_job(self, job_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "processing",
            "progress": 0,
            "current_step": "Khởi tạo tác vụ...",
            "result": {},
            "error_message": "",
            "metadata": metadata or {}
        }
        self._jobs[job_id] = job_data
        create_job_record(job_id, job_type, status="processing", progress=0, current_step="Khởi tạo tác vụ...")
        return job_id

    def update_progress(self, job_id: str, progress: int, current_step: str):
        if job_id in self._jobs:
            self._jobs[job_id]["progress"] = progress
            self._jobs[job_id]["current_step"] = current_step
        update_job_record(job_id, progress=progress, current_step=current_step)

    def finish_job(self, job_id: str, result: Dict[str, Any]):
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "completed"
            self._jobs[job_id]["progress"] = 100
            self._jobs[job_id]["current_step"] = "Hoàn tất thành công!"
            self._jobs[job_id]["result"] = result
        update_job_record(job_id, status="completed", progress=100, current_step="Hoàn tất thành công!", result=result)

    def fail_job(self, job_id: str, error: str):
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "failed"
            self._jobs[job_id]["current_step"] = "Tác vụ thất bại"
            self._jobs[job_id]["error_message"] = error
        update_job_record(job_id, status="failed", current_step="Tác vụ thất bại", error=error)

    def cancel_job(self, job_id: str) -> bool:
        self._cancelled_jobs.add(job_id)
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "cancelled"
            self._jobs[job_id]["current_step"] = "Đã hủy tác vụ"
        update_job_record(job_id, status="cancelled", current_step="Đã hủy tác vụ")
        return True

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled_jobs

    def get_job(self, job_id: str) -> Dict[str, Any]:
        if job_id in self._jobs:
            return self._jobs[job_id]
        rec = get_job_record(job_id)
        if rec:
            return rec
        return {"status": "not_found", "progress": 0, "current_step": "Không tìm thấy tác vụ"}

job_manager = JobManager()

async def run_1click_studio_job(job_id: str, product: dict, aspect_ratio: str = "4:5"):
    """
    Background worker executing 1-Click Studio pipeline step-by-step with real-time progress.
    """
    sq_filename = None
    feed_filename = None
    story_filename = None
    try:
        if job_manager.is_cancelled(job_id):
            return

        # Step 1: 10%
        job_manager.update_progress(job_id, 10, "Đang xác thực thông tin sản phẩm từ roots.vn...")
        await asyncio.sleep(0.2)

        prod_name = str(product.get("TenSanPham") or "Sản phẩm hữu cơ cao cấp").strip()[:150]
        brand = str(product.get("Brand") or "ROOTS").strip()[:60]
        origin = str(product.get("XuatXu") or "Tự nhiên").strip()[:60]
        category = str(product.get("DanhMuc") or "Thực phẩm sạch").strip()[:80]
        raw_img = str(product.get("AnhSanPham") or "").strip()
        slug = str(product.get("Slug") or "").strip()
        cat_slug = str(product.get("DanhMucSlug") or "").strip()

        if not raw_img:
            raise ValueError("Sản phẩm không có ảnh đại diện từ ROOTS.")

        try:
            price_km = float(product.get("GiaSauKm") or 0)
        except Exception:
            price_km = 0.0

        try:
            price_truoc_km = float(product.get("GiaTruocKm") or 0)
        except Exception:
            price_truoc_km = 0.0

        has_discount = price_truoc_km > price_km and price_km > 0
        price_str = f"{price_km:,.0f}đ" if price_km > 0 else "Liên hệ"
        old_price_str = f"{price_truoc_km:,.0f}đ" if has_discount else ""

        if slug:
            if cat_slug:
                product_url = f"https://roots.vn/danh-muc/{cat_slug}/{slug}"
            else:
                product_url = f"https://roots.vn/danh-muc/{slug}"
        else:
            product_url = "https://roots.vn"

        if job_manager.is_cancelled(job_id):
            return

        # Step 2: 35%
        job_manager.update_progress(job_id, 28, "Đang tải ảnh gốc và tạo nguồn hình sạch...")
        loop = asyncio.get_running_loop()
        sq_filename = await loop.run_in_executor(None, download_and_fit_to_square_1_1, raw_img, 1080)

        job_manager.update_progress(job_id, 45, f"Đang thiết kế social creative ({aspect_ratio}) với giá, ưu đãi và CTA...")
        feed_filename = await loop.run_in_executor(
            None,
            lambda: create_social_feed_creative(
                raw_img,
                prod_name,
                brand,
                category,
                price_str,
                old_price_str,
                aspect_ratio=aspect_ratio,
            )
        )

        if job_manager.is_cancelled(job_id):
            if sq_filename:
                (UPLOAD_DIR / sq_filename).unlink(missing_ok=True)
            if feed_filename:
                (UPLOAD_DIR / feed_filename).unlink(missing_ok=True)
            return

        # Step 3: 65%
        job_manager.update_progress(job_id, 68, "Gemini AI đang sáng tạo nội dung đa kênh & hashtag SEO...")
        hint = (
            f"Viết bài bán hàng mạng xã hội cho sản phẩm của siêu thị hữu cơ ROOTS:\n"
            f"- Tên sản phẩm: {prod_name}\n"
            f"- Thương hiệu: {brand}\n"
            f"- Xuất xứ: {origin}\n"
            f"- Danh mục: {category}\n"
            f"- Giá ưu đãi: {price_str}"
            + (f" (Giá gốc: {old_price_str})" if old_price_str else "")
            + f"\n- Link mua hàng chính hãng: {product_url}\n"
            f"Hãy làm nổi bật độ tươi ngon, hữu cơ, an toàn cho sức khỏe và kêu gọi đặt hàng ngay."
        )
        ai_data = await loop.run_in_executor(None, generate_social_captions, [sq_filename], hint)

        if job_manager.is_cancelled(job_id):
            if sq_filename:
                (UPLOAD_DIR / sq_filename).unlink(missing_ok=True)
            if feed_filename:
                (UPLOAD_DIR / feed_filename).unlink(missing_ok=True)
            return

        fb_cap = ai_data.get("sales_caption") or ai_data.get("viral_caption", "")
        ig_cap = ai_data.get("viral_caption") or fb_cap
        hashtags = ai_data.get("hashtags", [])
        if hashtags and "#roots" not in ig_cap.lower():
            ig_cap += "\n\n" + " ".join(hashtags)

        # Step 4: 85%
        job_manager.update_progress(job_id, 88, "Đang thiết kế và xuất ảnh Story 9:16 độ phân giải cao...")
        chosen_template = select_story_template(category, has_discount)
        hook_text = (ai_data.get("trend_caption") or "").split("\n")[0].replace('"', '').replace("'", "").strip()
        if not hook_text or len(hook_text) < 5:
            hook_text = f"🔥 {prod_name[:40]} - Chỉ {price_str}!"

        story_filename = await loop.run_in_executor(
            None,
            create_story_image,
            sq_filename,
            hook_text + f"\n{brand} • {category} • Đặt ngay tại ROOTS",
            chosen_template,
            product_url
        )

        google_cap = ai_data.get("sales_caption") or ai_data.get("viral_caption", "")
        if len(google_cap) > 1500:
            google_cap = google_cap[:1497] + "..."

        result_payload = {
            "product_name": prod_name,
            "brand": brand,
            "price": price_str,
            "old_price": old_price_str,
            "product_url": product_url,
            "square_image": sq_filename,
            "feed_image": feed_filename,
            "story_image": story_filename,
            "story_template": chosen_template,
            "fb_caption": fb_cap,
            "ig_caption": ig_cap,
            "google_caption": google_cap,
            "story_hook": hook_text,
            "hashtags": hashtags
        }

        # Step 5: 100%
        job_manager.finish_job(job_id, result_payload)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        if sq_filename:
            (UPLOAD_DIR / sq_filename).unlink(missing_ok=True)
        if feed_filename:
            (UPLOAD_DIR / feed_filename).unlink(missing_ok=True)
        if story_filename:
            (UPLOAD_DIR / story_filename).unlink(missing_ok=True)
        job_manager.fail_job(job_id, str(e))
