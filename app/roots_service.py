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
    """Center-crop an image to completely cover the target dimensions."""
    target_w, target_h = size
    img_w, img_h = image.size
    scale = max(target_w / img_w, target_h / img_h)
    resized_w = max(target_w, int(img_w * scale))
    resized_h = max(target_h, int(img_h * scale))
    resized = image.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    left = (resized_w - target_w) // 2
    top = (resized_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))

def download_and_fit_to_square_1_1(image_filename_or_url: str, output_size: int = 1080) -> str:
    """Download product image and fit cleanly to 1:1 square canvas."""
    prod_img = _load_product_image(image_filename_or_url)
    canvas = Image.new("RGBA", (output_size, output_size), (255, 255, 255, 255))
    pw, ph = prod_img.size
    max_dim = int(output_size * 0.88)
    scale = min(max_dim / pw, max_dim / ph)
    nw = int(pw * scale)
    nh = int(ph * scale)
    resized_p = prod_img.resize((nw, nh), Image.Resampling.LANCZOS)
    pos_x = (output_size - nw) // 2
    pos_y = (output_size - nh) // 2
    canvas.paste(resized_p, (pos_x, pos_y), resized_p)
    out_filename = f"roots_sq_{uuid.uuid4().hex[:10]}.jpg"
    out_path = UPLOAD_DIR / out_filename
    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_filename

