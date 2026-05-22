"""
SQLite-backed TTL cache for external API responses (code lookups, NPI, eCFR).

Why SQLite: portable, zero-dependency, survives process restarts on ephemeral
deploys (Render free tier), and is easily wiped for a fresh start.

TTLs:
  ICD-10 / CPT / HCPCS codes — 30 days  (codes are stable between annual updates)
  NPI                        — 7 days   (provider info can change)
  CARC / RARC                — never expire (in-memory table, no network call)
  eCFR / regulation text     — 7 days   (regulations change infrequently)

Usage:
  from tools.code_cache import get_cached, set_cached

  result = await get_cached("icd10", "M17.11")
  if result is None:
      result = await fetch_from_api(...)
      await set_cached("icd10", "M17.11", result, ttl_days=30)
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "data" / "code_cache.sqlite"

_TTL_DAYS: dict[str, int] = {
    "icd10": 30,
    "cpt": 30,
    "hcpcs": 30,
    "npi": 7,
    "ecfr": 7,
    "cms_coverage": 7,
}

# One asyncio.Lock per process to serialize SQLite writes (reads are fine concurrently)
_write_lock = asyncio.Lock()


def _get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS code_cache (
            namespace TEXT NOT NULL,
            key       TEXT NOT NULL,
            value     TEXT NOT NULL,
            expires_at REAL NOT NULL,
            PRIMARY KEY (namespace, key)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_expires ON code_cache(expires_at)"
    )
    con.commit()
    return con


_con: sqlite3.Connection | None = None


def _conn() -> sqlite3.Connection:
    global _con
    if _con is None:
        _con = _get_connection()
    return _con


async def get_cached(namespace: str, key: str) -> Any | None:
    """Return cached value or None if missing/expired."""
    try:
        now = time.time()
        row = _conn().execute(
            "SELECT value FROM code_cache WHERE namespace=? AND key=? AND expires_at>?",
            (namespace, key, now),
        ).fetchone()
        if row:
            return json.loads(row[0])
    except Exception as e:
        logger.debug(f"Cache read error ({namespace}/{key}): {e}")
    return None


async def set_cached(namespace: str, key: str, value: Any, ttl_days: int | None = None) -> None:
    """Write value to cache with TTL. ttl_days defaults to _TTL_DAYS[namespace]."""
    days = ttl_days if ttl_days is not None else _TTL_DAYS.get(namespace, 7)
    expires_at = time.time() + days * 86400
    try:
        async with _write_lock:
            _conn().execute(
                """
                INSERT INTO code_cache (namespace, key, value, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at
                """,
                (namespace, key, json.dumps(value), expires_at),
            )
            _conn().commit()
    except Exception as e:
        logger.debug(f"Cache write error ({namespace}/{key}): {e}")


async def evict_expired() -> int:
    """Delete expired entries. Returns count deleted."""
    try:
        async with _write_lock:
            cur = _conn().execute(
                "DELETE FROM code_cache WHERE expires_at <= ?", (time.time(),)
            )
            _conn().commit()
            return cur.rowcount
    except Exception as e:
        logger.debug(f"Cache eviction error: {e}")
        return 0
