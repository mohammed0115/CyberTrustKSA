from __future__ import annotations

import logging
import re

from django.conf import settings

logger = logging.getLogger("ai_engine")

MAX_TEXT_CHARS = getattr(settings, "AI_TEXT_MAX_CHARS", 50000)


def detect_file_type(path: str | None = None, filename: str | None = None) -> str:
    name = filename or path or ""
    ext = name.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return "PDF"
    if ext == "docx":
        return "DOCX"
    if ext in {"png", "jpg", "jpeg"}:
        return "IMG"
    return "OTHER"


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate_text(text: str) -> str:
    if not text:
        return ""
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[:MAX_TEXT_CHARS]


def extract_text_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for PDF extraction") from exc

    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return _truncate_text(_normalize_text("\n".join(parts)))


def extract_text_docx(path: str) -> str:
    try:
        import docx
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("python-docx is required for DOCX extraction") from exc

    doc = docx.Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    return _truncate_text(_normalize_text(text))


def extract_text_image(path: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception:
        logger.warning("OCR dependencies are not installed.")
        return ""

    tesseract_cmd = getattr(settings, "TESSERACT_CMD", "")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    lang = getattr(settings, "TESSERACT_LANG", "eng")
    try:
        text = pytesseract.image_to_string(Image.open(path), lang=lang)
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""
    return _truncate_text(_normalize_text(text))


def extract_text_from_pdf(path: str) -> str:
    return extract_text_pdf(path)


def extract_text_from_docx(path: str) -> str:
    return extract_text_docx(path)


def extract_text_from_image(path: str) -> str:
    return extract_text_image(path)