def create_social_feed_creative(
    product: dict,
    aspect_ratio: str = "4:5",
    bg_style: str = "organic"
) -> str:
    """Studio-quality post generator for ROOTS Organic Store."""
    if aspect_ratio == "1:1":
        W, H = 1080, 1080
    else:
        W, H = 1080, 1350
        
    canvas = Image.new("RGBA", (W, H), (250, 252, 248, 255))
    draw = ImageDraw.Draw(canvas)
    
    top_header_h = int(H * 0.14)
    draw.rectangle([0, 0, W, top_header_h], fill=(22, 101, 52, 255))
    
    brand_font = get_font("bold", 42)
    sub_font = get_font("medium", 22)
    draw.text((40, 28), "ROOTS ORGANIC STORE", fill=(255, 255, 255, 255), font=brand_font)
    draw.text((42, 82), "🌱 THỰC PHẨM & DINH DƯỠNG HỮU CƠ CHUẨN QUỐC TẾ", fill=(187, 247, 208, 255), font=sub_font)
    
    img_name = product.get("AnhSanPham") or product.get("hinh_anh") or product.get("image") or ""
    if img_name:
        try:
            prod_img = _load_product_image(img_name)
            pw, ph = prod_img.size
            max_pw = int(W * 0.82)
            max_ph = int(H * 0.52)
            scale = min(max_pw / pw, max_ph / ph)
            nw = int(pw * scale)
            nh = int(ph * scale)
            resized_p = prod_img.resize((nw, nh), Image.Resampling.LANCZOS)
            
            px = (W - nw) // 2
            py = top_header_h + int((H * 0.55 - nh) // 2) + 20
            
            shadow = Image.new("RGBA", (nw + 40, nh + 40), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.ellipse([10, 10, nw + 30, nh + 30], fill=(0, 0, 0, 35))
            shadow = shadow.filter(ImageFilter.GaussianBlur(16))
            canvas.paste(shadow, (px - 20, py - 10), shadow)
            canvas.paste(resized_p, (px, py), resized_p)
        except Exception as e:
            print(f"Error loading product image: {e}")

    card_y = int(H * 0.68)
    card_margin = 35
    card_h = H - card_y - 35
    draw.rounded_rectangle(
        [card_margin, card_y, W - card_margin, card_y + card_h],
        radius=30,
        fill=(255, 255, 255, 255),
        outline=(220, 238, 225, 255),
        width=3
    )
    
    prod_name = clean_text_for_render(product.get("TenSanPham") or product.get("ten_san_pham") or "Sản Phẩm Hữu Cơ ROOTS")
    title_font = get_font("bold", 36)
    name_lines = wrap_and_fit_text(draw, prod_name, title_font, W - card_margin * 2 - 60, max_lines=2)
    
    curr_y = card_y + 30
    for line in name_lines:
        draw.text((card_margin + 30, curr_y), line, fill=(15, 23, 42, 255), font=title_font)
        curr_y += 46
        
    badge_font = get_font("medium", 20)
    origin = product.get("XuatXu") or product.get("Brand") or "ROOTS Certified"
    badge_text = f"📍 Xuất xứ: {origin}"
    draw.text((card_margin + 30, curr_y + 10), badge_text, fill=(71, 85, 105, 255), font=badge_font)
    
    price_val = product.get("GiaSauKm") or product.get("gia") or ""
    price_orig = product.get("GiaTruocKm") or product.get("gia_goc") or ""
    
    if price_val:
        try:
            formatted_price = f"{int(float(price_val)):,}đ".replace(",", ".")
        except Exception:
            formatted_price = f"{price_val}đ"
            
        price_font = get_font("bold", 44)
        draw.text((card_margin + 30, card_y + card_h - 75), formatted_price, fill=(22, 101, 52, 255), font=price_font)
        
        if price_orig and float(price_orig) > float(price_val):
            try:
                formatted_orig = f"{int(float(price_orig)):,}đ".replace(",", ".")
                orig_font = get_font("medium", 24)
                orig_x = card_margin + 30 + int(draw.textlength(formatted_price, font=price_font)) + 20
                orig_y = card_y + card_h - 62
                draw.text((orig_x, orig_y), formatted_orig, fill=(148, 163, 184, 255), font=orig_font)
                strike_w = int(draw.textlength(formatted_orig, font=orig_font))
                draw.line([(orig_x, orig_y + 14), (orig_x + strike_w, orig_y + 14)], fill=(239, 68, 68, 255), width=2)
            except Exception:
                pass

    cta_w = 230
    cta_h = 60
    cta_x = W - card_margin - cta_w - 30
    cta_y = card_y + card_h - 80
    draw.rounded_rectangle([cta_x, cta_y, cta_x + cta_w, cta_y + cta_h], radius=16, fill=(22, 101, 52, 255))
    cta_font = get_font("bold", 22)
    cta_text = "ĐẶT MUA NGAY"
    tw = int(draw.textlength(cta_text, font=cta_font))
    draw.text((cta_x + (cta_w - tw) // 2, cta_y + 18), cta_text, fill=(255, 255, 255, 255), font=cta_font)

    out_filename = f"roots_creative_{uuid.uuid4().hex[:10]}.jpg"
    out_path = UPLOAD_DIR / out_filename
    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_filename

def select_story_template(product: dict) -> str:
    gia = float(product.get("GiaSauKm") or product.get("gia", 0) or 0)
    gia_goc = float(product.get("GiaTruocKm") or product.get("gia_goc", 0) or 0)
    danhmuc = (product.get("DanhMuc") or product.get("danh_muc") or "").lower()
    
    if gia_goc > gia and ((gia_goc - gia) / gia_goc) >= 0.15:
        return "flash_sale"
    if "nước ép" in danhmuc or "juice" in danhmuc or "detox" in danhmuc:
        return "juice_bar"
    if "bánh" in danhmuc or "bakery" in danhmuc:
        return "organic_recipe"
    return "glassmorphism"

def quick_generate_post_from_product(product: dict, aspect_ratio: str = "4:5") -> dict:
    normalized = normalize_product_dict(product)
    feed_image_name = create_social_feed_creative(normalized, aspect_ratio=aspect_ratio)
    
    story_hook = f"🌱 Khám phá {normalized.get('TenSanPham')} hữu cơ chuẩn quốc tế tại ROOTS!"
    story_template = select_story_template(normalized)
    
    story_image_name = None
    try:
        story_image_name = create_story_image(
            image_name=feed_image_name,
            caption_hint=normalized.get("TenSanPham", ""),
            template=story_template,
            hook_text=story_hook,
            story_link="https://roots.vn"
        )
    except Exception as e:
        story_image_name = feed_image_name

    prompt_hint = (
        f"Viết bài giới thiệu sản phẩm '{normalized.get('TenSanPham')}', "
        f"Giá: {normalized.get('GiaSauKm')}đ (Giá gốc: {normalized.get('GiaTruocKm')}đ). "
        f"Xuất xứ: {normalized.get('XuatXu')}. Thương hiệu: {normalized.get('Brand')}. "
        f"Điểm nổi bật: Thực phẩm hữu cơ sạch 100%, bổ dưỡng, chuẩn tự nhiên tại siêu thị ROOTS Organic Store & Juice Bar."
    )
    
    captions = {}
    try:
        captions = generate_social_captions(
            images=[feed_image_name],
            user_hint=prompt_hint
        )
    except Exception as e:
        captions = {
            "facebook": f"🌿 {normalized.get('TenSanPham')} - Chuẩn hữu cơ tươi ngon tại ROOTS!\n\n✨ Xuất xứ: {normalized.get('XuatXu')}\n💰 Giá: {normalized.get('GiaSauKm')}đ\n\n👉 Ghé ngay siêu thị ROOTS hoặc đặt giao tận nơi tại https://roots.vn",
            "instagram": f"Tươi mát & chuẩn lành cùng {normalized.get('TenSanPham')} 🌿\n\n#ROOTSOrganic #EatClean #OrganicFood #HealthyLifestyle",
            "google": f"🌿 {normalized.get('TenSanPham')} đã có mặt tại ROOTS Organic Store. Mua sắm thực phẩm sạch ngay hôm nay!",
            "story_hook": story_hook
        }

    return {
        "feed_image": feed_image_name,
        "story_image": story_image_name,
        "story_template": story_template,
        "story_hook": story_hook,
        "story_link": "https://roots.vn",
        "fb_caption": captions.get("facebook", ""),
        "ig_caption": captions.get("instagram", ""),
        "google_caption": captions.get("google", ""),
        "product_data": normalized
    }
