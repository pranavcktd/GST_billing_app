"""Audit trail: every successful change (POST/PUT/PATCH/DELETE) is recorded with who, what and when."""

import json
import re

from fastapi import FastAPI, Request
from starlette.responses import Response

from .db import get_db
from .models import AuditLog, User
from .security import decode_token

SKIP = ("/api/auth/", "/api/uploads", "/api/import/", "/api/billing/webhook", "/api/reconcile/", "/api/admin/", "/api/reseller/")
ENTITY = [
    (r"^/api/vouchers/[^/]+/cancel$", "document", "CANCEL"),
    (r"^/api/vouchers/[^/]+/einvoice", "e-invoice", "ACTION"),
    (r"^/api/vouchers/[^/]+/ewaybill", "e-way bill", "ACTION"),
    (r"^/api/vouchers", "document", None),
    (r"^/api/payments", "payment", None),
    (r"^/api/parties", "party", None),
    (r"^/api/items/[^/]+/adjust$", "stock adjustment", "CREATE"),
    (r"^/api/items", "item", None),
    (r"^/api/cheques", "cheque", "ACTION"),
    (r"^/api/accounts", "bank account", None),
    (r"^/api/transfers", "money transfer", None),
    (r"^/api/stock-transfers", "stock transfer", None),
    (r"^/api/godowns", "godown", None),
    (r"^/api/capital", "capital entry", None),
    (r"^/api/tax-payments", "tax payment", None),
    (r"^/api/loans", "loan", None),
    (r"^/api/expenses/categories", "expense category", None),
    (r"^/api/expenses/items", "expense item", None),
    (r"^/api/businesses", "company settings", None),
    (r"^/api/backups", "backup", None),
    (r"^/api/members", "member", None),
    (r"^/api/hsn", "HSN code", None),
    (r"^/api/tax-slab", "tax slab", "UPDATE"),
    (r"^/api/billing", "subscription", "ACTION"),
    (r"^/api/company", "company", "DELETE"),
]
VERB = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
LABEL = {"CREATE": "Created", "UPDATE": "Updated", "DELETE": "Deleted", "CANCEL": "Cancelled", "ACTION": ""}
ID_RE = re.compile(r"/([0-9a-f]{32})(?:/|$)")


def _describe(path: str, method: str, body: dict | None) -> tuple[str, str, str | None, str]:
    entity, action = "record", VERB.get(method, "ACTION")
    for pattern, ent, act in ENTITY:
        if re.match(pattern, path):
            entity, action = ent, act or action
            break
    m = ID_RE.search(path)
    entity_id = m.group(1) if m else (body or {}).get("id")
    what = ""
    if body:
        if body.get("title") and body.get("number"):
            entity = body["title"]
            what = body["number"]
        else:
            what = body.get("number") or body.get("name") or ""
        if body.get("grand_total") is not None:
            what += f" (₹{body['grand_total']:,.2f})"
        elif body.get("amount") is not None and isinstance(body.get("amount"), (int, float)):
            what += f" ₹{body['amount']:,.2f}"
    if path.endswith("/einvoice") or path.endswith("/ewaybill") or "/einvoice/" in path:
        what = path.rsplit("/", 1)[-1].replace("-", " ") + (f" for {body.get('number')}" if body and body.get("number") else "")
    verb = LABEL[action]
    summary = f"{verb} {entity} {what}".strip() if verb else f"{entity}: {what or path.rsplit('/', 1)[-1]}"
    return action, entity, entity_id, summary[:300]


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def audit_trail(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (request.method not in VERB or response.status_code >= 400 or not path.startswith("/api/")
                or path.startswith(SKIP)):
            return response
        raw = b"".join([chunk async for chunk in response.body_iterator])
        try:
            body = json.loads(raw) if raw and "json" in (response.media_type or response.headers.get("content-type", "")) else None
            body = body if isinstance(body, dict) else None
            user_id = None
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                user_id = decode_token(auth[7:])
            business_id = request.headers.get("x-business-id")
            if user_id and business_id:
                action, entity, entity_id, summary = _describe(path, request.method, body)
                gen = app.dependency_overrides.get(get_db, get_db)()
                db = next(gen)
                try:
                    user = db.get(User, user_id)
                    db.add(AuditLog(business_id=business_id, user_id=user_id, user_name=user.name if user else None,
                                    action=action, entity=entity, entity_id=entity_id, summary=summary,
                                    ip=request.client.host if request.client else None))
                    db.commit()
                except Exception:  # noqa: BLE001 — auditing must never break the request
                    db.rollback()
                finally:
                    gen.close()
        except Exception:  # noqa: BLE001
            pass
        return Response(content=raw, status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
                        media_type=response.media_type)
