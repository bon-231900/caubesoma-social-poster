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
            
            # Calculate total_pages accurately based on total_items or category count
            total_items = pagination.get("total_items", 0)
            if not total_items and not search:
                cats = fetch_roots_categories()
                if category and category in cats:
                    total_items = cats[category].get("count", 0)
                elif not category or category == "all":
                    total_items = sum(c.get("count", 0) for c in cats.values())
            
            total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else pagination.get("total_pages", 1)
            
            return {
                "status": "success",
                "products": products,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "total_items": total_items
                }
            }
    except Exception as e:
        print(f"Error fetching roots products: {e}")
    return {"status": "error", "products": [], "pagination": {"current_page": 1, "total_pages": 1, "total_items": 0}}

def fetch_roots_flash_sale(page: int = 1, page_size: int = 30):
    """Fetch flash sale or high-discount products from roots.vn"""
    all_data = fetch_roots_products(page=page, page_size=page_size)
    products = all_data.get("products", [])
    # Filter products that have discount
    discounted = [p for p in products if p.get("gia_goc") and p.get("gia") and float(p.get("gia_goc", 0)) > float(p.get("gia", 0))]
    return {
        "status": "success",
        "products": discounted if discounted else products[:10],
        "pagination": all_data.get("pagination", {})
    }

