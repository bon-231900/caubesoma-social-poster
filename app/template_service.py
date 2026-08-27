import re
from typing import Dict, Any

DEFAULT_VARIABLES = [
    {"key": "product_name", "label": "Tên sản phẩm", "example": "Nước Ép Bưởi Hồng ROOTS"},
    {"key": "brand", "label": "Thương hiệu", "example": "ROOTS Organic"},
    {"key": "price", "label": "Giá bán", "example": "65,000đ"},
    {"key": "discount", "label": "Mức giảm giá", "example": "(Giảm 20%)"},
    {"key": "origin", "label": "Xuất xứ", "example": "Việt Nam"},
    {"key": "product_url", "label": "Link mua hàng", "example": "https://roots.vn"},
    {"key": "hotline", "label": "Hotline", "example": "028 9999 6666"}
]

def resolve_caption_variables(template_str: str, context: Dict[str, Any]) -> str:
    """
    Replaces {variable_name} tags with actual product context values.
    """
    if not template_str:
        return ""
    
    result = template_str
    for k, v in context.items():
        placeholder = f"{{{k}}}"
        result = result.replace(placeholder, str(v or ""))
    
    # Clean up any leftover unresolved placeholders
    result = re.sub(r"\{[a-zA-Z0-9_]+\}", "", result)
    return result.strip()
