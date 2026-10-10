"""Practitioner workspace: clients, yearly files, figures in, financial statements out.

Enabled per account by the super admin (subscription feature flag `practice_clients` = number of clients).
"""

import copy
import datetime as dt
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..deps import DB, CurrentUser
from ..models import Business, Membership, PracticeClient, PracticeFile, User
from ..services import final_accounts as FA
from ..services import plans as P
from ..services import practice_io as IO
from ..services.platform_audit import log

router = APIRouter(prefix="/practice", tags=["practice"])
FY_RE = r"^20\d\d-\d\d$"


def limit_of(db, user: User) -> int:
    if user.platform_role == "SUPERADMIN":
        return 100000
    flags = P.current(db, user.id).feature_flags or {}
    try:
        return int(flags.get("practice_clients") or 0)
    except (TypeError, ValueError):
        return 0


def _need(db, user: User) -> int:
    lim = limit_of(db, user)
    if lim <= 0:
        raise HTTPException(402, {"message": "The practitioner workspace is not enabled for your account. "
                                             "Contact us to add it to your subscription.", "code": "UPGRADE",
                                  "plan": "ENTERPRISE", "plan_name": "Practitioner add-on"})
    return lim


def _client(db, user: User, cid: str) -> PracticeClient:
    c = db.get(PracticeClient, cid)
    if c is None or c.account_id != user.id:
        raise HTTPException(404, "Client not found")
    return c


def _file(db, user: User, fid: str) -> tuple[PracticeFile, PracticeClient]:
    f = db.get(PracticeFile, fid)
    if f is None:
        raise HTTPException(404, "File not found")
    return f, _client(db, user, f.client_id)


def _c_out(c: PracticeClient, files: list[PracticeFile] | None = None) -> dict:
    return dict(id=c.id, name=c.name, entity_type=c.entity_type, pan=c.pan, gstin=c.gstin, address=c.address, phone=c.phone,
                email=c.email, nature_of_business=c.nature_of_business, linked_business_id=c.linked_business_id, notes=c.notes,
                created_at=c.created_at, updated_at=c.updated_at,
                files=[dict(id=f.id, fy=f.fy, status=f.status, version=f.version, updated_at=f.updated_at) for f in files] if files is not None else None)


def _f_out(f: PracticeFile, c: PracticeClient) -> dict:
    return dict(id=f.id, fy=f.fy, status=f.status, source=f.source, version=f.version, data=f.data,
                finalized_at=f.finalized_at, finalized_by=f.finalized_by, updated_at=f.updated_at, client=_c_out(c))


# ---------------------------------------------------------------- status & clients
@router.get("/status")
def status(db: DB, user: CurrentUser):
    lim = limit_of(db, user)
    used = db.scalar(select(func.count()).select_from(PracticeClient).where(PracticeClient.account_id == user.id)) or 0
    db.commit()
    return {"enabled": lim > 0, "limit": lim, "used": used}


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    entity_type: Literal["PROPRIETORSHIP", "PARTNERSHIP"] = "PROPRIETORSHIP"
    pan: str | None = Field(None, pattern=r"^[A-Za-z]{5}\d{4}[A-Za-z]$")
    gstin: str | None = Field(None, max_length=15)
    address: str | None = Field(None, max_length=1000)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=200)
    nature_of_business: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=4000)


@router.get("/clients")
def list_clients(db: DB, user: CurrentUser, search: str | None = None):
    _need(db, user)
    q = select(PracticeClient).where(PracticeClient.account_id == user.id).order_by(PracticeClient.name)
    if search:
        q = q.where(PracticeClient.name.ilike(f"%{search}%") | PracticeClient.pan.ilike(f"%{search}%"))
    clients = db.scalars(q).all()
    files: dict[str, list] = {}
    if clients:
        for f in db.scalars(select(PracticeFile).where(PracticeFile.client_id.in_([c.id for c in clients])).order_by(PracticeFile.fy.desc())):
            files.setdefault(f.client_id, []).append(f)
    return [_c_out(c, files.get(c.id, [])) for c in clients]


