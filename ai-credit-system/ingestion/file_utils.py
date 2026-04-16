"""File rendering utilities: PDF/image/XLSX to PIL images."""

from __future__ import annotations

import base64
import io

import openpyxl
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw

CLASSIFIER_DPI = 72
CLASSIFIER_SIZE = (800, 1000)
EXTRACTOR_DPI = 150
EXTRACTOR_SIZE = (1400, 1900)


def pdf_to_images(file_bytes: bytes, dpi: int, max_pages: int | None = None) -> list[Image.Image]:
    imgs = convert_from_bytes(file_bytes, dpi=dpi)
    return imgs[:max_pages] if max_pages else imgs


def resize_image(img: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    img.thumbnail(max_size, Image.LANCZOS)
    return img


def image_to_b64(img: Image.Image, fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def image_file_to_pil(file_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(file_bytes))


def xlsx_to_images(file_bytes: bytes) -> list[Image.Image]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    lines = []
    for row in ws.iter_rows(values_only=True):
        lines.append(" | ".join(str(c) if c is not None else "" for c in row))
    text = "\n".join(lines[:80])
    img = Image.new("RGB", (1200, 1600), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill="black")
    return [img]


def prepare_pages_for_classifier(file_bytes: bytes, content_type: str) -> list[Image.Image]:
    """Low-res, max 2 pages for classification."""
    if content_type == "application/pdf":
        imgs = pdf_to_images(file_bytes, CLASSIFIER_DPI, max_pages=2)
    elif content_type in ("image/jpeg", "image/png"):
        imgs = [image_file_to_pil(file_bytes)]
    elif "spreadsheet" in content_type:
        imgs = xlsx_to_images(file_bytes)
    else:
        imgs = [image_file_to_pil(file_bytes)]
    return [resize_image(img, CLASSIFIER_SIZE) for img in imgs]


def prepare_pages_for_extractor(file_bytes: bytes, content_type: str) -> list[Image.Image]:
    """Mid-res, all pages for extraction."""
    if content_type == "application/pdf":
        imgs = pdf_to_images(file_bytes, EXTRACTOR_DPI)
    elif content_type in ("image/jpeg", "image/png"):
        imgs = [image_file_to_pil(file_bytes)]
    elif "spreadsheet" in content_type:
        imgs = xlsx_to_images(file_bytes)
    else:
        imgs = [image_file_to_pil(file_bytes)]
    return [resize_image(img, EXTRACTOR_SIZE) for img in imgs]
