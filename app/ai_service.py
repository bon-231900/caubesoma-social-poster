import base64
import json
import mimetypes
import requests
from pathlib import Path
from app.config import get_settings, UPLOAD_DIR

def encode_image(image_path: Path) -> dict:
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "image/jpeg"
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return {
        "inline_data": {
            "mime_type": mime_type,
            "data": data
        }
    }

def generate_social_captions(images: list, user_hint: str = "") -> dict:
    settings = get_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key:
        raise ValueError("Chưa cấu hình Gemini API Key. Vui lòng vào Cài đặt để thêm key.")

    model = settings.get("gemini_model", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
    
    parts = []

    # Attach images (up to 3 images for vision context)
    for img_name in images[:3]:
        if not (img_name.startswith("http://") or img_name.startswith("https://")):
            if Path(img_name).name != img_name:
                raise ValueError("Tên file ảnh không hợp lệ.")
            local_path = UPLOAD_DIR / img_name
            if local_path.exists():
                parts.append(encode_image(local_path))

    prompt = f"""Bạn là Giám đốc Sáng tạo và Chuyên gia Copywriter cao cấp cho siêu thị hữu cơ ROOTS (roots.vn).
Hãy quan sát kỹ hình ảnh và thông tin sản phẩm: "{user_hint}".

Hãy tạo ra nội dung mạng xã hội chuẩn mực theo đúng quy chuẩn thương hiệu ROOTS:
1. fb_caption (Song ngữ Việt - Anh):
[TIÊU ĐỀ HOA TIẾNG VIỆT]
[𝘌𝘯𝘨𝘭𝘪𝘴𝘩 𝘣𝘦𝘭𝘰𝘸]
[Đoạn văn tiếng Việt: Giàu cảm xúc, mô tả hương vị, nguồn gốc hữu cơ, lợi ích sức khỏe, sự tinh tế, lời mời mua sắm]
Mua sắm trực tiếp hoặc order online tại:
Website: https://roots.vn/
GrabMart: https://bit.ly/3ADYFHt
Shopee: https://shopee.vn/roots_organic
Capichi: https://capichideliveryapp.app.link/L1aEaCGHI3b
- - - - - - - - - -
[ENGLISH TITLE IN CAPS]
[English paragraph: Elegant storytelling, taste profile, and health benefits]
Visit Us today or Order online:
Website: https://roots.vn/
GrabMart: https://bit.ly/3ADYFHt
Shopee: https://shopee.vn/roots_organic
Capichi: https://capichideliveryapp.app.link/L1aEaCGHI3b
- - - - - - - - - -
ROOTS - Organic Store and Juice Bar
082 333 6868

2. ig_caption (Tiếng Anh + Icon danh sách + Link tree + Footer ROOTS + Hashtags)
3. google_caption (Tiếng Việt in hoa tiêu đề + cờ xuất xứ + công dụng sức khỏe + lời mời ghé 237 Nguyễn Công Trứ)
4. threads_caption (Phong cách Threads: Tự nhiên, ngắn gọn dưới 450 ký tự, đặt câu hỏi gợi mở thảo luận, kết hợp trải nghiệm healthy đời thường tại ROOTS, 1-2 hashtag)
5. viral_caption, sales_caption, trend_caption, hashtags.

Xuất ra đúng định dạng JSON:
{{
  "fb_caption": "...",
  "ig_caption": "...",
  "google_caption": "...",
  "threads_caption": "...",
  "viral_caption": "...",
  "sales_caption": "...",
  "trend_caption": "...",
  "hashtags": ["#rootsorganic", "#rootsvn", "#thucphamhuuco", "#saigonfood", "#organicstore", "#healthyfoodvietnam"]
}}
Chỉ trả về JSON thuần túy, không có giải thích thêm."""

    parts.append({"text": prompt})

    payload = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95
        }
    }

    # Attempt primary model and fallback if necessary
    candidate_models = [model, "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.5-flash-lite"]
    seen = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

    last_error = None
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, timeout=45)
            data = res.json()
            if res.status_code == 200 and "candidates" in data:
                text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text_out.startswith("```json"):
                    text_out = text_out[7:]
                if text_out.startswith("```"):
                    text_out = text_out[3:]
                if text_out.endswith("```"):
                    text_out = text_out[:-3]
                text_out = text_out.strip()
                parsed = json.loads(text_out)
                fb_c = parsed.get("fb_caption") or parsed.get("facebook") or ""
                ig_c = parsed.get("ig_caption") or parsed.get("instagram") or ""
                google_c = parsed.get("google_caption") or parsed.get("google") or ""
                threads_c = parsed.get("threads_caption") or parsed.get("threads") or ""
                hook = parsed.get("story_hook") or parsed.get("hook") or ""
                return {
                    "fb_caption": fb_c,
                    "facebook": fb_c,
                    "ig_caption": ig_c,
                    "instagram": ig_c,
                    "google_caption": google_c,
                    "google": google_c,
                    "threads_caption": threads_c,
                    "threads": threads_c,
                    "story_hook": hook,
                    "viral_caption": parsed.get("viral_caption", ""),
                    "sales_caption": parsed.get("sales_caption", ""),
                    "trend_caption": parsed.get("trend_caption", ""),
                    "hashtags": parsed.get("hashtags", []),
                    "model_used": m
                }
            else:
                last_error = data.get("error", {}).get("message", str(data))
        except Exception as e:
            last_error = str(e)

    raise RuntimeError(f"Lỗi gọi Gemini API ({model}): {last_error}")