@router.post("/clients", status_code=201)
def create_client(data: ClientIn, db: DB, user: CurrentUser):
    lim = _need(db, user)
    used = db.scalar(select(func.count()).select_from(PracticeClient).where(PracticeClient.account_id == user.id)) or 0
    if used >= lim:
        raise HTTPException(402, {"message": f"Your plan allows {lim} clients. Contact us to add more.", "code": "UPGRADE",
                                  "plan": "ENTERPRISE", "plan_name": "Practitioner add-on"})
    c = PracticeClient(account_id=user.id, **{**data.model_dump(), "pan": data.pan.upper() if data.pan else None,
                                              "gstin": data.gstin.upper() if data.gstin else None})
    db.add(c)
    db.commit()
    return _c_out(c, [])


@router.get("/clients/{cid}")
def get_client(cid: str, db: DB, user: CurrentUser):
    c = _client(db, user, cid)
    files = db.scalars(select(PracticeFile).where(PracticeFile.client_id == c.id).order_by(PracticeFile.fy.desc())).all()
    return _c_out(c, files)


@router.put("/clients/{cid}")
def update_client(cid: str, data: ClientIn, db: DB, user: CurrentUser):
    c = _client(db, user, cid)
    for k, v in data.model_dump().items():
        setattr(c, k, v.upper() if k in ("pan", "gstin") and v else v)
    db.commit()
    return get_client(cid, db, user)


@router.delete("/clients/{cid}", status_code=204)
def delete_client(cid: str, db: DB, user: CurrentUser):
    c = _client(db, user, cid)
    log(db, user, "DELETE", "practice-client", f"Practice client deleted: {c.name}", entity_id=c.id)
    db.delete(c)
    db.commit()


# ---------------------------------------------------------------- yearly files
class FileIn(BaseModel):
    fy: str = Field(pattern=FY_RE)
    carry_forward: bool = True  # previous year's closing figures become comparatives / opening


def _carry(prev: PracticeFile, client: PracticeClient) -> dict:
    """Previous year's figures → comparatives and openings of the new year."""
    d = copy.deepcopy(prev.data or {})
    comp = FA.compute(prev.data or {}, prev.fy, client.name)["cy"]
    ledgers = []
    for l in d.get("ledgers") or []:
        ledgers.append({**l, "id": IO.new_id(), "py": l.get("cy") or "0", "cy": "0"})
    if FA.D((d.get("closing_stock") or {}).get("cy")):
        opening = next((l for l in ledgers if l.get("head") == "OPENING_STOCK"), None)
        if opening is None:
            ledgers.append({"id": IO.new_id(), "name": "Opening stock", "group": None, "head": "OPENING_STOCK", "partner": None,
                            "cy": d["closing_stock"]["cy"], "py": "0"})
        else:
            opening["cy"] = d["closing_stock"]["cy"]
    dep = d.get("depreciation") or {}
    method = dep.get("method") or "IT"
    rows = comp["dep"]["rows"] if comp["dep"] else []
    assets = []
    if method == "IT":
        # the closing WDV of each block becomes the opening of its first asset line
        closing_by_block = {r["block"]: r["closing"] for r in rows}
        seen: set[str] = set()
        for a in dep.get("assets") or []:
            blk = a.get("block") or "Plant & machinery - general"
            if FA.D(closing_by_block.get(blk)) <= 0 and blk in seen:
                continue
            assets.append({**a, "opening": str(closing_by_block.get(blk, 0)) if blk not in seen else "0",
                           "addition": None, "addition_date": None, "sale": None})
            seen.add(blk)
    else:
        for a, r in zip(dep.get("assets") or [], rows):
            if FA.D(a.get("sale")):
                continue  # sold during the year
            assets.append({**a, "cost": str(FA.D(a.get("cost")) + FA.D(a.get("addition"))),
                           "opening_acc_dep": str(FA.D(a.get("opening_acc_dep")) + r["depreciation"]),
                           "put_to_use": a.get("put_to_use") or a.get("addition_date"),
                           "addition": None, "addition_date": None, "sale": None})
    return dict(entity_type=client.entity_type, ledgers=ledgers,
                closing_stock={"cy": "0", "py": (d.get("closing_stock") or {}).get("cy") or "0"},
                depreciation={"method": method, "assets": assets, "py_amount": str(comp["total_dep"])},
                partners=d.get("partners") or [], py={"ppe": str(comp["ppe"])})


