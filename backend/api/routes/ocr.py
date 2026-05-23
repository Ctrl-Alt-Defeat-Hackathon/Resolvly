"""
POST /api/v1/documents/ocr/page

Server-side OCR fallback for individual scanned pages.

Clients call this when Tesseract.js returns average confidence < 0.6 or crashes.
Requires pytesseract + Tesseract binary on the host; returns 501 when unavailable.

Install: pip install pytesseract Pillow && apt-get install tesseract-ocr
"""
from __future__ import annotations

import io
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

router = APIRouter()


class OcrPageResponse(BaseModel):
    text: str
    confidence: float
    engine: str = "pytesseract"


@router.post("/ocr/page", response_model=OcrPageResponse, status_code=status.HTTP_200_OK)
async def ocr_page(
    file: Annotated[UploadFile, File(description="Single page image (PNG/JPEG) to OCR server-side")],
) -> OcrPageResponse:
    """
    Run server-side OCR on a single page image.

    Returns 501 if pytesseract is not installed on this host.
    The client should fall back to Tesseract.js on 501.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Server-side OCR (pytesseract) is not installed on this host. "
                "Use client-side Tesseract.js instead. "
                "To enable: pip install pytesseract Pillow && install Tesseract binary."
            ),
        )

    data = await file.read()
    try:
        image = Image.open(io.BytesIO(data))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not open image file. Ensure it is a valid PNG or JPEG.",
        )

    try:
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        words = [w for w, c in zip(ocr_data["text"], ocr_data["conf"]) if int(c) > 0 and w.strip()]
        confs = [int(c) for c in ocr_data["conf"] if int(c) > 0]
        text = " ".join(words)
        avg_conf = sum(confs) / len(confs) / 100.0 if confs else 0.0
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR failed: {e}",
        )

    return OcrPageResponse(text=text, confidence=round(avg_conf, 3))
