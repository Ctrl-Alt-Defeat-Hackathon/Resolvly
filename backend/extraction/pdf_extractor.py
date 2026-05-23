"""
PDF and image text extraction utilities.

Strategy:
  - Digital PDFs  → pdfplumber (primary) with PyMuPDF fallback
  - Scanned PDFs  → per-page detection; scanned pages are flagged separately from digital pages
  - Images        → flagged for client-side Tesseract.js OCR (server-side via POST /ocr/page)

v2 improvements:
  - Per-page OCR detection instead of whole-document threshold (catches mixed digital+scanned docs)
  - Structured table data preserved in ExtractionResult.tables (not flattened into text)
  - PageMeta per page: text character count, image presence, is_scanned flag
  - has_mixed_content flag when some pages are digital and some are scanned
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pdfplumber
import fitz  # PyMuPDF


class DocumentType(str, Enum):
    pdf_digital = "pdf_digital"
    pdf_scanned = "pdf_scanned"     # no selectable text → needs OCR
    pdf_mixed = "pdf_mixed"         # some pages digital, some scanned
    image = "image"
    unknown = "unknown"


@dataclass
class PageMeta:
    """Per-page extraction metadata."""
    page_number: int          # 1-based
    text_chars: int           # number of non-whitespace characters extracted
    has_images: bool          # page contains embedded images
    is_scanned: bool          # True when text_chars < threshold and images present


@dataclass
class ExtractionResult:
    doc_id: str
    doc_type: DocumentType
    text_extracted: str
    ocr_used: bool
    ocr_confidence: float | None   # None when OCR not performed server-side
    page_count: int
    needs_client_ocr: bool         # True → front-end should run Tesseract.js on this doc
    # v2 additions — default to empty so existing callers are unaffected
    pages_meta: list[PageMeta] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)  # [page][table][row][cell]
    scanned_page_numbers: list[int] = field(default_factory=list)  # 1-based pages needing OCR
    has_mixed_content: bool = False   # True when doc has both digital and scanned pages


_MIN_TEXT_CHARS_PER_PAGE = 30   # pages with fewer chars and images are considered scanned


def _is_image_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}


def _page_has_images(pdf_page: "pdfplumber.page.Page") -> bool:
    """Return True if the pdfplumber page contains embedded image objects."""
    try:
        return bool(pdf_page.images)
    except Exception:
        return False


def _extract_pdf_pdfplumber(data: bytes) -> tuple[str, int, list[PageMeta], list[list[list[str]]]]:
    """
    Extract text from a digital PDF using pdfplumber with per-page classification.

    Returns: (full_text, page_count, pages_meta, all_tables)
    - full_text: concatenated text from all pages
    - pages_meta: per-page metadata (text_chars, has_images, is_scanned)
    - all_tables: structured table data across all pages (not flattened)
    """
    text_parts: list[str] = []
    pages_meta: list[PageMeta] = []
    all_tables: list[list[list[str]]] = []

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            has_images = _page_has_images(page)
            text_chars = len(re.sub(r"\s+", "", page_text))
            is_scanned = text_chars < _MIN_TEXT_CHARS_PER_PAGE and has_images

            # Extract tables in structured form (preserves header→value relationships)
            page_tables: list[list[str]] = []
            raw_tables = page.extract_tables()
            table_text_lines: list[str] = []
            for table in raw_tables:
                for row in table:
                    if row:
                        clean_row = [cell or "" for cell in row]
                        page_tables.append(clean_row)
                        table_text_lines.append("\t".join(clean_row))

            if table_text_lines:
                page_text += "\n" + "\n".join(table_text_lines)
            if page_tables:
                all_tables.extend(page_tables)

            text_parts.append(page_text)
            pages_meta.append(PageMeta(
                page_number=len(pages_meta) + 1,
                text_chars=text_chars,
                has_images=has_images,
                is_scanned=is_scanned,
            ))

    return "\n\n".join(text_parts), page_count, pages_meta, all_tables


def _extract_pdf_pymupdf(data: bytes) -> tuple[str, int]:
    """Fallback PDF extraction using PyMuPDF (no per-page metadata)."""
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
    Main entry point. Detects file type and extracts text with per-page analysis.

    v2 behaviour:
    - Per-page OCR detection: a page is flagged as scanned if it has < 30 non-whitespace
      chars AND contains embedded images. The rest of the document continues processing.
    - Mixed documents (some digital, some scanned) get doc_type=pdf_mixed, with
      scanned_page_numbers listing pages that need OCR.
    - Images are still flagged for client-side OCR (no server-side OCR without pytesseract).
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
    pages_meta: list[PageMeta] = []
    all_tables: list[list[list[str]]] = []
    extraction_error = None

    try:
        text, page_count, pages_meta, all_tables = _extract_pdf_pdfplumber(data)
    except Exception as e:
        extraction_error = e

    # Whole-doc fallback: if pdfplumber produced nothing at all, try PyMuPDF
    if not _has_meaningful_text(text):
        try:
            text, page_count = _extract_pdf_pymupdf(data)
            pages_meta = []  # PyMuPDF fallback has no per-page metadata
        except Exception:
            pass

    # Determine scanned pages from per-page metadata
    scanned_pages = [p.page_number for p in pages_meta if p.is_scanned]
    digital_pages = [p.page_number for p in pages_meta if not p.is_scanned]

    # All pages are scanned and no usable text → needs full OCR
    if not _has_meaningful_text(text):
        return ExtractionResult(
            doc_id=doc_id,
            doc_type=DocumentType.pdf_scanned,
            text_extracted="",
            ocr_used=False,
            ocr_confidence=None,
            page_count=page_count or 1,
            needs_client_ocr=True,
            pages_meta=pages_meta,
            tables=all_tables,
            scanned_page_numbers=scanned_pages,
            has_mixed_content=False,
        )

    # Mixed document: some pages are scanned
    has_mixed = bool(scanned_pages) and bool(digital_pages)

    return ExtractionResult(
        doc_id=doc_id,
        doc_type=DocumentType.pdf_mixed if has_mixed else DocumentType.pdf_digital,
        text_extracted=text,
        ocr_used=False,
        ocr_confidence=None,
        page_count=page_count,
        needs_client_ocr=bool(scanned_pages),  # front-end should OCR the scanned pages
        pages_meta=pages_meta,
        tables=all_tables,
        scanned_page_numbers=scanned_pages,
        has_mixed_content=has_mixed,
    )
