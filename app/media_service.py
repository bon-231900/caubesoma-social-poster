import os
import hashlib
import uuid
from pathlib import Path
from PIL import Image
from typing import Dict, Any, List
from app.config import UPLOAD_DIR
from app.database import create_media_item, get_media_items, get_media_by_hash, update_media_tags, delete_media_item

THUMB_DIR = UPLOAD_DIR / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

def compute_file_hash(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def create_thumbnail(source_path: Path, thumb_size: int = 250) -> str:
    """Generates lightweight 250x250 square thumbnail for ultra-fast media library browsing."""
    thumb_name = f"thumb_{source_path.name}"
    thumb_path = THUMB_DIR / thumb_name
    if thumb_path.exists():
        return thumb_name
    try:
        with Image.open(source_path) as img:
            img_rgba = img.convert("RGB")
            # Fit crop center
            w, h = img_rgba.size
            min_side = min(w, h)
            left = (w - min_side) // 2
            top = (h - min_side) // 2
            cropped = img_rgba.crop((left, top, left + min_side, top + min_side))
            resized = cropped.resize((thumb_size, thumb_size), Image.Resampling.LANCZOS)
            resized.save(thumb_path, format="JPEG", quality=85, optimize=True)
            return thumb_name
    except Exception as e:
        return source_path.name

def register_media_file(filename: str, original_name: str = "", tags: List[str] = None) -> Dict[str, Any]:
    file_path = UPLOAD_DIR / filename
    if not file_path.is_file():
        return {}
    
    file_size = file_path.stat().st_size
    file_hash = compute_file_hash(file_path)
    
    # Check duplicate
    existing = get_media_by_hash(file_hash)
    if existing:
        return existing

    width, height = 0, 0
    mime = "image/jpeg"
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            mime = f"image/{img.format.lower()}" if img.format else "image/jpeg"
    except Exception:
        pass

    # Auto generate thumbnail
    create_thumbnail(file_path, thumb_size=250)

    create_media_item(
        filename=filename,
        original_name=original_name or filename,
        file_hash=file_hash,
        mime_type=mime,
        file_size=file_size,
        width=width,
        height=height,
        tags=tags or ["Tất cả"]
    )
    return {
        "filename": filename,
        "original_name": original_name or filename,
        "file_hash": file_hash,
        "file_size": file_size,
        "width": width,
        "height": height,
        "tags": tags or ["Tất cả"]
    }
