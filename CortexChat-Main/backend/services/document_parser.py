"""
backend/services/document_parser.py — Multi-format Document Text Extractor.

This service abstracts away the complexities of reading various file formats.
It exposes a unified `extract_text` function that routes the raw byte stream to the 
appropriate parser based on the file extension.

Supported Formats & Engines:
  - PDF: PyMuPDF (fitz) — Extremely fast, robust C-binding, no external Poppler dependency.
  - DOCX: python-docx — Native XML traversal for Word documents.
  - TXT: Built-in Python decoders (UTF-8 with Latin-1 fallback).
  - Images (PNG/JPG): pytesseract — Optical Character Recognition (requires Tesseract binary).
"""

import io


def extract_text(file_bytes: bytes, file_ext: str) -> str:
    """
    Dispatch to the correct parser based on file extension.

    Args:
        file_bytes: Raw file content as bytes.
        file_ext:   Lowercase extension without dot ('pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg').

    Returns:
        Extracted plain text. Empty string if nothing could be parsed.
    """
    ext = file_ext.lower().lstrip(".")

    if ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext == "docx":
        return _extract_docx(file_bytes)
    elif ext == "txt":
        return _extract_txt(file_bytes)
    elif ext in ("png", "jpg", "jpeg"):
        return _extract_image(file_bytes)
    else:
        return ""


# ─── PDF ─────────────────────────────────────────────────────────────────────

def _extract_pdf(data: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz)."""
    try:
        # pyrefly: ignore [missing-import]
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return _clean(" ".join(pages))
    except Exception as exc:
        print(f"[Parser] PDF extraction failed: {exc}")
        return ""


# ─── DOCX ────────────────────────────────────────────────────────────────────

def _extract_docx(data: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs]
        return _clean("\n".join(paragraphs))
    except Exception as exc:
        print(f"[Parser] DOCX extraction failed: {exc}")
        return ""


# ─── TXT ─────────────────────────────────────────────────────────────────────

def _extract_txt(data: bytes) -> str:
    """Decode a plain-text file, falling back to latin-1 on UTF-8 errors."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    
    # Strip null bytes which can crash some APIs or DBs
    return _clean(text.replace("\u0000", ""))


# ─── Image / OCR ─────────────────────────────────────────────────────────────

def _extract_image(data: bytes) -> str:
    """Run Tesseract OCR on an image file."""
    try:
        from PIL import Image
        import pytesseract

        image = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(image)
        return _clean(text)
    except Exception as exc:
        print(f"[Parser] OCR extraction failed: {exc}")
        return ""


# ─── Utility ─────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    import re

    # Replace 3+ consecutive newlines with double newline
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Replace tabs with spaces
    text = text.replace("\t", " ")
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