@router.post("/clients/{cid}/files", status_code=201)
def create_file(cid: str, data: FileIn, db: DB, user: CurrentUser):
    _need(db, user)
    c = _client(db, user, cid)
    if db.scalar(select(PracticeFile).where(PracticeFile.client_id == c.id, PracticeFile.fy == data.fy)):
        raise HTTPException(409, f"FY {data.fy} already exists for this client")
    prev_fy = f"{int(data.fy[:4]) - 1}-{data.fy[2:4]}"
    prev = db.scalar(select(PracticeFile).where(PracticeFile.client_id == c.id, PracticeFile.fy == prev_fy))
    body = _carry(prev, c) if prev and data.carry_forward else dict(
        entity_type=c.entity_type, ledgers=[], closing_stock={"cy": "0", "py": "0"},
        depreciation={"method": "IT", "assets": [], "py_amount": "0"}, partners=[], py={})
    f = PracticeFile(client_id=c.id, fy=data.fy, data=body, source="CARRIED" if prev and data.carry_forward else None)
    db.add(f)
    db.commit()
    return _f_out(f, c)


@router.get("/files/{fid}")
def get_file(fid: str, db: DB, user: CurrentUser):
    f, c = _file(db, user, fid)
    return _f_out(f, c)


class DataIn(BaseModel):
    data: dict


def _remember(c: PracticeClient, data: dict) -> None:
    m = dict(c.mappings or {})
    for l in data.get("ledgers") or []:
        if l.get("head") and l.get("name"):
            m[l["name"].strip().lower()] = {"head": l["head"], "partner": l.get("partner")}
    c.mappings = m


def _editable(f: PracticeFile) -> None:
    if f.status == "FINAL":
        raise HTTPException(400, "This year's accounts are finalised — reopen them to make changes")


@router.put("/files/{fid}")
def save_file(fid: str, body: DataIn, db: DB, user: CurrentUser):
    f, c = _file(db, user, fid)
    _editable(f)
    data = body.data
    if len(data.get("ledgers") or []) > 3000:
        raise HTTPException(413, "Too many ledgers")
    data["entity_type"] = c.entity_type
    f.data = data
    f.source = f.source or "MANUAL"
    _remember(c, data)
    db.commit()
    return _f_out(f, c)


@router.get("/files/{fid}/statements")
def statements(fid: str, db: DB, user: CurrentUser):
    f, c = _file(db, user, fid)
    data = {**(f.data or {}), "entity_type": c.entity_type}
    comp = FA.compute(data, f.fy, c.name)
    client = _c_out(c)
    doc = FA.statements_doc(comp, client)
    return {"doc": doc, "checks": comp["checks"], "explain": comp["explain"],
            "summary": {k: comp["cy"][k] for k in ("net_profit", "gross_profit", "total_assets", "capital_closing",
                                                   "tb_difference", "difference", "revenue", "total_dep")},
            "status": f.status, "final_snapshot": f.final_snapshot}


def _apply_mappings(c: PracticeClient, ledgers: list[dict]) -> list[dict]:
    m = c.mappings or {}
    for l in ledgers:
        hit = m.get((l.get("name") or "").strip().lower())
        if hit:
            l["head"], l["partner"] = hit.get("head") or l.get("head"), hit.get("partner")
    return ledgers


def _merge(existing: list[dict], incoming: list[dict], mode: str) -> list[dict]:
    if mode == "replace":
        return incoming
    by = {(l.get("name") or "").strip().lower(): l for l in existing}
    for l in incoming:
        key = (l.get("name") or "").strip().lower()
        if key in by:
            by[key]["cy"], by[key]["py"] = l["cy"], l["py"] if FA.D(l["py"]) else by[key].get("py")
            by[key]["head"] = by[key].get("head") or l.get("head")
        else:
            existing.append(l)
    return existing


