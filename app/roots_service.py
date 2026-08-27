import uuid
import requests
import urllib.parse
from io import BytesIO
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

def fetch_roots_products(search: str = "", category: str = "", page: int = 1, page_size: int = 30):
    """Fetch product catalog from roots.vn with search and category filtering"""
    try:
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
            return r.json()
    except Exception as e:
        print(f"Error fetching roots products: {e}")
    return {"status": "error", "data": [], "pagination": {"total_items": 0, "total_pages": 0, "current_page": 1}}

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

    # Create 1:1 Square 1080x1080 Canvas (Pure Crisp White / Studio Background)
    W, H = output_size, output_size
    square_canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))

    # Calculate scale to fit comfortably inside canvas (with 5% padding)
    max_inner = int(output_size * 0.90)
    scale = min(max_inner / orig.width, max_inner / orig.height)
    new_w, new_h = int(orig.width * scale), int(orig.height * scale)
    
    resized_product = orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
    pos_x = (W - new_w) // 2
    pos_y = (H - new_h) // 2

    # Paste centered product with alpha mask
    square_canvas.paste(resized_product, (pos_x, pos_y), resized_product)

    # Save to uploads directory
    out_filename = f"roots_sq_{uuid.uuid4().hex}.jpg"
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
    """Build a premium social creative (1:1, 4:5, 9:16, 16:9) from the source product image."""
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

    # Soft organic glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-160, -120, 520, 560), fill=(52, 211, 153, 70))
    glow_draw.ellipse((W - 360, H - 400, W + 180, H + 100), fill=(250, 204, 21, 45))
    canvas = Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(70)))
    draw = ImageDraw.Draw(canvas)

    if aspect_ratio == "16:9":
        # Landscape 16:9 layout
        hero_box = (50, 50, 950, 1030)
        hero = _cover_crop(source, (hero_box[2] - hero_box[0], hero_box[3] - hero_box[1]))
        hero_mask = Image.new("L", hero.size, 0)
        ImageDraw.Draw(hero_mask).rounded_rectangle((0, 0, hero.width, hero.height), radius=40, fill=255)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((60, 60, 960, 1040), radius=40, fill=(0, 0, 0, 120))
        canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(20)))
        canvas.paste(hero, (hero_box[0], hero_box[1]), hero_mask)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(hero_box, radius=40, outline=(255, 255, 255, 200), width=4)

        panel_box = (1000, 50, 1870, 1030)
        panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(panel)
        p_draw.rounded_rectangle(panel_box, radius=40, fill=(248, 250, 246, 245))
        canvas = Image.alpha_composite(canvas, panel)
        draw = ImageDraw.Draw(canvas)

        draw.rounded_rectangle((1050, 90, 1450, 150), radius=30, fill=(236, 253, 245, 255))
        draw.ellipse((1065, 105, 1095, 135), fill=(16, 185, 129, 255))
        draw.text((1110, 106), "ROOTS • ORGANIC", font=get_font(22, bold=True), fill=(6, 78, 59))

        if old_price:
            draw.rounded_rectangle((1520, 90, 1780, 150), radius=30, fill=(225, 29, 72, 245))
            draw.text((1555, 106), "GIÁ ƯU ĐÃI", font=get_font(22, bold=True), fill="white")

        cat_text = clean_text_for_render(category or brand or "Sản phẩm hữu cơ").upper()[:50]
        draw.text((1050, 200), cat_text, font=get_font(24, bold=True), fill=(5, 150, 105))

        title = clean_text_for_render(product_name or "Sản phẩm hữu cơ cao cấp")
        lines, tfont, lheight = wrap_and_fit_text(draw, title, 750, 250, initial_size=46, min_size=30, bold=True, serif=True)
        ty = 250
        for l in lines[:4]:
            draw.text((1050, ty), l, font=tfont, fill=(15, 42, 34))
            ty += lheight

        draw.text((1050, 760), price, font=get_font(56, bold=True), fill=(4, 120, 87))
        if old_price:
            old_font = get_font(28, bold=False)
            old_x = 1050 + draw.textbbox((0, 0), price, font=get_font(56, bold=True))[2] + 20
            draw.text((old_x, 780), old_price, font=old_font, fill=(100, 116, 109))
            old_w = draw.textbbox((old_x, 780), old_price, font=old_font)[2] - old_x
            draw.line((old_x, 796, old_x + old_w, 796), fill=(225, 29, 72), width=3)

        draw.rounded_rectangle((1050, 870, 1450, 960), radius=40, fill=(5, 150, 105))
        draw.text((1120, 895), "ĐẶT HÀNG NGAY", font=get_font(26, bold=True), fill="white")
        draw.text((1050, 980), "Tươi sạch mỗi ngày • roots.vn", font=get_font(20), fill=(71, 94, 84))

    else:
        # Layouts: 1:1, 4:5, 9:16
        draw.rounded_rectangle((58, 52, 520, 128), radius=38, fill=(248, 250, 246, 240))
        draw.ellipse((78, 70, 118, 110), fill=(16, 185, 129, 255))
        draw.text((135, 70), "ROOTS  •  ORGANIC MARKET", font=get_font(26, bold=True), fill=(6, 78, 59))

        if old_price:
            draw.rounded_rectangle((W - 324, 60, W - 62, 126), radius=33, fill=(225, 29, 72, 245))
            draw.text((W - 290, 77), "GIÁ ƯU ĐÃI", font=get_font(25, bold=True), fill="white")

        if aspect_ratio == "1:1":
            hero_box = (58, 150, W - 58, 660)
            panel_y = 690
            panel_h = 390
        elif aspect_ratio == "9:16":
            hero_box = (58, 200, W - 58, 1300)
            panel_y = 1350
            panel_h = 570
        else: # 4:5
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
        for line in title_lines[:2 if aspect_ratio == "1:1" else 3]:
            draw.text((64, y), line, font=title_font, fill=(15, 42, 34))
            y += line_height

        price_y = panel_y + panel_h - 110
        draw.text((64, price_y), price, font=get_font(50, bold=True), fill=(4, 120, 87))
        if old_price:
            old_font = get_font(26, bold=False)
            old_x = 64 + draw.textbbox((0, 0), price, font=get_font(50, bold=True))[2] + 20
            draw.text((old_x, price_y + 16), old_price, font=old_font, fill=(100, 116, 109))
            old_width = draw.textbbox((old_x, price_y + 16), old_price, font=old_font)[2] - old_x
            draw.line((old_x, price_y + 32, old_x + old_width, price_y + 32), fill=(225, 29, 72), width=3)

        draw.rounded_rectangle((W - 364, price_y - 4, W - 62, price_y + 74), radius=40, fill=(5, 150, 105))
        draw.text((W - 300, price_y + 18), "ĐẶT HÀNG NGAY", font=get_font(25, bold=True), fill="white")
        draw.text((64, panel_y + panel_h - 35), "Tươi sạch mỗi ngày  •  roots.vn", font=get_font(20), fill=(71, 94, 84))

    output_name = f"roots_creative_{aspect_ratio.replace(':', '_')}_{uuid.uuid4().hex[:12]}.jpg"
    canvas.convert("RGB").save(UPLOAD_DIR / output_name, format="JPEG", quality=94, optimize=True)
    return output_name

