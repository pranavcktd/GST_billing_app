"""Staff logins created by the owner, the same person working for several businesses, sign-in control."""

from tests.test_api_flow import gstin, make_business, signup
from tests.test_modules import post
from tests.test_rbac import accept_invites
from tests.test_security_admin import login


def auth_of(r):
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_owner_creates_staff_and_shared_accountant(client):
    a = make_business(client, signup(client, "owner-a@x.in"))
    b = make_business(client, signup(client, "owner-b@x.in"), name="Verma Stores", gstin=gstin("27", "AABCV1429B"))

    # A creates a brand-new login for the accountant: temporary password, changed at first sign-in
    r = post(client, a, "/api/members", {"email": "Ravi.CA@x.in", "name": "Ravi", "role": "ACCOUNTANT"})
    assert r["created"] and r["temp_password"] and r["email"] == "ravi.ca@x.in"
    ravi = auth_of(login(client, "ravi.ca@x.in", r["temp_password"]))
    me = client.get("/api/auth/me", headers=ravi).json()
    assert me["must_change_password"] and [x["name"] for x in me["businesses"]] == ["Sharma Traders"]
    assert client.put("/api/auth/password", headers=ravi, json={"current_password": r["temp_password"], "new_password": "ravi-own-pass"}).status_code == 200
    ravi = auth_of(login(client, "ravi.ca@x.in", "ravi-own-pass"))

    # while Ravi works only for A, A may set a new temporary password
    mem_a = next(m for m in client.get("/api/members", headers=a).json() if m["email"] == "ravi.ca@x.in")
    assert mem_a["managed"] and mem_a["other_businesses"] == 0

    # B adds the same e-mail: no second account, no new password — an invitation Ravi must accept
    r = post(client, b, "/api/members", {"email": "ravi.ca@x.in", "name": "Someone else", "role": "ACCOUNTANT", "password": "owner-b-chosen"})
    assert r["invited"] and not r["created"] and "temp_password" not in r
    assert login(client, "ravi.ca@x.in", "owner-b-chosen").status_code == 401
    rb = {**ravi, "X-Business-Id": b["X-Business-Id"]}
    assert client.get("/api/parties", headers=rb).status_code == 403  # not accepted yet
    assert post(client, b, "/api/members", {"email": "ravi.ca@x.in", "role": "BILLING"}, 409)
    me = client.get("/api/auth/me", headers=ravi).json()
    assert [i["business_name"] for i in me["invitations"]] == ["Verma Stores"]
    accept_invites(client, ravi)
    assert client.get("/api/parties", headers=rb).status_code == 200
    assert len(client.get("/api/auth/me", headers=ravi).json()["businesses"]) == 2

    # now neither owner can change Ravi's password (it would lock him out of the other business)
    mem_a = next(m for m in client.get("/api/members", headers=a).json() if m["email"] == "ravi.ca@x.in")
    assert not mem_a["managed"] and mem_a["other_businesses"] == 1
    assert client.post(f"/api/members/{mem_a['id']}/temp-password", headers=a).status_code == 403
    mem_b = next(m for m in client.get("/api/members", headers=b).json() if m["email"] == "ravi.ca@x.in")
    assert client.post(f"/api/members/{mem_b['id']}/temp-password", headers=b).status_code == 403
    assert login(client, "ravi.ca@x.in", "ravi-own-pass").status_code == 200

    # declining an invitation removes it
    c = make_business(client, signup(client, "owner-c@x.in"), name="C", gstin=gstin("27", "AABCC1429B"))
    post(client, c, "/api/members", {"email": "ravi.ca@x.in", "role": "BILLING"})
    inv = client.get("/api/auth/me", headers=ravi).json()["invitations"][0]
    assert client.post(f"/api/auth/invitations/{inv['id']}/decline", headers=ravi).status_code == 200
    assert client.get("/api/auth/me", headers=ravi).json()["invitations"] == []


