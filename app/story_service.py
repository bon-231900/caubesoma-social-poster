import uuid
import math
import re
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from app.config import UPLOAD_DIR

def get_font(size=36, bold=False, serif=False):
    """
    Load high-quality Windows / Linux fonts with intelligent fallback.
    Uses Times New Roman for Vietnamese-friendly Serif, and Segoe UI / Arial for Sans.
    """
    if serif:
        font_paths = [
            "C:\\Windows\\Fonts\\timesbd.ttf" if bold else "C:\\Windows\\Fonts\\times.ttf",
            "C:\\Windows\\Fonts\\cambriab.ttf" if bold else "C:\\Windows\\Fonts\\cambria.ttf",
            "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
        ]
    else:
        font_paths = [
            "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\tahomabd.ttf" if bold else "C:\\Windows\\Fonts\\tahoma.ttf",
            "C:\\Windows\\Fonts\\calibrib.ttf" if bold else "C:\\Windows\\Fonts\\calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
    for fp in font_paths:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

def clean_text_for_render(text: str) -> str:
    """Strips emoji unicode characters that standard fonts render as tofu [] squares."""
    if not text:
        return ""
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\ufe0f]",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub("", text)
    return " ".join(cleaned.strip().split())

def draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r_outer: int, r_inner: int, fill: tuple, outline: tuple = None):
    """Draws a sharp geometric 5-point star vector."""
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=fill, outline=outline)

