"""Sequential document numbering per series and financial year.

GST (Rule 46) requires invoice numbers to be unique within a financial year, consecutive,
at most 16 characters, using only letters, digits, '-' and '/'.
Format: PREFIX/YY-YY/0001, e.g. INV/26-27/0001.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..gst.fy import fy_short
from ..models import Counter


def format_number(prefix: str, d: dt.date, seq: int) -> str:
    fy = fy_short(d)
    number = f"{prefix}/{fy}/{seq:04d}"
    if len(number) > 16:
        number = f"{prefix}{fy.replace('-', '')}{seq}"
    return number


def allocate_number(db: Session, business_id: str, key: str, prefix: str, d: dt.date, exists) -> str:
    """Take the next free number in the series. `exists(number)` guards against numbers typed manually."""
    fy = fy_short(d)
    counter = db.scalar(
        select(Counter)
        .where(Counter.business_id == business_id, Counter.key == key, Counter.fy == fy)
        .with_for_update()
    )
    if counter is None:
        counter = Counter(business_id=business_id, key=key, fy=fy, next=1)
        db.add(counter)
        db.flush()
    while True:
        number = format_number(prefix, d, counter.next)
        counter.next += 1
        if not exists(number):
            return number


def preview_number(db: Session, business_id: str, key: str, prefix: str, d: dt.date) -> str:
    counter = db.get(Counter, (business_id, key, fy_short(d)))
    return format_number(prefix, d, counter.next if counter else 1)
