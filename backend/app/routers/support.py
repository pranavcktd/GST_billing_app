"""Help & support for signed-in users: raise a ticket from any screen, follow the replies, reply, close or rate it.
See services/helpdesk.py. The team side is routers/helpdesk.py."""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import DB, CurrentUser
from ..models import Membership, Ticket, TicketAttachment, TicketMessage
from ..services import helpdesk as HD
from ..services import platform_team

router = APIRouter(prefix="/support", tags=["support"])


def _mine(db, user, ticket_id: str) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Ticket not found")
    return t


async def _read(files: list[UploadFile] | None) -> list[tuple[str, str, bytes]]:
    out = []
    for f in files or []:
        if f.filename:
            data = await f.read(HD.MAX_FILE + 1)
            out.append((f.filename, (f.content_type or "application/octet-stream").split(";")[0], data))
    if len(out) > 5:
        raise HTTPException(400, "Attach at most 5 files at a time")
    return out


@router.get("/meta")
def meta():
    return {"categories": HD.CATEGORIES, "priorities": HD.PRIORITIES, "statuses": HD.STATUSES, "max_mb": HD.MAX_FILE // 1024 // 1024}


@router.post("/tickets", status_code=201)
async def raise_ticket(db: DB, user: CurrentUser,
                       category: Annotated[Literal["ISSUE", "QUESTION", "FEEDBACK", "FEATURE", "BILLING"], Form()],
                       subject: Annotated[str, Form(min_length=3, max_length=200)],
                       body: Annotated[str, Form(min_length=5, max_length=10000)],
                       priority: Annotated[Literal["LOW", "NORMAL", "HIGH", "URGENT"], Form()] = "NORMAL",
                       module: Annotated[str | None, Form(max_length=80)] = None,
                       page: Annotated[str | None, Form(max_length=300)] = None,
                       files: Annotated[list[UploadFile] | None, File()] = None,
                       x_business_id: Annotated[str | None, Header()] = None,
                       user_agent: Annotated[str | None, Header()] = None):
    """Raise a ticket (multipart form so screenshots can come along). The business is taken from the screen the person
    is on, if they belong to it."""
    business_id = None
    if x_business_id and db.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.business_id == x_business_id)):
        business_id = x_business_id
    open_count = db.scalar(select(Ticket.id).where(Ticket.user_id == user.id, Ticket.status.in_(["OPEN", "IN_PROGRESS", "WAITING"]))
                           .offset(49).limit(1))
    if open_count:
        raise HTTPException(429, "You have many open tickets — please wait for replies on those first")
    uploads = await _read(files)
    t = HD.create(db, user, business_id, category, subject, body, priority, module, page, (user_agent or "")[:300] or None)
    first = db.scalar(select(TicketMessage.id).where(TicketMessage.ticket_id == t.id))
    HD.add_files(db, t, first, user, uploads)
    db.commit()
    return HD.summary(db, t, for_team=False)


@router.get("/tickets")
def my_tickets(db: DB, user: CurrentUser):
    rows = db.scalars(select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.last_activity_at.desc()).limit(200)).all()
    return [HD.summary(db, t, for_team=False) for t in rows]


@router.get("/tickets/{ticket_id}")
def my_ticket(ticket_id: str, db: DB, user: CurrentUser):
    return HD.detail(db, _mine(db, user, ticket_id), for_team=False)


@router.post("/tickets/{ticket_id}/messages")
async def reply(ticket_id: str, db: DB, user: CurrentUser, body: Annotated[str, Form(min_length=1, max_length=10000)],
                files: Annotated[list[UploadFile] | None, File()] = None):
    t = _mine(db, user, ticket_id)
    uploads = await _read(files)
    m = HD.user_reply(db, t, user, body)
    HD.add_files(db, t, m.id, user, uploads)
    db.commit()
    return HD.detail(db, t, for_team=False)


class StateIn(BaseModel):
    action: Literal["close", "reopen"]


@router.post("/tickets/{ticket_id}/state")
def change_state(ticket_id: str, data: StateIn, db: DB, user: CurrentUser):
    t = _mine(db, user, ticket_id)
    HD.set_status(db, t, user, "CLOSED" if data.action == "close" else "OPEN")
    db.commit()
    return HD.detail(db, t, for_team=False)


class RateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    note: str | None = Field(None, max_length=300)


@router.post("/tickets/{ticket_id}/rate")
def rate(ticket_id: str, data: RateIn, db: DB, user: CurrentUser):
    t = _mine(db, user, ticket_id)
    if t.status not in ("RESOLVED", "CLOSED"):
        raise HTTPException(400, "You can rate the help once the ticket is resolved")
    t.rating, t.rating_note = data.rating, (data.note or "").strip() or None
    db.commit()
    return HD.detail(db, t, for_team=False)


@router.get("/files/{file_id}")
def download(file_id: str, db: DB, user: CurrentUser):
    f = db.get(TicketAttachment, file_id)
    t = db.get(Ticket, f.ticket_id) if f else None
    team = platform_team.has_area(user, "helpdesk")
    if not t or not (team or t.user_id == user.id):
        raise HTTPException(404, "File not found")
    if not team and f.message_id:  # files of internal notes stay with the team
        m = db.get(TicketMessage, f.message_id)
        if m and m.internal:
            raise HTTPException(404, "File not found")
    safe = f.name.replace('"', "")
    return Response(f.data, media_type=f.content_type, headers={"Content-Disposition": f'inline; filename="{safe}"',
                                                                 "X-Content-Type-Options": "nosniff"})
