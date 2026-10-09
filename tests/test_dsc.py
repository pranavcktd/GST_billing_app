"""Digital signature from a .pfx file: upload checks, automatic / on-request signing, signature intact in the PDF."""

import datetime as dt
import io

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from tests.test_phase2 import sale, setup


def make_pfx(password: str = "secret", days: int = 365, name: str = "RAMESH SHARMA") -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sharma Traders")])
    now = dt.datetime.now(dt.UTC)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=2))
            .not_valid_after(now + dt.timedelta(days=days))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False,
                                         decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b"dsc", key, cert, None, serialization.BestAvailableEncryption(password.encode()))


def signatures(pdf: bytes):
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    r = PdfFileReader(io.BytesIO(pdf))
    return [validate_pdf_signature(s) for s in r.embedded_signatures]


def test_dsc_upload_and_signing(client):
    h, cust, item = setup(client)
    v = sale(client, h, cust, item)
    assert client.get("/api/dsc", headers=h).json() == {"configured": False}
    plain = client.get(f"/api/vouchers/{v['id']}/pdf", headers=h).content
    assert signatures(plain) == []

    up = lambda data, pw, mode="AUTO": client.post("/api/dsc", headers=h, files={"file": ("dsc.pfx", data)},  # noqa: E731
                                                   data={"password": pw, "mode": mode})
    assert up(make_pfx(), "wrong").status_code == 400
    assert up(b"not a certificate", "secret").status_code == 400
    assert "expired" in up(make_pfx(days=-1), "secret").json()["detail"]
    r = up(make_pfx(), "secret")
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["configured"] and st["subject"] == "RAMESH SHARMA" and st["mode"] == "AUTO" and st["days_left"] >= 364
    assert "pfx" not in str(st).lower() and "password" not in st  # secrets never go back to the browser

    signed = client.get(f"/api/vouchers/{v['id']}/pdf", headers=h).content
    sigs = signatures(signed)
    assert len(sigs) == 1 and sigs[0].intact and sigs[0].bottom_line is False  # intact; self-made CA not trusted
    assert sigs[0].signing_cert.subject.native["common_name"] == "RAMESH SHARMA"
    # customer link PDF is signed too in AUTO mode
    link = client.post(f"/api/vouchers/{v['id']}/share-link", headers=h).json()["token"]
    assert len(signatures(client.get(f"/api/public/invoice/{link}/pdf").content)) == 1

    # only on request
    assert client.put("/api/dsc/mode", headers=h, json={"mode": "ON_REQUEST"}).json()["mode"] == "ON_REQUEST"
    assert signatures(client.get(f"/api/vouchers/{v['id']}/pdf", headers=h).content) == []
    assert len(signatures(client.get(f"/api/vouchers/{v['id']}/pdf?sign=true", headers=h).content)) == 1

    assert client.delete("/api/dsc", headers=h).status_code == 204
    assert client.get("/api/dsc", headers=h).json() == {"configured": False}
    assert signatures(client.get(f"/api/vouchers/{v['id']}/pdf?sign=true", headers=h).content) == []
