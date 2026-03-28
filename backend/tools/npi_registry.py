"""
NPI Registry Lookup Tool

Fetches provider details from the NPPES NPI Registry API.
Endpoint: https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi}

Free, no API key required.
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel

_NPPES_URL = "https://npiregistry.cms.hhs.gov/api/"
_TIMEOUT = 10.0


class NPIResult(BaseModel):
    npi: str
    provider_name: str = ""
    provider_type: str = ""  # "individual" or "organization"
    specialty: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    phone: str = ""
    source: str = "NPPES NPI Registry (CMS)"
    source_url: str = ""
    found: bool = True


async def lookup_npi(npi: str) -> NPIResult:
    """
    Look up an NPI number and return provider details.

    Uses the NPPES NPI Registry API v2.1 (free, no auth required).
    """
    npi = npi.strip()
    if not npi.isdigit() or len(npi) != 10:
        return NPIResult(
            npi=npi,
            provider_name=f"Invalid NPI format: {npi} (must be exactly 10 digits)",
            found=False,
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _NPPES_URL,
                params={"version": "2.1", "number": npi},
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                return NPIResult(
                    npi=npi,
                    provider_name=f"NPI {npi} not found in NPPES registry",
                    found=False,
                )

            result = results[0]
            entity_type = result.get("enumeration_type", "")

            # Parse name
            basic = result.get("basic", {})
            if entity_type == "NPI-1":  # Individual
                first = basic.get("first_name", "")
                last = basic.get("last_name", "")
                credential = basic.get("credential", "")
                name = f"{first} {last}"
                if credential:
                    name += f", {credential}"
                provider_type = "individual"
            else:  # Organization (NPI-2)
                name = basic.get("organization_name", "Unknown Organization")
                provider_type = "organization"

            # Parse primary taxonomy (specialty)
            taxonomies = result.get("taxonomies", [])
            specialty = ""
            for tax in taxonomies:
                if tax.get("primary", False):
                    specialty = tax.get("desc", "")
                    break
            if not specialty and taxonomies:
                specialty = taxonomies[0].get("desc", "")

            # Parse address (primary practice location)
            addresses = result.get("addresses", [])
            practice_addr = None
            for addr in addresses:
                if addr.get("address_purpose") == "LOCATION":
                    practice_addr = addr
                    break
            if not practice_addr and addresses:
                practice_addr = addresses[0]

            address_line = ""
            city = ""
            state = ""
            zip_code = ""
            phone = ""
            if practice_addr:
                addr1 = practice_addr.get("address_1", "")
                addr2 = practice_addr.get("address_2", "")
                address_line = f"{addr1} {addr2}".strip()
                city = practice_addr.get("city", "")
                state = practice_addr.get("state", "")
                zip_code = practice_addr.get("postal_code", "")[:5]
                phone = practice_addr.get("telephone_number", "")

            return NPIResult(
                npi=npi,
                provider_name=name.strip(),
                provider_type=provider_type,
                specialty=specialty,
                address=address_line,
                city=city,
                state=state,
                zip_code=zip_code,
                phone=phone,
                source_url=f"https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi}",
            )

    except (httpx.HTTPError, KeyError, IndexError):
        pass

    return NPIResult(
        npi=npi,
        provider_name=f"NPI {npi} — lookup failed (API unavailable)",
        found=False,
    )
