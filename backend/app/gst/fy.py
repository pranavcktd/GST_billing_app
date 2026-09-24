"""Indian financial year helpers (April to March)."""

from datetime import date


def fy_start_year(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def fy_label(d: date) -> str:
    """'2026-27'"""
    y = fy_start_year(d)
    return f"{y}-{str(y + 1)[2:]}"


def fy_short(d: date) -> str:
    """'26-27' — used inside document numbers to keep them within 16 characters."""
    y = fy_start_year(d)
    return f"{str(y)[2:]}-{str(y + 1)[2:]}"


def fy_range(d: date) -> tuple[date, date]:
    y = fy_start_year(d)
    return date(y, 4, 1), date(y + 1, 3, 31)
