"""
GET /api/v1/codes/lookup?code={code}&type={icd10|cpt|carc|rarc|hcpcs|npi}

Standalone code lookup endpoint — resolves a single billing/denial/provider
code to its authoritative description. Powers the "Search Library" feature
on the frontend.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from tools.cms_icd_lookup import lookup_icd10
from tools.cms_hcpcs_lookup import lookup_cpt_hcpcs
from tools.carc_rarc_lookup import lookup_carc, lookup_rarc
from tools.npi_registry import lookup_npi

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_VALID_CODE_TYPES = {"icd10", "cpt", "hcpcs", "carc", "rarc", "npi"}


class CodeLookupResponse(BaseModel):
    code: str
    code_type: str
    description: str
    plain_english: str = ""
    common_fix: str = ""
    source: str = ""
    source_url: str = ""
    found: bool = True
    extra: dict = {}  # Additional data (e.g., NPI provider details)


@router.get("/lookup", response_model=CodeLookupResponse, status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def lookup_code(
    request: Request,
    code: str = Query(..., description="The code to look up (e.g., M54.5, 99213, 50, N1, 1234567890)"),
    type: str = Query(..., alias="type", description="Code type: icd10, cpt, hcpcs, carc, rarc, npi"),
) -> CodeLookupResponse:
    code = code.strip()
    code_type = type.strip().lower()

    if code_type not in _VALID_CODE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid code type '{code_type}'. Valid types: {', '.join(sorted(_VALID_CODE_TYPES))}",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Code parameter is required.",
        )

    if code_type == "icd10":
        result = await lookup_icd10(code)
        return CodeLookupResponse(
            code=result.code,
            code_type="icd10",
            description=result.description,
            source=result.source,
            source_url=result.source_url,
            found=result.found,
        )

    elif code_type in ("cpt", "hcpcs"):
        result = await lookup_cpt_hcpcs(code)
        return CodeLookupResponse(
            code=result.code,
            code_type=result.code_type,
            description=result.description,
            source=result.source,
            source_url=result.source_url,
            found=result.found,
        )

    elif code_type == "carc":
        result = await lookup_carc(code)
        return CodeLookupResponse(
            code=result.code,
            code_type="carc",
            description=result.description,
            plain_english=result.plain_english,
            common_fix=result.common_fix,
            source=result.source,
            found=result.found,
        )

    elif code_type == "rarc":
        result = await lookup_rarc(code)
        return CodeLookupResponse(
            code=result.code,
            code_type="rarc",
            description=result.description,
            plain_english=result.plain_english,
            source=result.source,
            found=result.found,
        )

    elif code_type == "npi":
        result = await lookup_npi(code)
        return CodeLookupResponse(
            code=result.npi,
            code_type="npi",
            description=f"{result.provider_name} — {result.specialty}" if result.specialty else result.provider_name,
            source=result.source,
            source_url=result.source_url,
            found=result.found,
            extra={
                "provider_name": result.provider_name,
                "provider_type": result.provider_type,
                "specialty": result.specialty,
                "address": result.address,
                "city": result.city,
                "state": result.state,
                "zip_code": result.zip_code,
                "phone": result.phone,
            },
        )

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error")
