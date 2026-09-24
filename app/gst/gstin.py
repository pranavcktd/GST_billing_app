"""GSTIN format + checksum validation.

Structure: 2-digit state code, 10-char PAN, entity number, 'Z', check character.
The check character uses the mod-36 Luhn-style algorithm published by GSTN.
"""

import re

from .states import STATES

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARS[(36 - total % 36) % 36]


def validate_gstin(gstin: str) -> str | None:
    """Return an error message, or None if the GSTIN is valid."""
    g = (gstin or "").strip().upper()
    if not GSTIN_RE.match(g):
        return "GSTIN must be 15 characters in the format 22AAAAA0000A1Z5"
    if g[:2] not in STATES:
        return f"Invalid state code '{g[:2]}' in GSTIN"
    if gstin_check_char(g[:14]) != g[14]:
        return "GSTIN checksum does not match — please re-check the number"
    return None


def pan_from_gstin(gstin: str) -> str:
    return gstin[2:12]
