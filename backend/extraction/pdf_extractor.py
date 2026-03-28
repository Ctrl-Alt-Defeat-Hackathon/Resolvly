"""
PDF and image text extraction utilities.

Strategy:
  - Digital PDFs  → pdfplumber (primary) with PyMuPDF fallback
  - Scanned PDFs  → detected when pdfplumber yields no text; flagged for client-side OCR
  - Images        → flagged for client-side Tesseract.js OCR (V1 does not run server-side OCR)
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pdfplumber
import fitz  # PyMuPDF


class DocumentType(str, Enum):
    pdf_digital = "pdf_digital"
    pdf_scanned = "pdf_scanned"     # no selectable text → needs OCR
    image = "image"
    unknown = "unknown"


@dataclass
class ExtractionResult:
    doc_id: str
    doc_type: DocumentType
    text_extracted: str
    ocr_used: bool
    ocr_confidence: float | None   # None when OCR not performed server-side
    page_count: int
    needs_client_ocr: bool         # True → front-end must run Tesseract.js


def _is_image_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}


def _extract_pdf_pdfplumber(data: bytes) -> tuple[str, int]:
    """Extract text from a digital PDF using pdfplumber."""
    text_parts: list[str] = []
    page_count = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            # Also try to extract tables as tab-separated text
            tables = page.extract_tables()
            table_texts = []
            for table in tables:
                for row in table:
                    if row:
                        table_texts.append("\t".join(cell or "" for cell in row))
            if table_texts:
                page_text += "\n" + "\n".join(table_texts)
            text_parts.append(page_text)
    return "\n\n".join(text_parts), page_count


def _extract_pdf_pymupdf(data: bytes) -> tuple[str, int]:
    """Fallback PDF extraction using PyMuPDF."""
    text_parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
        return "\n\n".join(text_parts), len(doc)


def _has_meaningful_text(text: str, min_chars: int = 50) -> bool:
    """Return True if the extracted text is substantive (not just whitespace/junk)."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return len(cleaned) >= min_chars


def extract_document(doc_id: str, filename: str, data: bytes) -> ExtractionResult:
    """
    Main entry point. Detects file type and extracts text.
    Images and scanned PDFs are flagged for client-side OCR.
    """
    if _is_image_file(filename):
        return ExtractionResult(
            doc_id=doc_id,
            doc_type=DocumentType.image,
            text_extracted="",
            ocr_used=False,
            ocr_confidence=None,
            page_count=1,
            needs_client_ocr=True,
        )

    # Assume PDF
    text = ""
    page_count = 0
    ocr_used = False
    extraction_error = None

    try:
        text, page_count = _extract_pdf_pdfplumber(data)
    except Exception as e:
        extraction_error = e

    if not _has_meaningful_text(text):
        # Try PyMuPDF fallback
        try:
            text, page_count = _extract_pdf_pymupdf(data)
        except Exception:
            pass

    if not _has_meaningful_text(text):
        # Scanned PDF — needs OCR
        return ExtractionResult(
            doc_id=doc_id,
            doc_type=DocumentType.pdf_scanned,
            text_extracted="",
            ocr_used=False,
            ocr_confidence=None,
            page_count=page_count or 1,
            needs_client_ocr=True,
        )

    return ExtractionResult(
        doc_id=doc_id,
        doc_type=DocumentType.pdf_digital,
        text_extracted=text,
        ocr_used=ocr_used,
        ocr_confidence=None,
        page_count=page_count,
        needs_client_ocr=False,
    )
