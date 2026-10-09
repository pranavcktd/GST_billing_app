"""IFSC → bank branch details (fake provider): fill, cache, unknown code, bad format, switched off."""

import httpx

from app.services import ifsc
from tests.test_api_flow import signup
from tests.test_security_admin import superadmin

HDFC = {"BANK": "HDFC Bank", "BRANCH": "LAXMI ROAD PUNE", "ADDRESS": "Laxmi Road, Pune", "CITY": "PUNE", "STATE": "MAHARASHTRA",
        "DISTRICT": "PUNE", "MICR": "411240002", "UPI": True, "NEFT": True, "RTGS": True, "IMPS": True, "IFSC": "HDFC0001234"}


def test_ifsc_lookup(client, monkeypatch):
    calls = []

    def get(url):
        calls.append(url)
        code = url.rsplit("/", 1)[1]
        return httpx.Response(200, json=HDFC) if code == "HDFC0001234" else httpx.Response(404, json="Not Found")

    monkeypatch.setattr(ifsc, "_http_get", get)
    ifsc._cache.clear()
    h = signup(client, "bank@x.in")
    r = client.get("/api/ifsc/hdfc0001234", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["bank"] == "HDFC Bank" and r.json()["branch"] == "LAXMI ROAD PUNE" and r.json()["ifsc"] == "HDFC0001234"
    client.get("/api/ifsc/HDFC0001234", headers=h)
    assert len(calls) == 1  # cached
    assert client.get("/api/ifsc/ZZZZ0123456", headers=h).status_code == 404
    assert client.get("/api/ifsc/HDFC1234", headers=h).status_code == 422  # bad format never reaches the provider
    assert len(calls) == 2
    assert client.get("/api/ifsc/HDFC0001234").status_code == 401  # signed-in users only

    root = superadmin(client, monkeypatch)
    assert client.put("/api/admin/ifsc-api", headers=root, json={"enabled": False}).json()["enabled"] is False
    assert client.get("/api/ifsc/HDFC0001234", headers=h).status_code == 503
    assert client.put("/api/admin/ifsc-api", headers=root, json={"base_url": "http://insecure"}).status_code == 422
