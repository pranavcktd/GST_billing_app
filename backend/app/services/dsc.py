"""Digital signature (DSC) on document PDFs from a certificate file (.pfx / .p12) the business uploads.

The certificate and its password are stored encrypted (same key as other secrets) and never sent back to the browser.
PDFs are signed with PAdES (pyHanko): Adobe Reader shows the signer and flags any change made after signing; it shows
"valid" when it trusts the issuing CA. Business setting: sign every PDF automatically (AUTO) or only on request.
USB-token DSCs (keys that cannot leave the token) need signing on the user's computer — a later phase.
"""

import datetime as dt
import io

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import BusinessCertificate
from ..security import decrypt_secret, encrypt_secret

MAX_BYTES = 64 * 1024


def _name(n, oid=NameOID.COMMON_NAME) -> str | None:
    vals = n.get_attributes_for_oid(oid)
    return vals[0].value if vals else None


def inspect(data: bytes, password: str) -> dict:
    """Open the certificate file; raise a friendly error when the file or password is wrong, or it has expired."""
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(400, "Upload the certificate file (.pfx or .p12) — it should be a few KB")
    try:
        key, cert, extra = pkcs12.load_key_and_certificates(data, password.encode() if password else None)
    except ValueError as e:
        raise HTTPException(400, "Could not open the certificate — check the file and its password") from e
    if key is None or cert is None:
        raise HTTPException(400, "This file has no private key — export the certificate WITH its private key (.pfx / .p12)")
    now = dt.datetime.now(dt.UTC)
    not_after = cert.not_valid_after_utc
    if not_after < now:
        raise HTTPException(400, f"This certificate expired on {not_after:%d %b %Y}")
    return {"subject": _name(cert.subject) or cert.subject.rfc4514_string()[:200],
            "organisation": _name(cert.subject, NameOID.ORGANIZATION_NAME),
            "issuer": _name(cert.issuer) or cert.issuer.rfc4514_string()[:200], "serial": format(cert.serial_number, "X")[:64],
            "not_before": cert.not_valid_before_utc, "not_after": not_after, "chain": len(extra or [])}


def save(db: Session, business_id: str, data: bytes, password: str, mode: str, user_name: str) -> BusinessCertificate:
    info = inspect(data, password)
    import base64

    row = db.get(BusinessCertificate, business_id) or BusinessCertificate(business_id=business_id)
    row.pfx_enc = encrypt_secret(base64.b64encode(data).decode())
    row.password_enc = encrypt_secret(password or "")
    row.subject, row.organisation, row.issuer, row.serial = info["subject"], info["organisation"], info["issuer"], info["serial"]
    row.not_before, row.not_after = info["not_before"], info["not_after"]
    row.mode = mode
    row.uploaded_by, row.uploaded_at = user_name, dt.datetime.now(dt.UTC)
    db.add(row)
    return row


def status(row: BusinessCertificate | None) -> dict:
    if not row:
        return {"configured": False}
    na = row.not_after if row.not_after.tzinfo else row.not_after.replace(tzinfo=dt.UTC)
    days = (na - dt.datetime.now(dt.UTC)).days
    return {"configured": True, "subject": row.subject, "organisation": row.organisation, "issuer": row.issuer,
            "serial": row.serial, "not_before": row.not_before, "not_after": row.not_after, "days_left": days,
            "expired": days < 0, "mode": row.mode, "uploaded_by": row.uploaded_by, "uploaded_at": row.uploaded_at}


def usable(row: BusinessCertificate | None) -> bool:
    return bool(row) and status(row)["days_left"] >= 0


def sign_pdf(pdf: bytes, row: BusinessCertificate, reason: str, location: str | None = None) -> bytes:
    """Embed a PAdES signature (invisible field; the PDF already prints 'Digitally signed by …')."""
    import base64

    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    data = base64.b64decode(decrypt_secret(row.pfx_enc))
    pw = decrypt_secret(row.password_enc) or None
    signer = signers.SimpleSigner.load_pkcs12_data(data, other_certs=[], passphrase=pw.encode() if pw else None)
    if signer is None:
        raise HTTPException(500, "The saved certificate could not be opened — upload it again in Settings")
    meta = signers.PdfSignatureMetadata(field_name="Signature1", reason=reason[:120], location=(location or "")[:80] or None)
    out = io.BytesIO()
    signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf)), meta, signer=signer, output=out)
    return out.getvalue()
