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

def normalize_product_dict(p: dict) -> dict:
    if not isinstance(p, dict):
        return {}
    ten = str(p.get("TenSanPham") or p.get("ten_san_pham") or p.get("name") or "").strip()
    anh = str(p.get("AnhSanPham") or p.get("hinh_anh") or p.get("image") or "").strip()
    gia = str(p.get("GiaSauKm") or p.get("gia") or p.get("price") or "0").strip()
    gia_goc = str(p.get("GiaTruocKm") or p.get("gia_goc") or p.get("original_price") or "0").strip()
    brand = str(p.get("Brand") or p.get("brand") or "ROOTS Organic").strip()
    xuat_xu = str(p.get("XuatXu") or p.get("xuat_xu") or "").strip()
    danh_muc = str(p.get("DanhMuc") or p.get("danh_muc") or "").strip()

    return {
        "id": p.get("id"),
        "MaNoiBo": p.get("MaNoiBo", ""),
        "TenSanPham": ten,
        "ten_san_pham": ten,
        "name": ten,
        "AnhSanPham": anh,
        "hinh_anh": anh,
        "image": anh,
        "GiaSauKm": gia,
        "gia": gia,
        "price": gia,
        "GiaTruocKm": gia_goc,
        "gia_goc": gia_goc,
        "original_price": gia_goc,
        "Brand": brand,
        "brand": brand,
        "XuatXu": xuat_xu,
        "xuat_xu": xuat_xu,
        "DanhMuc": danh_muc,
        "danh_muc": danh_muc,
        "Slug": p.get("Slug", "")
    }

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
            raw_products = res_data.get("data", [])
            products = [normalize_product_dict(p) for p in raw_products]
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
            if len(products) >= page_size and pagination.get("total_pages", 1) <= page:
                pagination["total_pages"] = page + 1

            return {
                "status": "success",
                "data": products,
                "products": products,
                "pagination": pagination
            }
    except Exception as e:
        print(f"Error fetching roots products: {e}")
    return {"status": "error", "data": [], "products": [], "pagination": {"total_items": 0, "total_pages": 1, "current_page": 1}}

def fetch_roots_flash_sale(page: int = 1, page_size: int = 30):
    """Fetch flash sale discounted products from roots.vn"""
    try:
        url = f"{ROOTS_BASE_URL}/api_flash_sale.php?page_number={page}&page_size={page_size}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            raw = data.get("data", [])
            prods = [normalize_product_dict(p) for p in raw]
            data["data"] = prods
            data["products"] = prods
            return data
    except Exception as e:
        print(f"Error fetching roots flash sale: {e}")
    return {"status": "error", "data": [], "products": []}

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

download_roots_image = _load_product_image

def _cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))

def download_and_fit_to_square_1_1(image_filename_or_url: str, output_size: int = 1080) -> str:
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
    out_filename = f"roots_sq_{uuid.uuid4().hex[:12]}.jpg"
    out_path = UPLOAD_DIR / out_filename
    square_canvas.convert("RGB").save(out_path, format="JPEG", quality=95, optimize=True)
    return out_filename

