"""
State DOI Contact Lookup Tool — the ONE static data file in the system.
Returns DOI contact block from state_doi_contacts.json for any US state.
"""
from __future__ import annotations

import json
from pathlib import Path

_DOI_DATA_PATH = Path(__file__).parent.parent / "data" / "state_doi_contacts.json"

with open(_DOI_DATA_PATH) as f:
    _STATE_DOI: dict = json.load(f)


def get_doi_contact(state: str) -> dict | None:
    """Return DOI contact entry for the given 2-letter state code, or None if not found."""
    return _STATE_DOI.get(state.upper())


def list_states() -> list[str]:
    return list(_STATE_DOI.keys())
