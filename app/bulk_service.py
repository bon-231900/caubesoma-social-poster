import io
import csv
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from app.database import create_post
from app.time_utils import normalize_schedule

COLUMNS = [
    ("title", "Tiêu đề / Chiến dịch (title)", 25),
    ("fb_caption", "Nội dung Facebook (fb_caption)", 40),
    ("ig_caption", "Nội dung Instagram (ig_caption)", 35),
    ("google_caption", "Nội dung Google Maps (google_caption)", 35),
    ("google_action_type", "Nút bấm Google (LEARN_MORE / ORDER / CALL / BOOK / NONE)", 22),
    ("google_action_url", "Link nút Google (google_action_url)", 30),
    ("images", "Hình ảnh (images - cách nhau dấu phẩy)", 32),
    ("target_fb", "Đăng FB (1/0)", 14),
    ("target_ig", "Đăng IG (1/0)", 14),
    ("target_story", "Đăng Story 9:16 (1/0)", 18),
    ("target_google", "Đăng Google (1/0)", 16),
    ("scheduled_time", "Ngày giờ đăng (YYYY-MM-DD HH:mm)", 25)
]

def map_action_type(val: str) -> str:
    if not val:
        return "LEARN_MORE"
    v = str(val).strip().upper()
    valid = ["LEARN_MORE", "ORDER", "BOOK", "SHOP", "SIGN_UP", "CALL", "NONE"]
    if v in valid:
        return v
    if "ĐẶT" in v or "ORDER" in v or "MUA" in v:
        return "ORDER"
    if "GỌI" in v or "CALL" in v:
        return "CALL"
    if "ĐẶT CHỖ" in v or "BOOK" in v:
        return "BOOK"
    if "ĐĂNG KÝ" in v or "SIGN" in v:
        return "SIGN_UP"
    if "KHÔNG" in v or "NONE" in v:
        return "NONE"
    return "LEARN_MORE"

