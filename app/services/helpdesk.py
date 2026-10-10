"""Helpdesk: tickets raised from inside the app (issue, question, feedback, feature request, billing) and handled by the
company team in Admin → Helpdesk. Who gets what alert:

- new ticket → the team it is routed to (billing → Finance, feature requests → Technical, the rest → Support), plus the
  super admins; if nobody is in that team yet, everyone with the helpdesk area
- assigned → the assignee
- team reply / resolved → the person who raised it (bell + e-mail)
- the person replies → the assignee, else the team
Internal notes are never shown to the person who raised the ticket.
"""

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..gst.constants import PlatformRole
from ..models import Business, Ticket, TicketAttachment, TicketMessage, User
from . import notify, platform_team

CATEGORIES = {"ISSUE": "Something is not working", "QUESTION": "Question / how do I", "FEEDBACK": "Feedback",
              "FEATURE": "New feature / requirement", "BILLING": "Billing & subscription"}
ROUTE = {"BILLING": "FINANCE", "FEATURE": "TECH"}
PRIORITIES = ["LOW", "NORMAL", "HIGH", "URGENT"]
STATUSES = {"OPEN": "Open", "IN_PROGRESS": "In progress", "WAITING": "Waiting for you", "RESOLVED": "Resolved", "CLOSED": "Closed"}
TEAM_STATUS_LABEL = {**STATUSES, "WAITING": "Waiting for customer"}
MAX_FILE = 5 * 1024 * 1024
FILE_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif", "application/pdf", "text/plain", "text/csv",
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def code(t: Ticket) -> str:
    return f"T-{t.number}"


def next_number(db: Session) -> int:
    return (db.scalar(select(func.max(Ticket.number))) or 1000) + 1


def user_link(t: Ticket) -> str:
    return f"/support?t={t.id}"


def team_link(t: Ticket) -> str:
    return f"/admin?tab=Helpdesk&id={t.id}"


def agents(db: Session) -> list[User]:
    return platform_team.members(db, "helpdesk")


def _routed(db: Session, t: Ticket) -> list[User]:
    everyone = agents(db)
    team = [u for u in everyone if u.platform_role == PlatformRole.TEAM.value and u.platform_team in (t.team, "ADMIN")]
    if not [u for u in team if u.platform_team == t.team]:
        return everyone
    return team + [u for u in everyone if u.platform_role != PlatformRole.TEAM.value]


def summary(db: Session, t: Ticket, for_team: bool) -> dict:
    who = db.get(User, t.user_id)
    agent = db.get(User, t.assigned_to) if t.assigned_to else None
    biz = db.get(Business, t.business_id) if t.business_id else None
    out = dict(id=t.id, code=code(t), number=t.number, category=t.category, category_label=CATEGORIES.get(t.category, t.category),
               subject=t.subject, priority=t.priority, status=t.status,
               status_label=(TEAM_STATUS_LABEL if for_team else STATUSES).get(t.status, t.status),
               team=t.team, module=t.module, page=t.page, created_at=t.created_at, last_activity_at=t.last_activity_at,
               first_response_at=t.first_response_at, resolved_at=t.resolved_at, rating=t.rating, rating_note=t.rating_note,
               business_name=biz.name if biz else None, assigned_name=agent.name if agent else None)
    if for_team:
        out.update(assigned_to=t.assigned_to, device=t.device, user_id=t.user_id, user_name=who.name if who else None,
                   user_email=who.email if who else None, user_phone=(who.mobile or who.phone) if who else None,
                   business_id=t.business_id)
    return out


def detail(db: Session, t: Ticket, for_team: bool) -> dict:
    q = select(TicketMessage).where(TicketMessage.ticket_id == t.id)
    if not for_team:
        q = q.where(TicketMessage.internal.is_(False))
    msgs = db.scalars(q.order_by(TicketMessage.created_at)).all()
    files = db.scalars(select(TicketAttachment).where(TicketAttachment.ticket_id == t.id).order_by(TicketAttachment.created_at)).all()
    shown = {m.id for m in msgs}
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_({m.author_id for m in msgs if m.author_id}))).all()}
    return {**summary(db, t, for_team),
            "messages": [dict(id=m.id, body=m.body, by_team=m.by_team, internal=m.internal, created_at=m.created_at,
                              author=(names.get(m.author_id) or "Support team") if (for_team or not m.by_team) else "Support team",
                              files=[dict(id=f.id, name=f.name, size=f.size, content_type=f.content_type) for f in files if f.message_id == m.id])
                         for m in msgs],
            "files": [dict(id=f.id, name=f.name, size=f.size, content_type=f.content_type, created_at=f.created_at)
                      for f in files if not f.message_id or f.message_id in shown]}