def test_exclusive_staff_temp_password(client):
    a = make_business(client, signup(client, "owner-a@x.in"))
    r = post(client, a, "/api/members", {"email": "clerk@x.in", "name": "Clerk", "role": "BILLING", "password": "chosen-by-owner"})
    assert r["temp_password"] == "chosen-by-owner"
    m = next(x for x in client.get("/api/members", headers=a).json() if x["email"] == "clerk@x.in")
    t = post(client, a, f"/api/members/{m['id']}/temp-password", {}, 200)["temp_password"]
    assert login(client, "clerk@x.in", "chosen-by-owner").status_code == 401
    assert login(client, "clerk@x.in", t).status_code == 200


def test_sign_in_control(client):
    owner = make_business(client, signup(client, "owner@x.in"))
    r = post(client, owner, "/api/members", {"email": "op@x.in", "name": "Operator", "role": "BILLING"})
    op_auth = auth_of(login(client, "op@x.in", r["temp_password"]))
    op = {**op_auth, "X-Business-Id": owner["X-Business-Id"]}

    # no rules: works, and the sign-in is recorded for the owner
    assert client.get("/api/parties", headers=op).status_code == 200
    rows = client.get("/api/staff/sessions", headers=owner).json()
    assert len(rows) == 1 and rows[0]["status"] == "AUTO" and rows[0]["email"] == "op@x.in"
    assert client.get("/api/staff/sessions", headers=op).status_code == 403  # billing staff can't see it

    # owner turns on approval: the same session now waits
    p = client.put("/api/staff/policy", headers=owner, json={"approval": True, "approval_hours": 10})
    assert p.status_code == 200 and p.json()["approval"]
    r = client.get("/api/parties", headers=op)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ACCESS_PENDING"
    assert client.get("/api/staff/pending", headers=owner).json()["count"] == 1
    sid = client.get("/api/staff/sessions", headers=owner, params={"status": "PENDING"}).json()[0]["id"]
    assert client.post(f"/api/staff/sessions/{sid}/approve", headers=owner).json()["status"] == "APPROVED"
    assert client.get("/api/parties", headers=op).status_code == 200

    # a new sign-in (another device) needs its own approval
    second = {**auth_of(login(client, "op@x.in", client_pw(client, owner))), "X-Business-Id": owner["X-Business-Id"]}
    assert client.get("/api/parties", headers=second).json()["detail"]["code"] == "ACCESS_PENDING"
    sid2 = client.get("/api/staff/sessions", headers=owner, params={"status": "PENDING"}).json()[0]["id"]
    client.post(f"/api/staff/sessions/{sid2}/deny", headers=owner)
    assert client.get("/api/parties", headers=second).json()["detail"]["code"] == "ACCESS_DENIED"

    assert client.get("/api/parties", headers=op).status_code == 401  # new temporary password signed the old session out
    op = second
    # office-only: the test client is not in the allowed range; the owner is never blocked
    assert client.put("/api/staff/policy", headers=owner, json={"ip_allowlist": ["203.0.113.0/24"]}).status_code == 200
    assert client.get("/api/parties", headers=op).json()["detail"]["code"] == "IP_NOT_ALLOWED"
    assert client.get("/api/parties", headers=owner).status_code == 200
    assert client.put("/api/staff/policy", headers=owner, json={"ip_allowlist": ["not-an-ip"]}).status_code == 422
    # working hours that exclude now
    client.put("/api/staff/policy", headers=owner, json={"hours_from": "00:00", "hours_to": "00:00"})
    assert client.get("/api/parties", headers=op).json()["detail"]["code"] == "OUTSIDE_HOURS"
    client.put("/api/staff/policy", headers=owner, json={})
    assert client.get("/api/parties", headers=op).status_code == 200


def client_pw(client, owner):
    """Give the operator a fresh temporary password (they work only here) and return it."""
    m = next(x for x in client.get("/api/members", headers=owner).json() if x["email"] == "op@x.in")
    return post(client, owner, f"/api/members/{m['id']}/temp-password", {}, 200)["temp_password"]