def generate_bulk_excel_template() -> io.BytesIO:
    """Tạo file mẫu Excel .xlsx chuyên nghiệp với style đẹp và dữ liệu mẫu chuẩn."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DanhSachDangBai"
    ws.views.sheetView[0].showGridLines = True

    # Palette
    header_fill = PatternFill(start_color="15803D", end_color="15803D", fill_type="solid") # Emerald 700
    sub_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # Emerald 100
    sample_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid") # Slate 50
    
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    desc_font = Font(name="Segoe UI", size=9, italic=True, color="166534")
    data_font = Font(name="Segoe UI", size=10, color="0F172A")
    note_font = Font(name="Segoe UI", size=10, color="64748B")

    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0")
    )

    # 1. Row 1: Header Titles
    for col_idx, (col_key, col_title, col_width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width

    ws.row_dimensions[1].height = 28

    # 2. Row 2: Description / Guide Row
    guides = [
        "Tên bài viết để quản lý nội bộ",
        "Nội dung bài viết Facebook (Hỗ trợ icon, xuống dòng)",
        "Nội dung Instagram (Kèm hashtags)",
        "Nội dung Google Business Profile",
        "Loại nút CTA: LEARN_MORE / ORDER / CALL / BOOK / SHOP / SIGN_UP / NONE",
        "Link landing page khi khách bấm nút CTA (Bỏ trống nếu là CALL/NONE)",
        "Tên file ảnh trong thư viện hoặc URL ảnh (Cách nhau bằng dấu phẩy)",
        "1 = Đăng FB, 0 = Không",
        "1 = Đăng IG Feed, 0 = Không",
        "1 = Đăng Story 9:16, 0 = Không",
        "1 = Đăng Google Maps, 0 = Không",
        "Định dạng: YYYY-MM-DD HH:mm (Ví dụ: 2026-08-30 09:00, bỏ trống = Đăng ngay)"
    ]
    for col_idx, guide in enumerate(guides, start=1):
        cell = ws.cell(row=2, column=col_idx, value=guide)
        cell.font = desc_font
        cell.fill = sub_fill
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = thin_border

    ws.row_dimensions[2].height = 36

    # 3. Row 3-5: Sample Data
    now = datetime.now()
    sample_rows = [
        [
            "Dầu Oliu Extra Virgin Thượng Hạng",
            "🌿 DẦU OLIU EXTRA VIRGIN HỮU CƠ - BẢO VỆ SỨC KHỎE TRỌN VẸN CHO CẢ GIA ĐÌNH!\\n\\nĐược chiết xuất từ những quả oliu hữu cơ tươi ngon nhất qua phương pháp ép lạnh tự nhiên.\\n\\n🛒 Đặt hàng tại ROOTS: https://roots.vn\\n📞 Hotline: 0868 472 236\\n#rootsorganic #organicfood #dauoliu #eatclean",
            "🌿 Dầu Oliu Extra Virgin Hữu Cơ Ép Lạnh - Lựa chọn hoàn hảo cho món salad thanh lành mỗi ngày! ✨\\n\\n#rootsorganic #healthyfood #eatclean #organicoil #detox",
            "Dầu Oliu Extra Virgin Hữu Cơ Ép Lạnh Thượng Hạng tại ROOTS Store. Đặt hàng ngay hôm nay!",
            "ORDER",
            "https://roots.vn/san-pham/dau-oliu-extra-virgin",
            "roots_creative_16_9_a86d16ecfef6.jpg",
            1, 1, 1, 1,
            (now + timedelta(days=1)).strftime("%Y-%m-%d 09:00")
        ],
        [
            "Nước Ép Cần Tây & Táo Xanh Detox",
            "🍹 THANH LỌC CƠ THỂ MỖI NGÀY CÙNG JUICE BAR ROOTS!\\n\\nNước ép Cần tây & Táo xanh nguyên chất 100% không thêm đường hay chất bảo quản.\\n\\n📍 232-234 Võ Thị Sáu, P. Võ Thị Sáu, Q.3, TP.HCM\\n#rootsjuice #detox #coldpressed #healthy",
            "Khởi đầu ngày mới tràn đầy năng lượng cùng Juice Bar ROOTS 🍹 100% Cold-pressed tươi mới!\\n\\n#rootsorganic #detoxjuice #cleanse #healthylifestyle",
            "Thanh lọc cơ thể với Nước ép Cần Tây & Táo Xanh Detox tại ROOTS Juice Bar!",
            "LEARN_MORE",
            "https://roots.vn/juice-bar",
            "roots_creative_16_9_a86d16ecfef6.jpg",
            1, 1, 1, 1,
            (now + timedelta(days=2)).strftime("%Y-%m-%d 15:30")
        ]
    ]

    for row_idx, r_data in enumerate(sample_rows, start=3):
        for col_idx, val in enumerate(r_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = sample_fill
            cell.alignment = Alignment(horizontal="center" if isinstance(val, int) else "left", vertical="top", wrap_text=True)
            cell.border = thin_border
        ws.row_dimensions[row_idx].height = 65

    # Sheet 2: Hướng dẫn chi tiết
    ws2 = wb.create_sheet(title="HuongDanChiTiet")
    ws2.views.sheetView[0].showGridLines = True
    ws2.column_dimensions["A"].width = 25
    ws2.column_dimensions["B"].width = 60
    
    ws2.cell(row=1, column=1, value="Cột").font = header_font
    ws2.cell(row=1, column=1).fill = header_fill
    ws2.cell(row=1, column=2, value="Quy định và Giá trị hợp lệ").font = header_font
    ws2.cell(row=1, column=2).fill = header_fill

    field_docs = [
        ("title", "Tên phân loại hoặc tiêu đề chiến dịch để hiển thị trong lịch quản lý."),
        ("fb_caption", "Nội dung đăng lên Facebook. Cho phép định dạng link, icon và nhiều dòng."),
        ("ig_caption", "Nội dung đăng lên Instagram Feed. Nên kèm các hashtag (#rootsorganic, #eatclean)."),
        ("google_caption", "Nội dung hiển thị trên bài đăng Google Maps & Google Search."),
        ("google_action_type", "Loại nút CTA trên Google: LEARN_MORE (Tìm hiểu thêm), ORDER (Đặt hàng), CALL (Gọi ngay), BOOK (Đặt bàn), NONE (Không nút)."),
        ("google_action_url", "Đường dẫn website khi khách bấm vào nút trên Google Maps (Không áp dụng nếu chọn CALL hoặc NONE)."),
        ("images", "Tên file ảnh đã tải lên Thư viện (Ví dụ: sanpham1.jpg) hoặc URL ảnh trực tiếp."),
        ("target_fb", "Nhập 1 để xuất bản lên Facebook, nhập 0 để bỏ qua."),
        ("target_ig", "Nhập 1 để xuất bản lên Instagram, nhập 0 để bỏ qua."),
        ("target_story", "Nhập 1 để tự động thiết kế và đăng lên Story 9:16."),
        ("target_google", "Nhập 1 để đăng lên Google Maps."),
        ("scheduled_time", "Thời gian hẹn giờ đăng: YYYY-MM-DD HH:mm (Ví dụ: 2026-08-30 09:00). Bỏ trống = Đăng ngay.")
    ]

    for idx, (col_k, col_doc) in enumerate(field_docs, start=2):
        c1 = ws2.cell(row=idx, column=1, value=col_k)
        c1.font = Font(name="Segoe UI", size=10, bold=True, color="15803D")
        c1.border = thin_border
        c2 = ws2.cell(row=idx, column=2, value=col_doc)
        c2.font = data_font
        c2.border = thin_border
        ws2.row_dimensions[idx].height = 24

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def parse_bulk_file(content: bytes, filename: str) -> list:
    """Đọc và trích xuất dữ liệu bài viết từ file Excel (.xlsx, .xls) hoặc CSV."""
    posts = []
    fname_lower = filename.lower()
    
    if fname_lower.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return []
        
        # Bỏ qua header
        header = rows[0]
        start_row = 1
        # Nếu row 2 là hàng hướng dẫn (chứa từ 'Hỗ trợ' hoặc 'hướng dẫn')
        if len(rows) > 2 and ("Hỗ trợ" in "".join(rows[1]) or "Nội dung" in "".join(rows[1])):
            start_row = 2

        for r in rows[start_row:]:
            if not any(r):
                continue
            title = r[0].strip() if len(r) > 0 else ""
            fb_caption = r[1].strip() if len(r) > 1 else ""
            ig_caption = r[2].strip() if len(r) > 2 else ""
            google_caption = r[3].strip() if len(r) > 3 else ""
            google_action_type = map_action_type(r[4].strip() if len(r) > 4 else "")
            google_action_url = r[5].strip() if len(r) > 5 else ""
            
            raw_images = r[6].strip() if len(r) > 6 else ""
            images = [img.strip() for img in raw_images.replace(";", ",").split(",") if img.strip()]
            
            target_fb = str(r[7]).strip() in ["1", "true", "True", "x", "X"] if len(r) > 7 else True
            target_ig = str(r[8]).strip() in ["1", "true", "True", "x", "X"] if len(r) > 8 else True
            target_story = str(r[9]).strip() in ["1", "true", "True", "x", "X"] if len(r) > 9 else False
            target_google = str(r[10]).strip() in ["1", "true", "True", "x", "X"] if len(r) > 10 else False
            
            raw_time = r[11].strip() if len(r) > 11 else ""
            scheduled_time = normalize_schedule(raw_time) if raw_time else ""

            if fb_caption or ig_caption or google_caption:
                posts.append({
                    "title": title or (fb_caption or ig_caption)[:40],
                    "fb_caption": fb_caption,
                    "ig_caption": ig_caption,
                    "google_caption": google_caption,
                    "google_action_type": google_action_type,
                    "google_action_url": google_action_url,
                    "images": images,
                    "target_fb": target_fb,
                    "target_ig": target_ig,
                    "target_story": target_story,
                    "target_google": target_google,
                    "scheduled_time": scheduled_time
                })

    else:
        # Excel .xlsx / .xls
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return []
        
        start_row = 1
        if len(rows) > 2:
            r2_str = "".join([str(c or "") for c in rows[1]])
            if "Nội dung" in r2_str or "Tên" in r2_str or "Định dạng" in r2_str or "Loại nút" in r2_str:
                start_row = 2

        for row in rows[start_row:]:
            if not any(row):
                continue
            title = str(row[0] or "").strip()
            fb_caption = str(row[1] or "").strip()
            ig_caption = str(row[2] or "").strip()
            google_caption = str(row[3] or "").strip()
            google_action_type = map_action_type(str(row[4] or ""))
            google_action_url = str(row[5] or "").strip()
            
            raw_images = str(row[6] or "").strip()
            images = [img.strip() for img in raw_images.replace(";", ",").split(",") if img.strip()]
            
            # Helper for bool
            def parse_bool(v, default=True):
                if v is None or str(v).strip() == "":
                    return default
                s = str(v).strip().lower()
                return s in ["1", "true", "x", "yes", "có"]

            target_fb = parse_bool(row[7] if len(row) > 7 else None, True)
            target_ig = parse_bool(row[8] if len(row) > 8 else None, True)
            target_story = parse_bool(row[9] if len(row) > 9 else None, False)
            target_google = parse_bool(row[10] if len(row) > 10 else None, False)

            # Fix fallback action url if missing
            if target_google and google_action_type in ["ORDER", "LEARN_MORE", "SHOP", "BOOK", "SIGN_UP"] and not google_action_url:
                google_action_url = "https://roots.vn"

            raw_time = str(row[11] or "").strip() if len(row) > 11 else ""
            scheduled_time = ""
            if raw_time and raw_time != "None":
                scheduled_time = normalize_schedule(raw_time)

            if fb_caption or ig_caption or google_caption:
                posts.append({
                    "title": title or (fb_caption or ig_caption)[:40],
                    "fb_caption": fb_caption,
                    "ig_caption": ig_caption,
                    "google_caption": google_caption,
                    "google_action_type": google_action_type,
                    "google_action_url": google_action_url,
                    "images": images,
                    "target_fb": target_fb,
                    "target_ig": target_ig,
                    "target_story": target_story,
                    "target_google": target_google,
                    "scheduled_time": scheduled_time
                })

    return posts

def import_bulk_posts(posts: list, user_role: str = "admin") -> dict:
    """Lưu danh sách bài viết từ Bulk Import vào cơ sở dữ liệu và lên lịch."""
    created_ids = []
    status_default = "pending_approval" if user_role == "staff" else "scheduled"
    
    for p in posts:
        sch_time = p.get("scheduled_time")
        post_status = status_default if sch_time else ("pending_approval" if user_role == "staff" else "draft")
        
        post_id = create_post(
            fb_caption=p.get("fb_caption", ""),
            ig_caption=p.get("ig_caption", ""),
            google_caption=p.get("google_caption", ""),
            images=p.get("images", []),
            target_fb=bool(p.get("target_fb", True)),
            target_ig=bool(p.get("target_ig", True)),
            target_story=bool(p.get("target_story", False)),
            target_google=bool(p.get("target_google", False)),
            google_action_type=p.get("google_action_type", "LEARN_MORE"),
            google_action_url=p.get("google_action_url", ""),
            scheduled_time=sch_time or None,
            status=post_status
        )
        created_ids.append(post_id)

    return {
        "success": True,
        "imported_count": len(created_ids),
        "post_ids": created_ids
    }
