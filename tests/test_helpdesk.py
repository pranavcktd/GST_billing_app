"""Helpdesk tickets raised in the app, handled by the company team; team members and their admin areas."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_payment_records import bell, make_staff
from tests.test_security_admin import SENT, fake_mail, platform_mail, superadmin  # noqa: F401 — fake_mail: e-mail stub

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def raise_ticket(client, h, **kw):
    data = {"category": "ISSUE", "subject": "Invoice PDF is blank", "body": "When I print invoice 12 the PDF is empty.",
            "priority": "HIGH", "module": "Sale Invoices", "page": "/v/sales/12", **kw}
    return client.post("/api/support/tickets", headers=h, data=data, files=[("files", ("screen.png", PNG, "image/png"))])


def test_ticket_life_cycle(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    platform_mail(client)
    support = make_staff(client, "asha@platform.in", ["helpdesk"], "SUPPORT")
    finance = make_staff(client, "fin@platform.in", ["helpdesk", "payments"], "FINANCE")
    sales = make_staff(client, "sales@platform.in", ["payments"], "SALES")
    owner = signup(client)
    h = make_business(client, owner)
    client.get("/api/auth/me", headers=root)  # super admin role saved

    SENT.clear()
    r = raise_ticket(client, h)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["code"] == "T-1001" and t["team"] == "SUPPORT" and t["business_name"] and t["status"] == "OPEN"
    # routed: support team + super admin get it; finance (other team) and sales (no helpdesk) do not
    assert bell(client, support)["items"][0]["kind"] == "TICKET_NEW"
    assert bell(client, root)["items"][0]["kind"] == "TICKET_NEW"
    assert bell(client, finance)["unread"] == 0 and bell(client, sales)["unread"] == 0
    assert any(m["To"] == "owner@shop.in" and "T-1001" in m["Subject"] for m in SENT)  # acknowledgement

    # billing questions go to Finance
    b = raise_ticket(client, owner, category="BILLING", subject="Charged twice", priority="NORMAL").json()
    assert b["team"] == "FINANCE" and b["business_name"] is None and bell(client, finance)["unread"] == 1

    # the queue
    q = client.get("/api/admin/helpdesk", headers=support, params={"status": "ACTIVE"}).json()
    assert [x["code"] for x in q["rows"]] == ["T-1001", "T-1002"] and q["unassigned"] == 2  # HIGH first
    assert client.get("/api/admin/helpdesk", headers=sales).status_code == 403
    assert client.get("/api/admin/helpdesk", headers=owner).status_code == 403
    assert client.get("/api/admin/helpdesk", headers=root, params={"q": "T-1002"}).json()["rows"][0]["code"] == "T-1002"
    meta = client.get("/api/admin/helpdesk/meta", headers=support).json()
    agent_ids = {a["id"] for a in meta["agents"]}
    assert len(agent_ids) == 3  # root, support, finance

    # internal note: never shown to the user; then a public reply assigns and notifies
    d = client.post(f"/api/admin/helpdesk/{t['id']}/messages", headers=support, data={"body": "Looks like a font issue", "internal": "true"}).json()
    assert d["messages"][-1]["internal"] and d["assigned_to"] is None and d["first_response_at"] is None
    SENT.clear()
    d = client.post(f"/api/admin/helpdesk/{t['id']}/messages", headers=support, data={"body": "Please try Print → Save as PDF."}).json()
    assert d["status"] == "IN_PROGRESS" and d["assigned_to"] and d["first_response_at"]
    me_view = client.get(f"/api/support/tickets/{t['id']}", headers=owner).json()
    assert [m["body"] for m in me_view["messages"]] == ["When I print invoice 12 the PDF is empty.", "Please try Print → Save as PDF."]
    assert me_view["messages"][1]["author"] == "Support team" and len(me_view["files"]) == 1
    assert bell(client, owner)["items"][0]["kind"] == "TICKET_REPLY" and any(m["To"] == "owner@shop.in" for m in SENT)
    # attachment: owner and team can open it, someone else cannot
    fid = me_view["files"][0]["id"]
    assert client.get(f"/api/support/files/{fid}", headers=owner).content == PNG
    assert client.get(f"/api/support/files/{fid}", headers=support).status_code == 200
    assert client.get(f"/api/support/files/{fid}", headers=signup(client, "x@x.in")).status_code == 404
    assert client.get(f"/api/support/tickets/{t['id']}", headers=finance).status_code == 404  # user route is owner-only

    # user replies → assignee alerted; resolve → user alerted; rate
    client.post(f"/api/support/tickets/{t['id']}/messages", headers=owner, data={"body": "Still blank"})
    assert bell(client, support)["items"][0]["kind"] == "TICKET_REPLY"
    d = client.put(f"/api/admin/helpdesk/{t['id']}", headers=support, json={"status": "RESOLVED"}).json()
    assert d["status"] == "RESOLVED" and bell(client, owner)["items"][0]["kind"] == "TICKET_RESOLVED"
    assert post(client, owner, f"/api/support/tickets/{t['id']}/rate", {"rating": 5, "note": "Quick help"}, 200)["rating"] == 5
    # replying reopens; closing; replying to a closed ticket is refused
    client.post(f"/api/support/tickets/{t['id']}/messages", headers=owner, data={"body": "Again blank today"})
    assert client.get(f"/api/support/tickets/{t['id']}", headers=owner).json()["status"] == "OPEN"
    post(client, owner, f"/api/support/tickets/{t['id']}/state", {"action": "close"}, 200)
    assert client.post(f"/api/support/tickets/{t['id']}/messages", headers=owner, data={"body": "x"}).status_code == 400

    # assignment and validation
    d = client.put(f"/api/admin/helpdesk/{b['id']}", headers=root, json={"assigned_to": [i for i in agent_ids if i != d["assigned_to"]][0]}).json()
    assert d["assigned_name"]
    bad = client.put(f"/api/admin/helpdesk/{b['id']}", headers=root, json={"assigned_to": "nobody"})
    assert bad.status_code == 400
    assert client.get("/api/admin/helpdesk", headers=root).json()["rating"] == {"average": 5.0, "count": 1}
    assert [x["code"] for x in client.get("/api/support/tickets", headers=owner).json()] == ["T-1002", "T-1001"]

    # files: type and size checks
    r = client.post("/api/support/tickets", headers=h, data={"category": "QUESTION", "subject": "Script", "body": "see file"},
                    files=[("files", ("x.html", b"<script>", "text/html"))])
    assert r.status_code == 400 and "only images" in r.text


def test_team_members_and_areas(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    platform_mail(client)
    owner = signup(client)
    make_business(client, owner)

    out = post(client, root, "/api/admin/team", {"name": "Asha", "email": "asha@corenexgen.in", "team": "SUPPORT"}, 201)
    assert out["areas"] == ["helpdesk"] and out["temporary_password"] and out["emailed"]
    login = client.post("/api/auth/login", json={"email": "asha@corenexgen.in", "password": out["temporary_password"]}).json()
    asha = {"Authorization": f"Bearer {login['token']}"}
    me = client.get("/api/auth/me", headers=asha).json()
    assert me["platform_role"] == "TEAM" and me["platform_areas"] == ["helpdesk"] and me["must_change_password"]
    assert client.get("/api/admin/helpdesk", headers=asha).status_code == 200
    for path in ("/api/admin/payments", "/api/admin/team", "/api/admin/stats", "/api/admin/businesses", "/api/admin/site", "/api/admin/users"):
        assert client.get(path, headers=asha).status_code == 403, path

    # an existing login (owner) joins as a deputy admin with every area
    dep = post(client, root, "/api/admin/team", {"name": "Owner", "email": "owner@shop.in", "team": "ADMIN"}, 201)
    assert set(dep["areas"]) == {"helpdesk", "payments", "analytics", "accounts", "website"} and dep["temporary_password"] is None
    assert client.get("/api/admin/businesses", headers=owner).status_code == 200
    assert client.get("/api/admin/site", headers=owner).status_code == 200
    assert client.get("/api/admin/team", headers=owner).status_code == 403  # the team itself stays with the super admin
    assert client.put("/api/admin/site/terms", headers=owner, json={"title": "Terms", "body": "x", "reaccept": True}).status_code == 403

    # super admin / reseller e-mails cannot be added; no duplicates; unknown area refused
    assert client.post("/api/admin/team", headers=root, json={"name": "Root", "email": "root@platform.in", "team": "TECH"}).status_code == 400
    assert client.post("/api/admin/team", headers=root, json={"name": "Asha", "email": "asha@corenexgen.in", "team": "TECH"}).status_code == 409
    assert client.post("/api/admin/team", headers=root, json={"name": "Bina", "email": "b@x.in", "team": "TECH", "areas": ["keys"]}).status_code == 422
    assert client.post("/api/admin/team", headers=asha, json={"name": "Bina", "email": "b@x.in", "team": "TECH"}).status_code == 403

    # a ticket assigned to Asha goes back to the queue when she is deactivated
    t = raise_ticket(client, owner).json()
    client.put(f"/api/admin/helpdesk/{t['id']}", headers=root, json={"assigned_to": out["id"]})
    edited = client.put(f"/api/admin/team/{out['id']}", headers=root, json={"team": "SUPPORT", "areas": ["helpdesk"], "active": False}).json()
    assert not edited["active"]
    assert client.get(f"/api/admin/helpdesk/{t['id']}", headers=root).json()["assigned_to"] is None
    assert client.get("/api/auth/me", headers=asha).status_code == 401  # signed out

    # removing team access keeps the login
    assert client.delete(f"/api/admin/team/{dep['id']}", headers=root).status_code == 204
    assert client.get("/api/admin/businesses", headers=owner).status_code == 403
    me = client.get("/api/auth/me", headers=owner).json()  # still signed in to their own business
    assert me["platform_role"] is None and me["platform_areas"] == [] and me["businesses"]
    members = client.get("/api/admin/team", headers=root).json()["members"]
    assert [m["email"] for m in members] == ["asha@corenexgen.in"]