@router.post("/files/{fid}/import-tb")
async def import_tb(fid: str, db: DB, user: CurrentUser, file: UploadFile = File(...), mode: str = "replace"):
    f, c = _file(db, user, fid)
    _editable(f)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File is larger than 10 MB")
    try:
        ledgers, warnings = IO.parse_trial_balance(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    data = dict(f.data or {})
    data["ledgers"] = _merge(list(data.get("ledgers") or []), _apply_mappings(c, ledgers), mode)
    f.data, f.source = data, "TRIAL_BALANCE"
    db.commit()
    unmapped = sum(1 for l in data["ledgers"] if not l.get("head"))
    return {"file": _f_out(f, c), "imported": len(ledgers), "unmapped": unmapped, "warnings": warnings}


class BooksIn(BaseModel):
    business_id: str


@router.get("/linkable-businesses")
def linkable(db: DB, user: CurrentUser):
    """Businesses in MyBillSync the practitioner can read (owner, admin or CA / accountant member)."""
    rows = db.execute(select(Business.id, Business.name, Business.gstin, Membership.role).join(
        Membership, Membership.business_id == Business.id).where(Membership.user_id == user.id)).all()
    return [dict(id=i, name=n, gstin=g, role=getattr(r, "value", r)) for i, n, g, r in rows]


@router.post("/files/{fid}/import-books")
def import_books(fid: str, body: BooksIn, db: DB, user: CurrentUser):
    f, c = _file(db, user, fid)
    _editable(f)
    m = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.business_id == body.business_id))
    if m is None:
        raise HTTPException(403, "Ask the business owner to add you as a staff member (CA / Accountant role) first")
    ledgers, stock = IO.books_to_ledgers(db, m.business, f.fy)
    data = dict(f.data or {})
    data["ledgers"] = _apply_mappings(c, ledgers)
    data["closing_stock"] = stock
    f.data, f.source = data, "BOOKS"
    c.linked_business_id = body.business_id
    db.commit()
    return {"file": _f_out(f, c), "imported": len(ledgers)}


@router.get("/tb-template")
def tb_template(user: CurrentUser):
    return Response(IO.template(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="trial-balance-template.xlsx"'})


@router.post("/files/{fid}/finalize")
def finalize(fid: str, db: DB, user: CurrentUser):
    f, c = _file(db, user, fid)
    _editable(f)
    st = statements(fid, db, user)
    if any(ch["level"] == "error" for ch in st["checks"]):
        raise HTTPException(400, "Resolve the errors in the checks before finalising")
    f.status, f.finalized_at, f.finalized_by = "FINAL", dt.datetime.now(dt.UTC), f"{user.name} <{user.email}>"
    f.final_snapshot = {"doc": _jsonable(st["doc"]), "summary": _jsonable(st["summary"])}
    log(db, user, "ACTION", "practice-file", f"Finalised {c.name} FY {f.fy} (v{f.version})", entity_id=f.id)
    db.commit()
    return _f_out(f, c)


@router.post("/files/{fid}/reopen")
def reopen(fid: str, db: DB, user: CurrentUser):
    f, c = _file(db, user, fid)
    if f.status != "FINAL":
        raise HTTPException(400, "Not finalised")
    f.status, f.version = "DRAFT", (f.version or 1) + 1
    log(db, user, "ACTION", "practice-file", f"Reopened {c.name} FY {f.fy} as version {f.version}", entity_id=f.id)
    db.commit()
    return _f_out(f, c)


def _jsonable(o):
    from decimal import Decimal
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_jsonable(v) for v in o]
    return o


@router.get("/heads")
def heads(user: CurrentUser):
    return [dict(code=k, section=v[0], label=v[1], nature=v[2], help=v[3]) for k, v in FA.HEADS.items()]

