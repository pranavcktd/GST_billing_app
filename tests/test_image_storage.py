"""Logos / signatures / item photos kept in our database when the super admin chooses it."""

import io

from PIL import Image

from tests.test_phase2 import sale, setup
from tests.test_security_admin import superadmin


def png(w=2400, h=800, alpha=True) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA" if alpha else "RGB", (w, h), (30, 100, 200, 255) if alpha else (30, 100, 200)).save(out, "PNG")
    return out.getvalue()


def test_database_image_storage(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    r = client.put("/api/admin/documents-settings", headers=root, json={"images_storage": "DATABASE", "image_max_mb": 1})
    assert r.status_code == 200 and r.json()["images_storage"] == "DATABASE"
    assert client.put("/api/admin/documents-settings", headers=root, json={"images_storage": "NOPE"}).status_code == 422

    h, cust, item = setup(client)
    up = client.post("/api/uploads", headers=h, data={"kind": "logo"}, files={"file": ("logo.png", png(), "image/png")})
    assert up.status_code == 200, up.text
    url = up.json()["url"]
    assert url.startswith("/api/files/img/") and url.endswith(".png")
    img = client.get(url)  # public: shown on invoices customers open without signing in
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert max(Image.open(io.BytesIO(img.content)).size) == 1200  # resized
    photo = client.post("/api/uploads", headers=h, data={"kind": "item"}, files={"file": ("p.png", png(alpha=False), "image/png")}).json()["url"]
    assert photo.endswith(".jpg")
    assert client.post("/api/uploads", headers=h, data={"kind": "logo"}, files={"file": ("x.png", b"not an image", "image/png")}).status_code == 400
    assert client.post("/api/uploads", headers=h, data={"kind": "logo"}, files={"file": ("x.gif", b"GIF89a", "image/gif")}).status_code == 400
    assert client.get("/api/files/img/" + "0" * 32 + ".png").status_code == 404

    # the invoice PDF draws the logo from the database
    biz = client.get("/api/businesses/current", headers=h).json()
    keep = {k: x for k, x in biz.items() if k not in ("id", "plan", "einvoice_password_set", "ewb_password_set", "gst_portal", "modules")}
    client.put("/api/businesses/current", headers=h, json={**keep, "logo_url": url})
    v = sale(client, h, cust, item)
    pdf = client.get(f"/api/vouchers/{v['id']}/pdf", headers=h)
    assert pdf.status_code == 200 and b"/Subtype /Image" in pdf.content
