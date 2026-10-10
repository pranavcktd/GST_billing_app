"""Website content: policy pages and home page edited by the super admin, versions, restore, reset, re-acceptance."""

from tests.test_api_flow import signup
from tests.test_security_admin import superadmin


def test_edit_versions_and_reaccept(client, monkeypatch):
    t = client.get("/api/site/terms").json()
    assert not t["custom"] and "## 1. Acceptance and versions" in t["body"] and t["format"] == "markdown"
    assert client.get("/api/site/landing").json()["body"] is None  # home page uses the built-in texts
    assert client.get("/api/site/nope").status_code == 404

    user = signup(client, "reader@x.in")
    root = superadmin(client, monkeypatch)
    assert client.put("/api/site/terms", headers=root, json={}).status_code == 405  # public route is read-only
    r = client.put("/api/admin/site/terms", headers=root, json={"title": "Terms of Service", "body": "## New terms\n\nHello", "reaccept": True})
    assert r.status_code == 200 and r.json()["legal_version"]
    assert client.get("/api/site/terms").json()["body"].startswith("## New terms")
    assert client.get("/api/auth/me", headers=user).json()["legal_ok"] is False  # everyone accepts the new terms

    client.put("/api/admin/site/terms", headers=root, json={"title": "Terms of Service", "body": "## Newer"})
    vs = client.get("/api/admin/site/terms/versions", headers=root).json()
    assert len(vs) == 2  # the built-in text and "New terms" were kept
    older = next(v for v in vs if client.get(f"/api/admin/site/terms/versions/{v['id']}", headers=root).json()["body"].startswith("## New terms"))
    assert client.post(f"/api/admin/site/terms/versions/{older['id']}/restore", headers=root).json()["body"].startswith("## New terms")
    assert client.post("/api/admin/site/terms/reset", headers=root).json()["custom"] is False
    assert "## 1. Acceptance" in client.get("/api/site/terms").json()["body"]

    assert client.put("/api/admin/site/landing", headers=root, json={"title": "Home", "body": "[1, 2]"}).status_code == 422
    ok = client.put("/api/admin/site/landing", headers=root, json={"title": "Home", "body": '{"hero": {"title": "Hi"}}'})
    assert ok.status_code == 200 and client.get("/api/site/landing").json()["custom"]
    assert client.get("/api/admin/site", headers=user).status_code == 403