def download_roots_image(image_filename_or_url: str) -> Image.Image:
    """Download product image from roots CDN or external URL"""
    if not image_filename_or_url:
        raise ValueError("Chưa có đường dẫn ảnh sản phẩm.")
    
    if image_filename_or_url.startswith("http://") or image_filename_or_url.startswith("https://"):
        img_url = image_filename_or_url
    else:
        img_url = f"{ROOTS_IMG_BASE}/{image_filename_or_url}"
        
    res = requests.get(img_url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(f"Không thể tải ảnh sản phẩm từ ROOTS (HTTP {res.status_code})")
    
    img = Image.open(BytesIO(res.content))
    return img.convert("RGBA")

def download_and_fit_to_square_1_1(image_url_or_name: str, target_size: int = 1080) -> str:
    """
    Download product image, fit it nicely onto 1:1 square canvas with clean white / subtle blur background.
    Saves to uploads folder and returns filename.
    """
    img = download_roots_image(image_url_or_name)
    orig_w, orig_h = img.size
    
    # 1:1 Canvas
    canvas = Image.new("RGBA", (target_size, target_size), (255, 255, 255, 255))
    
    # Scale product to fit comfortably (around 85% of canvas width/height)
    max_dim = int(target_size * 0.88)
    scale = min(max_dim / orig_w, max_dim / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    
    resized_prod = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    pos_x = (target_size - new_w) // 2
    pos_y = (target_size - new_h) // 2
    
    canvas.paste(resized_prod, (pos_x, pos_y), resized_prod)
    
    output_filename = f"roots_sq_{uuid.uuid4().hex[:12]}.jpg"
    out_path = UPLOAD_DIR / output_filename
    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return output_filename

def create_social_feed_creative(
    product: dict,
    aspect_ratio: str = "4:5", # "4:5" (1080x1350) or "1:1" (1080x1080)
    bg_style: str = "organic" # "organic", "fresh", "clean_white"
) -> str:
    """
    Studio-quality post generator for ROOTS Organic Store:
    Creates high-converting 4:5 Feed Graphic with product visual, organic badges, price tag, and brand accents.
    """
    if aspect_ratio == "1:1":
        W, H = 1080, 1080
    else:
        W, H = 1080, 1350
        
    # Base Canvas
    canvas = Image.new("RGBA", (W, H), (250, 252, 248, 255))
    draw = ImageDraw.Draw(canvas)
    
    # Top Header Background Gradient or Organic Card
    top_header_h = int(H * 0.14)
    draw.rectangle([0, 0, W, top_header_h], fill=(22, 101, 52, 255)) # Rich Organic Green
    
    # ROOTS Brand Title in Header
    brand_font = get_font("bold", 42)
    sub_font = get_font("medium", 22)
    draw.text((40, 28), "ROOTS ORGANIC STORE", fill=(255, 255, 255, 255), font=brand_font)
    draw.text((42, 82), "🌱 THỰC PHẨM & DINH DƯỠNG HỮU CƠ CHUẨN QUỐC TẾ", fill=(187, 247, 208, 255), font=sub_font)
    
    # Load and render Product Image
    img_name = product.get("hinh_anh") or product.get("image") or ""
    if img_name:
        try:
            prod_img = download_roots_image(img_name)
            pw, ph = prod_img.size
            # Max dimensions for product area
            max_pw = int(W * 0.82)
            max_ph = int(H * 0.52)
            scale = min(max_pw / pw, max_ph / ph)
            nw = int(pw * scale)
            nh = int(ph * scale)
            resized_p = prod_img.resize((nw, nh), Image.Resampling.LANCZOS)
            
            px = (W - nw) // 2
            py = top_header_h + int((H * 0.55 - nh) // 2) + 20
            
            # Subtle soft shadow behind product
            shadow = Image.new("RGBA", (nw + 40, nh + 40), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.ellipse([10, 10, nw + 30, nh + 30], fill=(0, 0, 0, 35))
            shadow = shadow.filter(ImageFilter.GaussianBlur(16))
            canvas.paste(shadow, (px - 20, py - 10), shadow)
            
            # Paste Product
            canvas.paste(resized_p, (px, py), resized_p)
        except Exception as e:
            print(f"Error loading product image for creative: {e}")

    # Bottom Information Card (Modern Glass / White Card)
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
    
    # Product Title
    prod_name = clean_text_for_render(product.get("ten_san_pham") or product.get("name") or "Sản Phẩm Hữu Cơ ROOTS")
    title_font = get_font("bold", 36)
    name_lines = wrap_and_fit_text(draw, prod_name, title_font, W - card_margin * 2 - 60, max_lines=2)
    
    curr_y = card_y + 30
    for line in name_lines:
        draw.text((card_margin + 30, curr_y), line, fill=(15, 23, 42, 255), font=title_font)
        curr_y += 46
        
    # Origin & Category badges
    badge_font = get_font("medium", 20)
    origin = product.get("xuat_xu") or product.get("brand") or "ROOTS Certified"
    badge_text = f"📍 Xuất xứ: {origin}"
    draw.text((card_margin + 30, curr_y + 10), badge_text, fill=(71, 85, 105, 255), font=badge_font)
    
    # Pricing & CTA Box
    price_val = product.get("gia") or product.get("price") or ""
    price_orig = product.get("gia_goc") or product.get("original_price") or ""
    
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
                # Strikethrough line
                strike_w = int(draw.textlength(formatted_orig, font=orig_font))
                draw.line([(orig_x, orig_y + 14), (orig_x + strike_w, orig_y + 14)], fill=(239, 68, 68, 255), width=2)
            except Exception:
                pass

    # CTA Button on Bottom Right
    cta_w = 230
    cta_h = 60
    cta_x = W - card_margin - cta_w - 30
    cta_y = card_y + card_h - 80
    draw.rounded_rectangle([cta_x, cta_y, cta_x + cta_w, cta_y + cta_h], radius=16, fill=(22, 101, 52, 255))
    cta_font = get_font("bold", 22)
    cta_text = "ĐẶT MUA NGAY"
    tw = int(draw.textlength(cta_text, font=cta_font))
    draw.text((cta_x + (cta_w - tw) // 2, cta_y + 18), cta_text, fill=(255, 255, 255, 255), font=cta_font)

    # Save output
    output_filename = f"roots_creative_{uuid.uuid4().hex[:12]}.jpg"
    out_path = UPLOAD_DIR / output_filename
    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return output_filename

def select_story_template(product: dict) -> str:
    """Smart template selector based on product discount / type"""
    gia = float(product.get("gia", 0) or 0)
    gia_goc = float(product.get("gia_goc", 0) or 0)
    danhmuc = (product.get("danh_muc") or "").lower()
    
    if gia_goc > gia and ((gia_goc - gia) / gia_goc) >= 0.15:
        return "flash_sale"
    if "nước ép" in danhmuc or "juice" in danhmuc or "detox" in danhmuc:
        return "juice_bar"
    if "bánh" in danhmuc or "bakery" in danhmuc:
        return "organic_recipe"
    return "glassmorphism"

def quick_generate_post_from_product(product: dict, aspect_ratio: str = "4:5") -> dict:
    """
    1-Click Studio pipeline:
    1. Generates studio feed graphic (4:5 or 1:1).
    2. Generates 9:16 Story graphic with call to action.
    3. Calls Gemini AI to craft high-converting Facebook, Instagram, Google Business captions.
    """
    feed_image_name = create_social_feed_creative(product, aspect_ratio=aspect_ratio)
    
    # Story Generator
    story_hook = f"🌱 Khám phá {product.get('ten_san_pham', 'sản phẩm')} hữu cơ chuẩn quốc tế tại ROOTS!"
    story_template = select_story_template(product)
    
    story_image_name = None
    try:
        story_image_name = create_story_image(
            image_name=feed_image_name,
            caption_hint=product.get("ten_san_pham", ""),
            template=story_template,
            hook_text=story_hook,
            story_link="https://roots.vn"
        )
    except Exception as e:
        print(f"Error creating story in 1-click studio: {e}")
        story_image_name = feed_image_name

    # AI Caption Generation
    prompt_hint = (
        f"Viết bài giới thiệu sản phẩm '{product.get('ten_san_pham')}', "
        f"Giá: {product.get('gia', '')}đ (Giá gốc: {product.get('gia_goc', '')}đ). "
        f"Xuất xứ: {product.get('xuat_xu', '')}. Thương hiệu: {product.get('brand', '')}. "
        f"Điểm nổi bật: Thực phẩm hữu cơ sạch 100%, bổ dưỡng, chuẩn tự nhiên tại siêu thị ROOTS Organic Store & Juice Bar."
    )
    
    captions = {}
    try:
        captions = generate_social_captions(
            images=[feed_image_name],
            user_hint=prompt_hint
        )
    except Exception as e:
        print(f"AI Caption generation error: {e}")
        captions = {
            "facebook": f"🌿 {product.get('ten_san_pham')} - Chuẩn hữu cơ tươi ngon tại ROOTS!\n\n✨ Xuất xứ: {product.get('xuat_xu', 'ROOTS Certified')}\n💰 Giá: {product.get('gia', '')}đ\n\n👉 Ghé ngay siêu thị ROOTS hoặc đặt giao tận nơi tại https://roots.vn",
            "instagram": f"Tươi mát & chuẩn lành cùng {product.get('ten_san_pham')} 🌿\n\n#ROOTSOrganic #EatClean #OrganicFood #HealthyLifestyle",
            "google": f"🌿 {product.get('ten_san_pham')} đã có mặt tại ROOTS Organic Store. Mua sắm thực phẩm sạch ngay hôm nay!",
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
        "product_data": product
    }