def create_social_feed_creative(
    image_filename_or_url: str,
    product_name: str,
    brand: str,
    category: str,
    price: str,
    old_price: str = "",
    aspect_ratio: str = "4:5",
) -> str:
    source = _load_product_image(image_filename_or_url)
    dims = {
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
    }
    W, H = dims.get(aspect_ratio, (1080, 1350))
    background = _cover_crop(source, (W, H)).filter(ImageFilter.GaussianBlur(34))
    background = Image.alpha_composite(background, Image.new("RGBA", (W, H), (6, 44, 31, 160)))
    canvas = background.copy()

    hero_box = (58, 166, W - 58, 854)
    panel_y = 900
    panel_h = 450

    hero = _cover_crop(source, (hero_box[2] - hero_box[0], hero_box[3] - hero_box[1]))
    hero_mask = Image.new("L", hero.size, 0)
    ImageDraw.Draw(hero_mask).rounded_rectangle((0, 0, hero.width, hero.height), radius=44, fill=255)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((hero_box[0] + 10, hero_box[1] + 14, hero_box[2] + 10, hero_box[3] + 14), radius=44, fill=(0, 0, 0, 115))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(22)))
    canvas.paste(hero, (hero_box[0], hero_box[1]), hero_mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(hero_box, radius=44, outline=(255, 255, 255, 210), width=4)

    panel = Image.new("RGBA", (W, panel_h), (247, 250, 245, 247))
    ImageDraw.Draw(panel).rounded_rectangle((0, 0, W, panel_h), radius=50, fill=(247, 250, 245, 247))
    canvas.alpha_composite(panel, (0, panel_y))
    draw = ImageDraw.Draw(canvas)

    category_text = clean_text_for_render(category or brand or "Sản phẩm hữu cơ").upper()[:55]
    draw.text((64, panel_y + 30), category_text, font=get_font(23, bold=True), fill=(5, 150, 105))

    title = clean_text_for_render(product_name or "Sản phẩm hữu cơ cao cấp")
    title_lines, title_font, line_height = wrap_and_fit_text(
        draw, title, W - 130, panel_h - 180, initial_size=46, min_size=28, bold=True, serif=True
    )
    y = panel_y + 70
    for line in title_lines[:3]:
        draw.text((64, y), line, font=title_font, fill=(15, 42, 34))
        y += line_height

    price_y = panel_y + panel_h - 110
    draw.text((64, price_y), price, font=get_font(50, bold=True), fill=(4, 120, 87))

    draw.rounded_rectangle((W - 364, price_y - 4, W - 62, price_y + 74), radius=40, fill=(5, 150, 105))
    draw.text((W - 300, price_y + 18), "ĐẶT HÀNG NGAY", font=get_font(25, bold=True), fill="white")
    draw.text((64, panel_y + panel_h - 35), "Tươi sạch mỗi ngày  •  roots.vn", font=get_font(20), fill=(71, 94, 84))

    output_name = f"roots_creative_{aspect_ratio.replace(':', '_')}_{uuid.uuid4().hex[:12]}.jpg"
    canvas.convert("RGB").save(UPLOAD_DIR / output_name, format="JPEG", quality=94, optimize=True)
    return output_name

def select_story_template(category: str, has_sale: bool) -> str:
    cat_lower = (category or "").lower()
    if has_sale:
        return "sale"
    if any(k in cat_lower for k in ["juice", "nước ép", "sinh tố", "đồ uống", "trà", "kombucha", "sữa"]):
        return "juice"
    return "organic"

def quick_generate_post_from_product(product: dict, aspect_ratio: str = "4:5") -> dict:
    if not isinstance(product, dict):
        raise ValueError("Dữ liệu sản phẩm không hợp lệ.")

    prod_name = str(product.get("TenSanPham") or "Sản phẩm hữu cơ cao cấp").strip()[:150]
    brand = str(product.get("Brand") or "ROOTS").strip()[:60]
    origin = str(product.get("XuatXu") or "Tự nhiên").strip()[:60]
    category = str(product.get("DanhMuc") or "Thực phẩm sạch").strip()[:80]
    raw_img = str(product.get("AnhSanPham") or "").strip()

    if not raw_img:
        raise ValueError("Sản phẩm không có ảnh đại diện từ ROOTS.")

    try:
        price_km = float(product.get("GiaSauKm") or 0)
    except (ValueError, TypeError):
        price_km = 0.0

    try:
        price_truoc_km = float(product.get("GiaTruocKm") or 0)
    except (ValueError, TypeError):
        price_truoc_km = 0.0

    has_discount = price_truoc_km > price_km and price_km > 0
    price_str = f"{price_km:,.0f}đ" if price_km > 0 else "Liên hệ"
    old_price_str = f"{price_truoc_km:,.0f}đ" if has_discount else ""
    product_url = "https://roots.vn"

    square_img_filename = download_and_fit_to_square_1_1(raw_img, output_size=1080)
    feed_img_filename = create_social_feed_creative(
        raw_img,
        product_name=prod_name,
        brand=brand,
        category=category,
        price=price_str,
        old_price=old_price_str,
        aspect_ratio=aspect_ratio,
    )

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

    ai_data = generate_social_captions(images=[square_img_filename], user_hint=hint)
    fb_cap = ai_data.get("fb_caption") or ai_data.get("sales_caption") or ""
    ig_cap = ai_data.get("ig_caption") or ai_data.get("viral_caption") or fb_cap
    chosen_template = select_story_template(category, has_discount)
    hook_text = (ai_data.get("trend_caption") or "").split("\n")[0].replace('"', "").replace("'", "").strip()
    if not hook_text:
        hook_text = f"🔥 {prod_name[:40]} - Chỉ {price_str}!"

    story_img_filename = create_story_image(
        source_image_name=square_img_filename,
        caption_hint=hook_text + f"\n{brand} • {category} • Đặt ngay tại ROOTS",
        template=chosen_template,
        story_link=product_url
    )

    google_cap = ai_data.get("google_caption") or fb_cap
    if len(google_cap) > 1500:
        google_cap = google_cap[:1497] + "..."

    return {
        "product_name": prod_name,
        "brand": brand,
        "price": price_str,
        "old_price": old_price_str,
        "product_url": product_url,
        "square_image": square_img_filename,
        "feed_image": feed_img_filename,
        "story_image": story_img_filename,
        "story_template": chosen_template,
        "fb_caption": fb_cap,
        "ig_caption": ig_cap,
        "google_caption": google_cap,
        "story_hook": hook_text,
    }
