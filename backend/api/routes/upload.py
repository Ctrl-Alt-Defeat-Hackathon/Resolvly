"""
POST /api/v1/documents/upload

Accepts up to 5 files (PDF, JPG, PNG), extracts text from digital PDFs,
and returns per-document extraction results plus an upload_id for subsequent calls.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import get_settings
from extraction.pdf_extractor import DocumentType, extract_document

router = APIRouter()
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".tiff"}


class DocumentResult(BaseModel):
    doc_id: str
    filename: str
    type: DocumentType
    text_extracted: str
    ocr_used: bool
    ocr_confidence: float | None
    page_count: int
    needs_client_ocr: bool


class UploadResponse(BaseModel):
    upload_id: str
    documents: list[DocumentResult]


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def upload_documents(
    request: Request,
    files: Annotated[list[UploadFile], File(description="PDF or image files (max 5, 10 MB each)")],
) -> UploadResponse:
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {settings.max_files_per_upload} files per upload.",
        )

    upload_id = str(uuid.uuid4())
    results: list[DocumentResult] = []

    for file in files:
        # Validate file size
        data = await file.read()
        size_mb = len(data) / (1024 * 1024)
        if size_mb > settings.max_file_size_mb:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{file.filename}' exceeds the {settings.max_file_size_mb} MB limit.",
            )

        # Validate content type / extension
        filename = file.filename or "document"
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        content_type = file.content_type or ""

        if content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{filename}' has unsupported type '{content_type}'. Allowed: PDF, JPG, PNG.",
            )

        doc_id = str(uuid.uuid4())
        result = extract_document(doc_id=doc_id, filename=filename, data=data)

        results.append(
            DocumentResult(
                doc_id=result.doc_id,
                filename=filename,
                type=result.doc_type,
                text_extracted=result.text_extracted,
                ocr_used=result.ocr_used,
                ocr_confidence=result.ocr_confidence,
                page_count=result.page_count,
                needs_client_ocr=result.needs_client_ocr,
            )
        )

    return UploadResponse(upload_id=upload_id, documents=results)