def generate_combo_campaign_and_prompts(products: list, user_hint: str = "") -> dict:
    """
    Takes a group of selected products from roots.vn and generates:
    1. Comprehensive Multi-Product Social Captions (Facebook, Instagram, Google Business).
    2. Exactly 4 English commercial photography prompts (Flatlay, Lifestyle, Close-up, Editorial) 
       for user to generate images directly on Midjourney, FLUX.1, Ideogram, or DALL-E 3.
    """
    settings = get_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key:
        raise ValueError("Chưa cấu hình Gemini API Key. Vui lòng vào Cài đặt để thêm key.")

    model = settings.get("gemini_model", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"

    # Compile products list into structured text summary
    product_lines = []
    total_price = 0.0
    for idx, p in enumerate(products, 1):
        name = str(p.get("TenSanPham") or "Sản phẩm").strip()
        brand = str(p.get("Brand") or "ROOTS").strip()
        cat = str(p.get("DanhMuc") or "").strip()
        origin = str(p.get("XuatXu") or "").strip()
        try:
            p_km = float(p.get("GiaSauKm") or 0)
        except Exception:
            p_km = 0.0
        try:
            p_old = float(p.get("GiaTruocKm") or 0)
        except Exception:
            p_old = 0.0
        
        total_price += (p_km if p_km > 0 else p_old)
        p_str = f"{p_km:,.0f}đ" if p_km > 0 else (f"{p_old:,.0f}đ" if p_old > 0 else "Liên hệ")
        old_str = f" (Giá gốc: {p_old:,.0f}đ)" if p_old > p_km and p_km > 0 else ""
        slug = p.get("Slug", "")
        cat_slug = p.get("DanhMucSlug", "")
        link = f"https://roots.vn/danh-muc/{cat_slug}/{slug}" if (slug and cat_slug) else "https://roots.vn"
        
        product_lines.append(f"{idx}. {name} | Thương hiệu: {brand} | Phân loại: {cat} | Xuất xứ: {origin} | Giá: {p_str}{old_str} | Link: {link}")

    product_summary_text = "\n".join(product_lines)
    total_price_str = f"{total_price:,.0f}đ" if total_price > 0 else "Liên hệ"

    system_prompt = f"""Bạn là Giám đốc Sáng tạo (Creative Director) và Copywriter cao cấp cho siêu thị hữu cơ cao cấp ROOTS (roots.vn).

Người dùng vừa chọn một NHÓM GỒM {len(products)} SẢN PHẨM để làm chiến dịch bài đăng Combo / Bộ sưu tập:
---
DANH SÁCH SẢN PHẨM:
{product_summary_text}
TỔNG GIÁ COMBO DỰ KIẾN: {total_price_str}
YÊU CẦU BỔ SUNG TỪ NGƯỜI DÙNG: {user_hint or "Không có"}
---

QUY CHUẨN NỘI DUNG CAPTION THƯƠNG HIỆU ROOTS (BẮT BUỘC TUÂN THỦ 100% THEO MẪU):

1. FACEBOOK CAPTION (CHUẨN SONG NGỮ VIỆT - ANH):
Cấu trúc bài viết Facebook bắt buộc phải có đầy đủ 2 phần tiếng Việt và tiếng Anh ngăn cách chuẩn chỉnh:
[TIÊU ĐỀ HOA TIẾNG VIỆT]
[𝘌𝘯𝘨𝘭𝘪𝘴𝘩 𝘣𝘦𝘭𝘰𝘸]
[Đoạn văn tiếng Việt: Giàu cảm xúc, storytelling, miêu tả hương vị/công dụng từng món trong combo, sự chỉn chu tinh tế, lời mời mua hàng hoặc làm quà tặng]
Mua sắm trực tiếp hoặc order online tại:
Website: https://roots.vn/
GrabMart: https://bit.ly/3ADYFHt
Shopee: https://shopee.vn/roots_organic
Capichi: https://capichideliveryapp.app.link/L1aEaCGHI3b
- - - - - - - - - -
[ENGLISH TITLE IN CAPS]
[English paragraph: Elegant, engaging storytelling, describing flavors, benefits, and thoughtful gift idea]
Visit Us today or Order online:
Website: https://roots.vn/
GrabMart: https://bit.ly/3ADYFHt
Shopee: https://shopee.vn/roots_organic
Capichi: https://capichideliveryapp.app.link/L1aEaCGHI3b
- - - - - - - - - -
ROOTS - Organic Store and Juice Bar
082 333 6868

2. INSTAGRAM CAPTION (TIẾNG ANH + ICON GẠCH ĐẦU DÒNG TỪNG VỊ/MÓN + LINK TREE + HASHTAGS):
Cấu trúc Instagram:
[English Opening Hook]
[Liệt kê từng món/vị trong combo kèm icon sinh động, VD: 💚❤️ [Món 1] - [Mô tả vị] / 🥜 [Món 2] - [Mô tả] / ☁️ [Texture trải nghiệm]...]
📍 Find your favorite products at ROOTS Organic Store & Juice Bar:
▫️ Website: https://roots.vn/
▫️ GrabMart: https://bit.ly/3ADYFHt
▫️ Shopee: https://shopee.vn/roots_organic
▫️ Capichi: https://capichideliveryapp.app.link/L1aEaCGHI3b
- - - - - - - - - -
ROOTS - Organic Store and Juice Bar
🏠 237 - 239 - 241 Nguyễn Công Trứ, Phường Bến Thành, TP. HCM
📞 082 333 6868
🌍 https://roots.vn/
[Dãy hashtags phong phú tiếng Việt & tiếng Anh về sản phẩm, ẩm thực Sài Gòn, healthy food và ROOTS]

3. GOOGLE BUSINESS CAPTION (TIẾNG VIỆT HẤP DẪN + SEO LOCAL + ICON + CỜ QUỐC GIA):
[Emoji + TIÊU ĐỀ IN HOA NỔI BẬT + CỜ QUỐC GIA XUẤT XỨ (VD: 🍒 𝗢𝗖𝗘𝗔𝗡 𝗦𝗣𝗥𝗔𝗬 𝗖𝗥𝗔𝗡𝗕𝗘𝗥𝗥𝗬 – VỊ NAM VIỆT QUẤT CHUẨN MỸ ĐÃ CÓ TẠI 𝗥𝗢𝗢𝗧𝗦! 🇺🇸)]
[Câu hỏi khơi gợi vị giác, cảm xúc]
[Giới thiệu thương hiệu, nguồn gốc hữu cơ, điểm độc đáo]
[✨ Lợi ích sức khỏe, vitamin, phong cách sống lành mạnh]
[Gợi ý cách dùng / bảo quản]
[👉 Lời kêu gọi ghé siêu thị ROOTS tại 237 Nguyễn Công Trứ hoặc đặt hàng online]

4. BỘ 4 PROMPTS TẠO ẢNH AI (Tự động thích ứng bối cảnh theo ngành hàng sản phẩm đã chọn: Bàn gỗ rustic cho thực phẩm, Khay đá Marble phòng tắm Spa cho mỹ phẩm, Bàn làm việc/Yoga cho nước ép detox, Kệ giặt giũ hiện đại cho đồ gia dụng...).

XUẤT RA ĐÚNG ĐỊNH DẠNG JSON THUẦN TÚY:
{{
  "campaign_title": "Tên chủ đề ngắn gọn, cuốn hút cho Combo",
  "design_keywords_en": "Từ khóa tiếng Anh ngắn gọn (4-7 từ) để tìm kiếm ý tưởng thiết kế (VD: 'organic baby puree food photography ad' hoặc 'botanical rose shower gel spa mockup')",
  "fb_caption": "[Nội dung Facebook đúng chuẩn song ngữ và khối link theo mẫu trên]",
  "ig_caption": "[Nội dung Instagram đúng chuẩn tiếng Anh, icon danh sách, địa chỉ và hashtag theo mẫu trên]",
  "google_caption": "[Nội dung Google Business đúng chuẩn tiêu đề hoa in đậm, công dụng sức khỏe theo mẫu trên]",
  "story_hook": "Câu hook ngắn gọn, giật gân dành cho Story 9:16 (dưới 60 ký tự)",
  "image_prompts": [
    {{
      "style_id": "hero_arrangement",
      "title_vi": "📸 1. Toàn Cảnh Sắp Đặt Nghệ Thuật (Hero Shot)",
      "description_vi": "Ảnh toàn cảnh combo sắp xếp nghệ thuật theo đúng bối cảnh ngành hàng.",
      "prompt_en": "Top-down commercial product photography of [mô tả chi tiết sản phẩm thật tiếng Anh], elegantly arranged on [bối cảnh phù hợp ngành hàng], soft natural morning light, surrounded by [phụ kiện thực tế tương ứng], photorealistic, 8k resolution, commercial product studio lighting, Hasselblad H6D-100c --ar 1:1",
      "aspect_ratio": "1:1",
      "tool_tips": "Kéo ảnh thật vào ChatGPT / Midjourney / FLUX.1"
    }},
    {{
      "style_id": "contextual_lifestyle",
      "title_vi": "🏡 2. Bối Cảnh Sử Dụng Đời Thực (Lifestyle Scene)",
      "description_vi": "Bối cảnh sinh hoạt chân thực (phòng tắm spa / góc yoga / bàn làm việc / gian bếp / phòng khách tùy theo sản phẩm).",
      "prompt_en": "Eye-level cozy realistic lifestyle scene featuring [mô tả sản phẩm], placed in [không gian đời thực tương ứng], sunbeams streaming through a window, shallow depth of field, warm inviting atmosphere, hyper-realistic, 8k, award-winning commercial photography --ar 4:5",
      "aspect_ratio": "4:5",
      "tool_tips": "Kéo ảnh thật vào ChatGPT / GPT-4o / Ideogram"
    }},
    {{
      "style_id": "macro_freshness",
      "title_vi": "🔍 3. Cận Cảnh Chi Tiết & Độ Tinh Khiết (Macro Detail)",
      "description_vi": "Chụp cận cảnh texture chất liệu, giọt nước, thớ sản phẩm, bao bì cao cấp.",
      "prompt_en": "Extreme close-up macro commercial product photography focusing on [chi tiết kết cấu sản phẩm và thành phần tự nhiên], fine water droplets on surfaces, vibrant natural colors, bokeh creamy background, premium organic packaging texture, cinematic lighting, sharp crisp details, 8k resolution --ar 1:1",
      "aspect_ratio": "1:1",
      "tool_tips": "Kéo ảnh thật vào ChatGPT / FLUX.1 / Midjourney"
    }},
    {{
      "style_id": "editorial_story",
      "title_vi": "🎨 4. Phong Cách Tạp Chí Sang Trọng (Editorial & Story)",
      "description_vi": "Bố cục nghệ thuật cao cấp phong cách Pinterest/Vogue, ánh sáng nghệ thuật, tối ưu khung dọc Story 9:16.",
      "prompt_en": "Editorial magazine cover aesthetic photography featuring an artistic layout of [sản phẩm combo], earthy organic color palette matching the product, dramatic soft chiaroscuro lighting, elegant artistic shadows, Kinfolk magazine style, ultra-high definition, 8k --ar 9:16",
      "aspect_ratio": "9:16",
      "tool_tips": "Kéo ảnh thật vào ChatGPT / Midjourney / Ideogram"
    }}
  ]
}}
Lưu ý: Thay thế toàn bộ placeholder trong prompt_en bằng mô tả tiếng Anh thật, chi tiết và chính xác. Chỉ trả về JSON hợp lệ, không bọc markdown phụ."""

    payload = {
        "contents": [{
            "parts": [{"text": system_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95
        }
    }

    candidate_models = [model, "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.5-flash-lite"]
    seen = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

    last_error = None
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, timeout=50)
            data = res.json()
            if res.status_code == 200 and "candidates" in data:
                text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text_out.startswith("```json"):
                    text_out = text_out[7:]
                if text_out.startswith("```"):
                    text_out = text_out[3:]
                if text_out.endswith("```"):
                    text_out = text_out[:-3]
                text_out = text_out.strip()
                parsed = json.loads(text_out)
                parsed["total_price_str"] = total_price_str
                parsed["products_count"] = len(products)
                parsed["model_used"] = m
                
                # Build rich design inspiration search links
                kw = str(parsed.get("design_keywords_en") or "organic food social media ad").strip()
                from urllib.parse import quote_plus
                kw_q = quote_plus(kw)
                parsed["design_inspiration"] = {
                    "keywords": kw,
                    "pinterest_url": f"https://www.pinterest.com/search/pins/?q={kw_q}",
                    "behance_url": f"https://www.behance.net/search/projects?search={kw_q}",
                    "dribbble_url": f"https://dribbble.com/search/{kw_q}",
                    "lexica_url": f"https://lexica.art/?q={kw_q}",
                    "canva_url": f"https://www.canva.com/templates/?query={kw_q}",
                    "freepik_url": f"https://www.freepik.com/search?format=search&query={kw_q}+social+media"
                }
                return parsed
            else:
                last_error = data.get("error", {}).get("message", str(data))
        except Exception as e:
            last_error = str(e)

    raise RuntimeError(f"Lỗi gọi Gemini AI cho Combo Campaign ({model}): {last_error}")
