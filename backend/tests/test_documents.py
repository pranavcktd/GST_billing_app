"""Document vault: upload (database storage), links, limits, permissions, share links, e-mail."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_rbac import staff
from tests.test_security_admin import platform_mail, SENT, fake_mail, superadmin  # noqa: F401 — fake_mail: autouse SMTP stub

PDF = b"%PDF-1.4\n% test document\n"


def upload(client, h, name="itr.pdf", data=PDF, **fields):
    form = {"title": "ITR FY 2025-26", "category": "Income-tax return & computation", "financial_year": "2025-26", **fields}
    return client.post("/api/documents", headers=h, data=form, files={"file": (name, data, "application/octet-stream")})


def test_vault_upload_link_share_email(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    assert client.put("/api/admin/documents-settings", headers=root, json={"storage": "DATABASE", "max_file_mb": 1, "quota_mb": 1}).status_code == 200
    h = make_business(client, signup(client))
    meta = client.get("/api/documents/meta", headers=h).json()
    assert meta["allow_upload"] and meta["allow_links"] and "FSSAI licence" in meta["categories"]

    r = upload(client, h)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["kind"] == "FILE" and doc["size_bytes"] == len(PDF) and doc["file_name"] == "itr.pdf"
    f = client.get(f"/api/documents/{doc['id']}/file", headers=h)
    assert f.status_code == 200 and f.content == PDF and f.headers["content-type"].startswith("application/pdf")

    # file type, size and storage limits
    assert upload(client, h, name="virus.exe").status_code == 400
    assert upload(client, h, data=b"x" * (1024 * 1024 + 1)).status_code == 400
    assert upload(client, h, data=b"y" * (1024 * 1024 - 10)).status_code == 400  # would exceed the 1 MB quota

    # a link document, with an expiry date (licence)
    link = client.post("/api/documents", headers=h, data={
        "title": "FSSAI licence", "category": "FSSAI licence", "url": "https://drive.google.com/file/d/abc/view", "expiry_date": "2026-10-20"})
    assert link.status_code == 201 and link.json()["kind"] == "LINK" and link.json()["expiry_status"] == "EXPIRING"
    assert client.post("/api/documents", headers=h, data={"title": "x", "url": "javascript:alert(1)"}).status_code == 422
    assert {d["title"] for d in client.get("/api/documents", headers=h, params={"q": "fssai"}).json()} == {"FSSAI licence"}

    # share link opens without signing in; a link document shares its own address
    s = post(client, h, f"/api/documents/{doc['id']}/share-link", {}, 200)
    token_path = s["url"].split("/api", 1)[1]
    pub = client.get("/api" + token_path)
    assert pub.status_code == 200 and pub.content == PDF
    assert client.get("/api/public/documents/not-a-real-token-xxxxxxxxxx").status_code == 404
    assert post(client, h, f"/api/documents/{link.json()['id']}/share-link", {}, 200)["url"].startswith("https://drive.google.com")

    # e-mail with the file attached
    platform_mail(client)
    assert post(client, h, f"/api/documents/{doc['id']}/email", {"to": ["ca@firm.in"], "message": "For audit"}, 200)["sent"]
    msg = SENT[-1]
    assert msg["To"] == "ca@firm.in" and any(p.get_filename() == "itr.pdf" for p in msg.iter_attachments())

    # billing staff cannot see the vault; the accountant can read but not delete
    billing = staff(client, h, "op@x.in", "BILLING")
    assert client.get("/api/documents", headers=billing).status_code == 403
    ca = staff(client, h, "ca@x.in", "ACCOUNTANT")
    assert client.get("/api/documents", headers=ca).status_code == 200
    assert client.delete(f"/api/documents/{doc['id']}", headers=ca).status_code == 403

    # other businesses can't reach it; deleting removes it
    other = make_business(client, signup(client, "o2@x.in"))
    assert client.get(f"/api/documents/{doc['id']}/file", headers=other).status_code == 404
    assert client.delete(f"/api/documents/{doc['id']}", headers=h).status_code == 204
    assert client.get("/api" + token_path).status_code == 404

    # links-only mode: uploads refused, links still fine
    client.put("/api/admin/documents-settings", headers=root, json={"storage": "LINKS"})
    assert upload(client, h).status_code == 403
    assert not client.get("/api/documents/meta", headers=h).json()["allow_upload"]
