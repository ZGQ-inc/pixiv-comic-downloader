"""
Export utilities for saving reassembled images, PDF, or CBZ/ZIP archives.
"""
import io
import os
import re
import zipfile
from typing import List
from PIL import Image


def sanitize_filename(filename: str) -> str:
    """Removes or replaces invalid Windows filename characters."""
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename).strip()
    return sanitized if sanitized else "comic"


def save_pages_as_images(
    images: List[Image.Image],
    output_dir: str,
    img_format: str = "PNG",
    prefix: str = "page"
) -> List[str]:
    """
    Saves a list of PIL Images to individual image files in output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_paths = []
    ext = img_format.lower()
    if ext == "jpeg":
        ext = "jpg"

    for idx, img in enumerate(images, start=1):
        filename = f"{prefix}_{idx:03d}.{ext}"
        filepath = os.path.join(output_dir, filename)

        if img_format.upper() in ["JPEG", "JPG"] and img.mode in ["RGBA", "P"]:
            img = img.convert("RGB")

        img.save(filepath, format=img_format)
        saved_paths.append(filepath)

    return saved_paths


def export_to_pdf(images: List[Image.Image], output_pdf_path: str) -> str:
    """
    Exports a list of PIL Images as a single multi-page PDF document.
    """
    if not images:
        raise ValueError("No images to export to PDF.")

    rgb_images = []
    for img in images:
        if img.mode != "RGB":
            rgb_images.append(img.convert("RGB"))
        else:
            rgb_images.append(img)

    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    first_image = rgb_images[0]
    rest_images = rgb_images[1:] if len(rgb_images) > 1 else []

    first_image.save(
        output_pdf_path,
        save_all=True,
        append_images=rest_images,
        resolution=100.0
    )
    return output_pdf_path


def export_to_cbz(images: List[Image.Image], output_cbz_path: str, prefix: str = "page") -> str:
    """
    Packages a list of PIL Images into a CBZ comic archive (standard zip format).
    """
    if not images:
        raise ValueError("No images to export to CBZ.")

    os.makedirs(os.path.dirname(os.path.abspath(output_cbz_path)), exist_ok=True)
    with zipfile.ZipFile(output_cbz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, img in enumerate(images, start=1):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"{prefix}_{idx:03d}.png", buf.getvalue())

    return output_cbz_path