def select_story_template(category: str, has_sale: bool) -> str:
    """
    Intelligently picks the best aesthetic Story template based on product category & sale status.
    """
    cat_lower = (category or "").lower()
    if has_sale:
        return "sale"
    if any(k in cat_lower for k in ["juice", "nước ép", "sinh tố", "đồ uống", "trà", "kombucha", "sữa", "rượu"]):
        return "juice"
    if any(k in cat_lower for k in ["bánh", "tạp chí", "trái cây", "rau", "thịt", "hải sản", "chocolate", "sô-cô-la"]):
        return "magazine"
    if any(k in cat_lower for k in ["chăm sóc", "mỹ phẩm", "nhà cửa", "gia vị", "đồ khô", "hạt", "ngũ cốc", "dầu", "gội", "tắm", "body", "skin", "care", "beauty"]):
        return "polaroid"
    return "organic"

def quick_generate_post_from_product(product: dict) -> dict:
    """
    Takes product dictionary from roots.vn, formats 1:1 square image,
    calls Gemini AI for high-converting social copy, and generates 9:16 Story canvas.
    """
    if not isinstance(product, dict):
        raise ValueError("Dữ liệu sản phẩm không hợp lệ.")

    # Sanitize and safely extract product fields
    prod_name = str(product.get("TenSanPham") or "Sản phẩm hữu cơ cao cấp").strip()[:150]
    brand = str(product.get("Brand") or "ROOTS").strip()[:60]
    origin = str(product.get("XuatXu") or "Tự nhiên").strip()[:60]
    category = str(product.get("DanhMuc") or "Thực phẩm sạch").strip()[:80]
    raw_img = str(product.get("AnhSanPham") or "").strip()
    slug = str(product.get("Slug") or "").strip()
    cat_slug = str(product.get("DanhMucSlug") or "").strip()

    if not raw_img:
        raise ValueError("Sản phẩm không có ảnh đại diện từ ROOTS.")

    # Calculate prices safely
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

    # Construct product link on roots.vn
    if slug:
        if cat_slug:
            product_url = f"https://roots.vn/danh-muc/{cat_slug}/{slug}"
        else:
            product_url = f"https://roots.vn/danh-muc/{slug}"
    else:
        product_url = "https://roots.vn"

    square_img_filename = None
    feed_img_filename = None
    story_img_filename = None

    try:
        # 1. Build a clean square source plus a social-first creative in selected aspect ratio.
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

        # 2. Build tailored AI prompt for Gemini
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

        fb_cap = ai_data.get("fb_caption") or ai_data.get("sales_caption") or ai_data.get("viral_caption", "")
        ig_cap = ai_data.get("ig_caption") or ai_data.get("viral_caption") or fb_cap
        
        # Append hashtags if present and not already in ig_cap
        hashtags = ai_data.get("hashtags", [])
        if hashtags and "#roots" not in ig_cap.lower():
            ig_cap += "\n\n" + " ".join(hashtags)

        # 3. Choose smart Story template and create 9:16 Story Canvas
        chosen_template = select_story_template(category, has_discount)
        hook_text = (ai_data.get("trend_caption") or "").split("\n")[0].replace('"', "").replace("'", "").strip()
        if not hook_text or len(hook_text) < 5:
            hook_text = f"🔥 {prod_name[:40]} - Chỉ {price_str}!"

        story_img_filename = create_story_image(
            source_image_name=square_img_filename,
            caption_hint=hook_text + f"\n{brand} • {category} • Đặt ngay tại ROOTS",
            template=chosen_template,
            story_link=product_url
        )

        # 4. Extract Google caption (up to 1500 chars)
        google_cap = ai_data.get("google_caption") or ai_data.get("sales_caption") or fb_cap
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
            "hashtags": hashtags
        }

    except Exception as e:
        # Immediate cleanup of any generated orphaned files upon failure
        if square_img_filename:
            sq_path = UPLOAD_DIR / square_img_filename
            if sq_path.exists():
                try:
                    sq_path.unlink()
                except Exception:
                    pass
        if feed_img_filename:
            feed_path = UPLOAD_DIR / feed_img_filename
            if feed_path.exists():
                try:
                    feed_path.unlink()
                except Exception:
                    pass
        if story_img_filename:
            st_path = UPLOAD_DIR / story_img_filename
            if st_path.exists():
                try:
                    st_path.unlink()
                except Exception:
                    pass
        raise e