def wrap_and_fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    initial_size: int = 38,
    min_size: int = 24,
    bold: bool = True,
    serif: bool = False
):
    """
    Wrap text to fit comfortably inside max_width and max_height.
    Dynamically scales font size down until all text fits without overflow.
    """
    cleaned_text = clean_text_for_render(text)
    if not cleaned_text:
        return [], get_font(initial_size, bold=bold, serif=serif), int(initial_size * 1.35)

    size = initial_size
    while size >= min_size:
        font = get_font(size, bold=bold, serif=serif)
        words = cleaned_text.split(" ")
        lines = []
        cur_line = []
        
        for word in words:
            test_line = " ".join(cur_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                cur_line.append(word)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                    cur_line = [word]
                else:
                    lines.append(word)
                    cur_line = []
        if cur_line:
            lines.append(" ".join(cur_line))
            
        line_height = int(size * 1.35)
        total_h = len(lines) * line_height
        
        if total_h <= max_height:
            return lines, font, line_height
        size -= 2

    # Fallback to truncated lines with minimum font
    font = get_font(min_size, bold=bold, serif=serif)
    line_height = int(min_size * 1.35)
    max_lines = max(1, max_height // line_height)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if len(lines[-1]) > 3:
            lines[-1] = lines[-1][:-3] + "..."
    return lines, font, line_height

def draw_rounded_card_with_shadow(
    base_img: Image.Image,
    card_img: Image.Image,
    pos: tuple,
    radius: int = 36,
    shadow_blur: int = 26,
    shadow_offset: int = 16,
    shadow_color: tuple = (0, 0, 0, 160),
    border_color: tuple = (255, 255, 255, 230),
    border_width: int = 4
):
    """Draws a rounded image onto base_img with soft ambient drop shadow and crisp border."""
    cw, ch = card_img.size
    cx, cy = pos

    pad = shadow_blur * 2
    shadow = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle(
        [(pad, pad), (cw + pad, ch + pad)],
        radius=radius,
        fill=shadow_color
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    base_img.paste(shadow, (cx - pad, cy - pad + shadow_offset), shadow)

    mask = Image.new("L", (cw, ch), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rounded_rectangle([(0, 0), (cw, ch)], radius=radius, fill=255)
    base_img.paste(card_img, (cx, cy), mask)
    
    if border_width > 0:
        b_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(b_img)
        b_draw.rounded_rectangle(
            [(0, 0), (cw - 1, ch - 1)],
            radius=radius,
            outline=border_color,
            width=border_width
        )
        base_img.paste(b_img, (cx, cy), b_img)

def draw_centered_text(draw: ImageDraw.ImageDraw, box: tuple, text: str, font: ImageFont.ImageFont, fill: tuple):
    """Draw text centered both horizontally and vertically within bounding box (x1, y1, x2, y2)."""
    clean_txt = clean_text_for_render(text)
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), clean_txt, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x1 + (x2 - x1 - tw) // 2
    ty = y1 + (y2 - y1 - th) // 2 - bbox[1]
    draw.text((tx, ty), clean_txt, font=font, fill=fill)

def create_story_image(
    source_image_name: str,
    caption_hint: str = "",
    brand_name: str = "ROOTS - Organic Store",
    template: str = "organic",
    story_link: str = "https://roots.vn"
) -> str:
    """
    Generate retail & supermarket optimized 1080x1920 (9:16) Story canvas.
    STRICT SAFE ZONE:
    - Top Safe Zone (Y: 0 -> 300px): Avoids Meta Story Header (Avatar, Username, Progress bar, Close button).
    - Bottom Safe Zone (Y: 1600 -> 1920px): Avoids Reply message input, Like/Share buttons, and Link CTA.
    - Content Active Zone (Y: 300px -> 1580px, X: 70px -> 1010px).
    """
    source_path = UPLOAD_DIR / source_image_name
    if Path(source_image_name).name != source_image_name:
        raise ValueError("Tên file ảnh không hợp lệ.")
    if not source_path.exists():
        raise FileNotFoundError(f"Không tìm thấy ảnh gốc: {source_image_name}")

    orig = Image.open(source_path).convert("RGBA")
    W, H = 1080, 1920
    story = Image.new("RGBA", (W, H), (15, 23, 42, 255))
    
    # Process Hook & Subtitle text cleanly
    raw_lines = [l.strip() for l in caption_hint.strip().split("\n") if l.strip()]
    hook = raw_lines[0] if raw_lines else "Sản phẩm tươi ngon thượng hạng đã cập bến!"
    sub_text = raw_lines[1] if len(raw_lines) > 1 else "100% Tươi Sạch • An Toàn • Đảm Bảo Chất Lượng"

    # =========================================================================
    # TEMPLATE 1: SIÊU THỊ HỮU CƠ (ORGANIC SUPERMARKET - PREMIUM & FRESH)
    # =========================================================================
    if template in ["organic", "glassmorphism"]:
        bg_ratio = max(W / orig.width, H / orig.height)
        bg_w, bg_h = int(orig.width * bg_ratio), int(orig.height * bg_ratio)
        bg_img = orig.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        bg_img = bg_img.crop(((bg_w - W) // 2, (bg_h - H) // 2, (bg_w - W) // 2 + W, (bg_h - H) // 2 + H))
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=40))
        
        tint = Image.new("RGBA", (W, H), (10, 48, 34, 180))
        dark_layer = Image.new("RGBA", (W, H), (15, 23, 42, 90))
        bg_img = Image.alpha_composite(bg_img, tint)
        bg_img = Image.alpha_composite(bg_img, dark_layer)
        story.paste(bg_img, (0, 0))

        draw = ImageDraw.Draw(story)

        # Top Badge
        badge_w, badge_h = 680, 75
        badge_x, badge_y = (W - badge_w) // 2, 310
        draw.rounded_rectangle(
            [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
            radius=38,
            fill=(250, 247, 242, 250),
            outline=(52, 211, 153, 255),
            width=3
        )
        f_badge = get_font(26, bold=True, serif=False)
        draw_centered_text(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), "100% ORGANIC & FRESH DAILY", f_badge, (10, 48, 34))

        # Center Product Photo Card
        max_cw, max_ch = 940, 790
        scale = min(max_cw / orig.width, max_ch / orig.height)
        cw, ch = int(orig.width * scale), int(orig.height * scale)
        card_img = orig.resize((cw, ch), Image.Resampling.LANCZOS)
        cx = (W - cw) // 2
        cy = 410 + (max_ch - ch) // 2
        draw_rounded_card_with_shadow(story, card_img, (cx, cy), radius=38, shadow_blur=28, border_color=(255, 255, 255, 255), border_width=4)

        # Bottom Info Card
        info_box_w, info_box_h = 940, 345
        info_box_x, info_box_y = (W - info_box_w) // 2, 1230
        
        info_card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ic_draw = ImageDraw.Draw(info_card)
        ic_draw.rounded_rectangle(
            [(info_box_x, info_box_y), (info_box_x + info_box_w, info_box_y + info_box_h)],
            radius=36,
            fill=(15, 33, 27, 240),
            outline=(52, 211, 153, 180),
            width=3
        )
        story = Image.alpha_composite(story, info_card)
        draw = ImageDraw.Draw(story)

        text_max_w = info_box_w - 70
        hook_lines, f_hook, h_lh = wrap_and_fit_text(draw, hook, text_max_w, 130, initial_size=34, min_size=24, bold=True, serif=True)
        cur_y = info_box_y + 25
        for line in hook_lines:
            draw.text((info_box_x + 35, cur_y), line, fill=(255, 255, 255), font=f_hook)
            cur_y += h_lh

        f_sub = get_font(22, bold=False)
        sub_preview = clean_text_for_render(sub_text)[:75] + ("..." if len(sub_text) > 75 else "")
        draw.text((info_box_x + 35, cur_y + 8), sub_preview, fill=(167, 243, 208), font=f_sub)

        # Big Shopping CTA Button
        cta_btn_w, cta_btn_h = info_box_w - 70, 70
        cta_btn_x, cta_btn_y = info_box_x + 35, info_box_y + info_box_h - 90
        
        draw.rounded_rectangle(
            [(cta_btn_x, cta_btn_y), (cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h)],
            radius=35,
            fill=(16, 185, 129),
            outline=(255, 255, 255, 200),
            width=2
        )
        f_cta = get_font(28, bold=True)
        draw_centered_text(draw, (cta_btn_x, cta_btn_y, cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h), "ĐẶT HÀNG & GIAO TẬN NƠI", f_cta, (255, 255, 255))

    # =========================================================================
    # TEMPLATE 2: JUICE BAR & SMOOTHIE (NƯỚC ÉP TƯƠI MÁT & HEALTHY DRINK)
    # =========================================================================
    elif template == "juice":
        bg_img = Image.new("RGBA", (W, H), (255, 126, 95, 255))
        bg_draw = ImageDraw.Draw(bg_img)
        for y in range(H):
            ratio = y / H
            r = int(255 * (1 - ratio) + 254 * ratio)
            g = int(94 * (1 - ratio) + 180 * ratio)
            b = int(98 * (1 - ratio) + 123 * ratio)
            bg_draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

        bg_ratio = max(W / orig.width, H / orig.height)
        bg_w, bg_h = int(orig.width * bg_ratio), int(orig.height * bg_ratio)
        orig_blur = orig.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        orig_blur = orig_blur.crop(((bg_w - W) // 2, (bg_h - H) // 2, (bg_w - W) // 2 + W, (bg_h - H) // 2 + H))
        orig_blur = orig_blur.filter(ImageFilter.GaussianBlur(radius=45))
        orig_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        orig_overlay.paste(orig_blur, (0, 0))
        
        dark_tint = Image.new("RGBA", (W, H), (30, 15, 10, 120))
        bg_img = Image.alpha_composite(bg_img, dark_tint)
        story.paste(bg_img, (0, 0))

        draw = ImageDraw.Draw(story)

        badge_w, badge_h = 720, 75
        badge_x, badge_y = (W - badge_w) // 2, 310
        draw.rounded_rectangle(
            [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
            radius=38,
            fill=(255, 255, 255, 245),
            outline=(249, 115, 22, 255),
            width=3
        )
        f_badge = get_font(26, bold=True)
        draw_centered_text(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), "COLD-PRESSED • 100% NGUYÊN CHẤT", f_badge, (194, 65, 12))

        max_cw, max_ch = 940, 790
        scale = min(max_cw / orig.width, max_ch / orig.height)
        cw, ch = int(orig.width * scale), int(orig.height * scale)
        card_img = orig.resize((cw, ch), Image.Resampling.LANCZOS)
        cx = (W - cw) // 2
        cy = 410 + (max_ch - ch) // 2
        draw_rounded_card_with_shadow(story, card_img, (cx, cy), radius=42, shadow_blur=30, shadow_color=(120, 40, 10, 180), border_color=(255, 255, 255, 255), border_width=5)

        info_box_w, info_box_h = 940, 345
        info_box_x, info_box_y = (W - info_box_w) // 2, 1230
        
        info_card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ic_draw = ImageDraw.Draw(info_card)
        ic_draw.rounded_rectangle(
            [(info_box_x, info_box_y), (info_box_x + info_box_w, info_box_y + info_box_h)],
            radius=36,
            fill=(26, 16, 12, 235),
            outline=(251, 146, 60, 200),
            width=3
        )
        story = Image.alpha_composite(story, info_card)
        draw = ImageDraw.Draw(story)

        text_max_w = info_box_w - 70
        hook_lines, f_hook, h_lh = wrap_and_fit_text(draw, hook, text_max_w, 130, initial_size=34, min_size=24, bold=True, serif=False)
        cur_y = info_box_y + 25
        for line in hook_lines:
            draw.text((info_box_x + 35, cur_y), line, fill=(255, 255, 255), font=f_hook)
            cur_y += h_lh

        f_sub = get_font(22, bold=False)
        sub_preview = "Không Thêm Đường • Giàu Vitamin • Tươi Mới Từng Ngày"
        draw.text((info_box_x + 35, cur_y + 8), sub_preview, fill=(254, 215, 170), font=f_sub)

        cta_btn_w, cta_btn_h = info_box_w - 70, 70
        cta_btn_x, cta_btn_y = info_box_x + 35, info_box_y + info_box_h - 90
        
        draw.rounded_rectangle(
            [(cta_btn_x, cta_btn_y), (cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h)],
            radius=35,
            fill=(249, 115, 22),
            outline=(255, 255, 255, 220),
            width=2
        )
        f_cta = get_font(28, bold=True)
        draw_centered_text(draw, (cta_btn_x, cta_btn_y, cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h), "THƯỞNG THỨC NGAY HÔM NAY", f_cta, (255, 255, 255))

    # =========================================================================
    # TEMPLATE 3: GIỜ VÀNG SĂN SALE (FLASH DEAL & SUPERMARKET PROMOTION)
    # =========================================================================
    elif template == "sale":
        bg_img = Image.new("RGBA", (W, H), (153, 27, 27, 255))
        bg_draw = ImageDraw.Draw(bg_img)
        for y in range(H):
            ratio = y / H
            r = int(185 * (1 - ratio) + 40 * ratio)
            g = int(28 * (1 - ratio) + 5 * ratio)
            b = int(28 * (1 - ratio) + 5 * ratio)
            bg_draw.line([(0, y), (W, y)], fill=(r, g, b, 255))
        story.paste(bg_img, (0, 0))

        draw = ImageDraw.Draw(story)

        badge_w, badge_h = 720, 75
        badge_x, badge_y = (W - badge_w) // 2, 310
        draw.rounded_rectangle(
            [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
            radius=38,
            fill=(245, 158, 11, 255),
            outline=(255, 255, 255, 255),
            width=3
        )
        f_badge = get_font(26, bold=True)
        draw_centered_text(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), "SIÊU ƯU ĐÃI • GIỜ VÀNG GIÁ SỐC", f_badge, (120, 10, 10))

        max_cw, max_ch = 940, 790
        scale = min(max_cw / orig.width, max_ch / orig.height)
        cw, ch = int(orig.width * scale), int(orig.height * scale)
        card_img = orig.resize((cw, ch), Image.Resampling.LANCZOS)
        cx = (W - cw) // 2
        cy = 410 + (max_ch - ch) // 2
        draw_rounded_card_with_shadow(story, card_img, (cx, cy), radius=38, shadow_blur=30, shadow_color=(0, 0, 0, 200), border_color=(254, 240, 138, 255), border_width=5)

        # Floating Hot Deal Badge Sticker
        sticker_w, sticker_h = 240, 60
        sticker_x = cx + cw - sticker_w - 20
        sticker_y = cy + 20
        draw.rounded_rectangle(
            [(sticker_x, sticker_y), (sticker_x + sticker_w, sticker_y + sticker_h)],
            radius=30,
            fill=(220, 38, 38, 250),
            outline=(255, 255, 255, 255),
            width=3
        )
        f_stk = get_font(22, bold=True)
        draw_centered_text(draw, (sticker_x, sticker_y, sticker_x + sticker_w, sticker_y + sticker_h), "DEAL HOT", f_stk, (255, 255, 255))

        info_box_w, info_box_h = 940, 345
        info_box_x, info_box_y = (W - info_box_w) // 2, 1230
        
        info_card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ic_draw = ImageDraw.Draw(info_card)
        ic_draw.rounded_rectangle(
            [(info_box_x, info_box_y), (info_box_x + info_box_w, info_box_y + info_box_h)],
            radius=36,
            fill=(20, 5, 5, 245),
            outline=(245, 158, 11, 220),
            width=3
        )
        story = Image.alpha_composite(story, info_card)
        draw = ImageDraw.Draw(story)

        text_max_w = info_box_w - 70
        hook_lines, f_hook, h_lh = wrap_and_fit_text(draw, hook, text_max_w, 130, initial_size=34, min_size=24, bold=True)
        cur_y = info_box_y + 25
        for line in hook_lines:
            draw.text((info_box_x + 35, cur_y), line, fill=(255, 255, 255), font=f_hook)
            cur_y += h_lh

        f_sub = get_font(22, bold=False)
        sub_preview = "Số Lượng Có Hạn • Áp Dụng Khi Đặt Hàng Trực Tuyến"
        draw.text((info_box_x + 35, cur_y + 8), sub_preview, fill=(253, 230, 138), font=f_sub)

        cta_btn_w, cta_btn_h = info_box_w - 70, 70
        cta_btn_x, cta_btn_y = info_box_x + 35, info_box_y + info_box_h - 90
        
        draw.rounded_rectangle(
            [(cta_btn_x, cta_btn_y), (cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h)],
            radius=35,
            fill=(245, 158, 11),
            outline=(255, 255, 255, 220),
            width=2
        )
        f_cta = get_font(28, bold=True)
        draw_centered_text(draw, (cta_btn_x, cta_btn_y, cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h), "SĂN DEAL NGAY KẺO LỠ", f_cta, (120, 10, 10))

    # =========================================================================
    # TEMPLATE 4: TẠP CHÍ ẨM THỰC (EDITORIAL GOURMET & KINFOLK)
    # =========================================================================
    elif template in ["minimal", "magazine"]:
        bg_ratio = max(W / orig.width, H / orig.height)
        bg_w, bg_h = int(orig.width * bg_ratio), int(orig.height * bg_ratio)
        bg_img = orig.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        bg_img = bg_img.crop(((bg_w - W) // 2, (bg_h - H) // 2, (bg_w - W) // 2 + W, (bg_h - H) // 2 + H))
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=50))
        
        tint = Image.new("RGBA", (W, H), (15, 23, 42, 210))
        bg_img = Image.alpha_composite(bg_img, tint)
        story.paste(bg_img, (0, 0))

        draw = ImageDraw.Draw(story)

        f_pub = get_font(24, bold=True, serif=True)
        draw.text((80, 320), "ROOTS GOURMET SELECTION", fill=(226, 232, 240), font=f_pub)
        
        f_issue = get_font(18, bold=False)
        draw.text((80, 355), "SPECIAL DAILY EDITION • ORGANIC LIVING", fill=(148, 163, 184), font=f_issue)

        draw.line([(80, 390), (W - 80, 390)], fill=(148, 163, 184, 120), width=1)

        max_cw, max_ch = 920, 780
        scale = min(max_cw / orig.width, max_ch / orig.height)
        cw, ch = int(orig.width * scale), int(orig.height * scale)
        card_img = orig.resize((cw, ch), Image.Resampling.LANCZOS)
        cx = (W - cw) // 2
        cy = 420 + (max_ch - ch) // 2
        draw_rounded_card_with_shadow(story, card_img, (cx, cy), radius=28, shadow_blur=32, shadow_color=(0, 0, 0, 180), border_color=(255, 255, 255, 240), border_width=3)

        info_box_w, info_box_h = 920, 345
        info_box_x, info_box_y = (W - info_box_w) // 2, 1230
        
        info_card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ic_draw = ImageDraw.Draw(info_card)
        ic_draw.rounded_rectangle(
            [(info_box_x, info_box_y), (info_box_x + info_box_w, info_box_y + info_box_h)],
            radius=28,
            fill=(30, 41, 59, 230),
            outline=(148, 163, 184, 120),
            width=2
        )
        story = Image.alpha_composite(story, info_card)
        draw = ImageDraw.Draw(story)

        text_max_w = info_box_w - 70
        hook_lines, f_hook, h_lh = wrap_and_fit_text(draw, hook, text_max_w, 130, initial_size=34, min_size=24, bold=True, serif=True)
        cur_y = info_box_y + 25
        for line in hook_lines:
            draw.text((info_box_x + 35, cur_y), line, fill=(255, 255, 255), font=f_hook)
            cur_y += h_lh

        f_sub = get_font(20, bold=False)
        sub_preview = "Hương vị tinh tuyển • Nâng tầm trải nghiệm ẩm thực sống khỏe"
        draw.text((info_box_x + 35, cur_y + 8), sub_preview, fill=(203, 213, 225), font=f_sub)

        cta_btn_w, cta_btn_h = info_box_w - 70, 68
        cta_btn_x, cta_btn_y = info_box_x + 35, info_box_y + info_box_h - 88
        draw.rounded_rectangle(
            [(cta_btn_x, cta_btn_y), (cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h)],
            radius=20,
            fill=(248, 250, 252),
            outline=(203, 213, 225, 255),
            width=2
        )
        f_cta = get_font(26, bold=True)
        draw_centered_text(draw, (cta_btn_x, cta_btn_y, cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h), "KHÁM PHÁ THỰC ĐƠN", f_cta, (15, 23, 42))

    # =========================================================================
    # TEMPLATE 5: POLAROID REVIEW & BEST SELLER (GÓC REVIEW & SẢN PHẨM HOT)
    # =========================================================================
    elif template == "polaroid":
        bg_ratio = max(W / orig.width, H / orig.height)
        bg_w, bg_h = int(orig.width * bg_ratio), int(orig.height * bg_ratio)
        bg_img = orig.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        bg_img = bg_img.crop(((bg_w - W) // 2, (bg_h - H) // 2, (bg_w - W) // 2 + W, (bg_h - H) // 2 + H))
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=40))
        
        warm_overlay = Image.new("RGBA", (W, H), (40, 25, 20, 160))
        bg_img = Image.alpha_composite(bg_img, warm_overlay)
        story.paste(bg_img, (0, 0))

        draw = ImageDraw.Draw(story)

        # Top 5-Star Banner
        badge_w, badge_h = 720, 75
        badge_x, badge_y = (W - badge_w) // 2, 310
        draw.rounded_rectangle(
            [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
            radius=38,
            fill=(255, 251, 235, 250),
            outline=(245, 158, 11, 255),
            width=3
        )
        
        # Draw 5 crisp golden vector stars
        start_star_x = badge_x + 50
        for s_idx in range(5):
            draw_star(draw, start_star_x + s_idx * 28, badge_y + 37, 11, 5, fill=(245, 158, 11))
            
        f_badge = get_font(24, bold=True)
        draw.text((start_star_x + 155, badge_y + 22), "SẢN PHẨM BÁN CHẠY NHẤT", fill=(180, 83, 9), font=f_badge)

        pol_w, pol_h = 860, 810
        pol_x = (W - pol_w) // 2
        pol_y = 410

        tape_w, tape_h = 240, 48
        tape_x = (W - tape_w) // 2
        tape_y = pol_y - 20
        draw.rounded_rectangle(
            [(tape_x, tape_y), (tape_x + tape_w, tape_y + tape_h)],
            radius=10,
            fill=(254, 243, 199, 210),
            outline=(252, 211, 77, 240),
            width=2
        )

        pad = 30
        pol_shadow = Image.new("RGBA", (pol_w + pad * 2, pol_h + pad * 2), (0, 0, 0, 0))
        ps_draw = ImageDraw.Draw(pol_shadow)
        ps_draw.rounded_rectangle([(pad, pad), (pol_w + pad, pol_h + pad)], radius=20, fill=(0, 0, 0, 160))
        pol_shadow = pol_shadow.filter(ImageFilter.GaussianBlur(24))
        story.paste(pol_shadow, (pol_x - pad, pol_y - pad + 14), pol_shadow)

        pol_card = Image.new("RGBA", (pol_w, pol_h), (255, 255, 255, 255))
        pc_draw = ImageDraw.Draw(pol_card)

        photo_margin = 35
        photo_w = pol_w - (photo_margin * 2)
        photo_h = pol_h - 130
        scale = max(photo_w / orig.width, photo_h / orig.height)
        pw, ph = int(orig.width * scale), int(orig.height * scale)
        p_img = orig.resize((pw, ph), Image.Resampling.LANCZOS)
        p_img = p_img.crop(((pw - photo_w) // 2, (ph - photo_h) // 2, (pw - photo_w) // 2 + photo_w, (ph - photo_h) // 2 + photo_h))
        pol_card.paste(p_img, (photo_margin, photo_margin))

        f_chin = get_font(26, bold=True, serif=True)
        draw_centered_text(pc_draw, (0, photo_margin + photo_h, pol_w, pol_h), "ROOTS ORGANIC • VERIFIED QUALITY", f_chin, (71, 85, 105))
        
        story.paste(pol_card, (pol_x, pol_y))
        draw = ImageDraw.Draw(story)

        info_box_w, info_box_h = 920, 325
        info_box_x, info_box_y = (W - info_box_w) // 2, 1250
        
        info_card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ic_draw = ImageDraw.Draw(info_card)
        ic_draw.rounded_rectangle(
            [(info_box_x, info_box_y), (info_box_x + info_box_w, info_box_y + info_box_h)],
            radius=34,
            fill=(28, 25, 23, 240),
            outline=(245, 158, 11, 160),
            width=2
        )
        story = Image.alpha_composite(story, info_card)
        draw = ImageDraw.Draw(story)

        text_max_w = info_box_w - 70
        hook_lines, f_hook, h_lh = wrap_and_fit_text(draw, hook, text_max_w, 110, initial_size=32, min_size=24, bold=True)
        cur_y = info_box_y + 20
        for line in hook_lines:
            draw.text((info_box_x + 35, cur_y), line, fill=(255, 255, 255), font=f_hook)
            cur_y += h_lh

        f_sub = get_font(20, bold=False)
        sub_preview = "Khách hàng đánh giá 5 sao cho chất lượng & độ tươi sạch"
        draw.text((info_box_x + 35, cur_y + 6), sub_preview, fill=(253, 230, 138), font=f_sub)

        cta_btn_w, cta_btn_h = info_box_w - 70, 68
        cta_btn_x, cta_btn_y = info_box_x + 35, info_box_y + info_box_h - 86
        draw.rounded_rectangle(
            [(cta_btn_x, cta_btn_y), (cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h)],
            radius=34,
            fill=(245, 158, 11),
            outline=(255, 255, 255, 220),
            width=2
        )
        f_cta = get_font(26, bold=True)
        draw_centered_text(draw, (cta_btn_x, cta_btn_y, cta_btn_x + cta_btn_w, cta_btn_y + cta_btn_h), "XEM THÊM & ĐẶT HÀNG", f_cta, (69, 26, 3))

    out_filename = f"story_{uuid.uuid4().hex}.jpg"
    out_path = UPLOAD_DIR / out_filename
    story_rgb = story.convert("RGB")
    story_rgb.save(out_path, format="JPEG", quality=95, optimize=True)
    return out_filename