def create(db: Session, user: User, business_id: str | None, category: str, subject: str, body: str, priority: str,
           module: str | None, page: str | None, device: str | None) -> Ticket:
    t = Ticket(number=next_number(db), user_id=user.id, business_id=business_id, category=category, subject=subject.strip(),
               priority=priority, status="OPEN", team=ROUTE.get(category, "SUPPORT"), module=module, page=page, device=device)
    db.add(t)
    db.flush()
    db.add(TicketMessage(ticket_id=t.id, author_id=user.id, by_team=False, body=body.strip()))
    biz = db.get(Business, business_id) if business_id else None
    notify.users(db, _routed(db, t), "TICKET_NEW", f"New ticket {code(t)}: {t.subject}",
                 f"{user.name} ({user.email}){' · ' + biz.name if biz else ''} — {CATEGORIES[category]}, {priority.lower()} priority"
                 f"{' · raised from ' + module if module else ''}.\n{body.strip()[:400]}", link=team_link(t))
    notify.queue_mail(db, [user.email], f"We received your request {code(t)}: {t.subject}", notify.email_html(
        f"We received your request {code(t)}",
        f"Hello {user.name},\nThank you for writing to us. Our team will reply here and by e-mail.\n“{t.subject}”",
        user_link(t), "View your ticket"))
    return t


def add_files(db: Session, t: Ticket, message_id: str | None, by: User, files: list[tuple[str, str, bytes]]) -> None:
    if db.scalar(select(func.count(TicketAttachment.id)).where(TicketAttachment.ticket_id == t.id)) + len(files) > 20:
        raise HTTPException(400, "A ticket can have at most 20 files")
    for name, ctype, data in files:
        if ctype not in FILE_TYPES:
            raise HTTPException(400, f"{name}: only images, PDF, text, CSV or Excel files can be attached")
        if len(data) > MAX_FILE:
            raise HTTPException(400, f"{name} is larger than 5 MB")
        db.add(TicketAttachment(ticket_id=t.id, message_id=message_id, uploaded_by=by.id, name=name[:200] or "file",
                                content_type=ctype, size=len(data), data=data))


def user_reply(db: Session, t: Ticket, user: User, body: str) -> TicketMessage:
    if t.status == "CLOSED":
        raise HTTPException(400, "This ticket is closed — reopen it to reply")
    m = TicketMessage(ticket_id=t.id, author_id=user.id, by_team=False, body=body.strip())
    db.add(m)
    if t.status in ("WAITING", "RESOLVED"):
        t.status, t.resolved_at = "OPEN", None
    t.last_activity_at = now()
    to = [db.get(User, t.assigned_to)] if t.assigned_to else _routed(db, t)
    notify.users(db, [u for u in to if u], "TICKET_REPLY", f"{code(t)}: reply from {user.name}", body.strip()[:500], link=team_link(t))
    db.flush()
    return m


def team_reply(db: Session, t: Ticket, agent: User, body: str, internal: bool, status: str | None) -> TicketMessage:
    m = TicketMessage(ticket_id=t.id, author_id=agent.id, by_team=True, internal=internal, body=body.strip())
    db.add(m)
    t.last_activity_at = now()
    if not internal:
        t.first_response_at = t.first_response_at or now()
        if not t.assigned_to:
            t.assigned_to = agent.id
        if status is None and t.status == "OPEN":
            status = "IN_PROGRESS"
    if status:
        set_status(db, t, agent, status, notify_user=False)
    if not internal:
        who = db.get(User, t.user_id)
        resolved = t.status == "RESOLVED"
        notify.users(db, [who], "TICKET_RESOLVED" if resolved else "TICKET_REPLY",
                     f"{code(t)} {'resolved' if resolved else 'has a reply from support'}: {t.subject}",
                     body.strip()[:1500] + ("\n\nIf this did not fix it, just reply and the ticket opens again." if resolved else ""),
                     link=user_link(t))
    db.flush()
    return m


def set_status(db: Session, t: Ticket, actor: User, status: str, notify_user: bool = True) -> None:
    if status not in STATUSES:
        raise HTTPException(422, "Unknown status")
    if status == t.status:
        return
    t.status = status
    t.resolved_at = now() if status in ("RESOLVED", "CLOSED") else None
    t.last_activity_at = now()
    if notify_user and status == "RESOLVED" and actor.id != t.user_id:
        notify.users(db, [db.get(User, t.user_id)], "TICKET_RESOLVED", f"{code(t)} resolved: {t.subject}",
                     "Our team has marked your ticket as resolved. If anything is still wrong, reply and it opens again.",
                     link=user_link(t))


def assign(db: Session, t: Ticket, actor: User, agent_id: str | None) -> None:
    if agent_id == t.assigned_to:
        return
    if agent_id:
        agent = db.get(User, agent_id)
        if not agent or not platform_team.has_area(agent, "helpdesk"):
            raise HTTPException(400, "That person does not work in the helpdesk")
        if agent.id != actor.id:
            notify.users(db, [agent], "TICKET_ASSIGNED", f"{code(t)} assigned to you: {t.subject}",
                         f"{actor.name} assigned you this {CATEGORIES.get(t.category, '').lower()} ticket ({t.priority.lower()} priority).",
                         link=team_link(t))
    t.assigned_to = agent_id
    t.last_activity_at = now()
