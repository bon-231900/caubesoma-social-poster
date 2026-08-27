import uuid
import requests
import urllib.parse
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from app.config import UPLOAD_DIR
from app.ai_service import generate_social_captions
from app.story_service import create_story_image, get_font, clean_text_for_render, wrap_and_fit_text

ROOTS_BASE_URL = "https://roots.vn"
ROOTS_IMG_BASE = "https://img.roots.vn/products"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_roots_categories():
    """Fetch all categories from roots.vn"""
    try:
        url = f"{ROOTS_BASE_URL}/api_categories.php"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return data.get("categories", {})
    except Exception as e:
        print(f"Error fetching roots categories: {e}")
    return {}

def fetch_roots_products(search: str = "", category: str = "", page: int = 1, page_size: int = 20):
    """Fetch product catalog from roots.vn with search and category filtering"""
    try:
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))
        params = {
            "page_number": page,
            "page_size": page_size
        }
        if search and search.strip():
            params["search"] = search.strip()
        if category and category != "all" and category != "Tất cả":
            params["DanhMuc"] = category

        url = f"{ROOTS_BASE_URL}/api_products.php?{urllib.parse.urlencode(params)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            res_data = r.json()
            products = res_data.get("data", [])
            pagination = res_data.get("pagination", {})
            
            # Enrich pagination with known category counts
            all_cats = fetch_roots_categories()
            if category and category != "all" and category != "Tất cả" and category in all_cats:
                known_count = all_cats[category].get("count", 0)
                if known_count > 0:
                    pagination["total_items"] = known_count
                    pagination["total_pages"] = max(1, (known_count + page_size - 1) // page_size)
            elif not search and all_cats:
                total_all = sum(c.get("count", 0) for c in all_cats.values() if isinstance(c, dict))
                if total_all > 0:
                    pagination["total_items"] = total_all
                    pagination["total_pages"] = max(1, (total_all + page_size - 1) // page_size)

            pagination["current_page"] = page
            # If server returned full page of items, ensure total_pages allows clicking next
            if len(products) >= page_size and pagination.get("total_pages", 1) <= page:
                pagination["total_pages"] = page + 1

            res_data["pagination"] = pagination
            return res_data
    except Exception as e:
        print(f"Error fetching roots products: {e}")
    return {"status": "error", "data": [], "pagination": {"total_items": 0, "total_pages": 1, "current_page": 1}}

def fetch_roots_flash_sale(page: int = 1, page_size: int = 30):
    """Fetch flash sale discounted products from roots.vn"""
    try:
        url = f"{ROOTS_BASE_URL}/api_flash_sale.php?page_number={page}&page_size={page_size}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching roots flash sale: {e}")
    return {"status": "error", "data": []}

def _load_product_image(image_filename_or_url: str) -> Image.Image:
    """Load an approved ROOTS URL or an existing local upload without distortion."""
    local_path = UPLOAD_DIR / image_filename_or_url
    if Path(image_filename_or_url).name == image_filename_or_url and local_path.is_file():
        return Image.open(local_path).convert("RGBA")

    if image_filename_or_url.startswith("http://") or image_filename_or_url.startswith("https://"):
        parsed = urllib.parse.urlparse(image_filename_or_url)
        allowed_hosts = {"roots.vn", "www.roots.vn", "img.roots.vn"}
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise ValueError("Chỉ chấp nhận URL ảnh HTTPS từ ROOTS.")
        img_url = image_filename_or_url
    else:
        clean_name = image_filename_or_url.split("?")[0]
        img_url = f"{ROOTS_IMG_BASE}/{clean_name}"

    try:
        r = requests.get(img_url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        if len(r.content) > 20 * 1024 * 1024:
            raise ValueError("Ảnh sản phẩm vượt quá 20 MB")
        return Image.open(BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        raise ValueError(f"Không thể tải ảnh từ URL: {img_url} ({str(e)})")

def _cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))

def download_and_fit_to_square_1_1(image_filename_or_url: str, output_size: int = 1080) -> str:
    """Create a clean square source used for AI vision and Story generation."""
    orig = _load_product_image(image_filename_or_url)

    W, H = output_size, output_size
    square_canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))

    max_inner = int(output_size * 0.90)
    scale = min(max_inner / orig.width, max_inner / orig.height)
    new_w, new_h = int(orig.width * scale), int(orig.height * scale)
    
    resized_product = orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
    pos_x = (W - new_w) // 2
    pos_y = (H - new_h) // 2

    square_canvas.paste(resized_product, (pos_x, pos_y), resized_product)

    out_filename = f"roots_sq_{uuid.uuid4().hex}.jpg"
    out_path = UPLOAD_DIR / out_filename
    square_canvas.convert("RGB").save(out_path, format="JPEG", quality=95, optimize=True)
    return out_filename

def quick_generate_post_from_product(product: dict, aspect_ratio: str = "4:5") -> dict:
    product_name = product.get("TenSanPham") or "Sản phẩm ROOTS"
    brand = product.get("Brand") or "ROOTS"
    category = product.get("DanhMuc") or "Sản phẩm"
    price = str(product.get("GiaSauKm") or "")
    old_price = str(product.get("GiaTruocKm") or "")
    img_url = product.get("AnhSanPham") or ""

    images = []
    if img_url:
        sq_img = download_and_fit_to_square_1_1(img_url)
        images.append(sq_img)

    return {
        "success": True,
        "images": images,
        "product_name": product_name,
        "brand": brand,
        "category": category,
        "price": price,
        "old_price": old_price
    }
