"""Alerts: a row under the bell for each person, and usually the same alert by e-mail.

E-mails are queued on the database session and sent only after the commit, so a rolled-back action never e-mails
anyone, and a mail problem (no sender set up, provider down) never stops the action that caused the alert.
"""

import html
import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Notification, User
from . import mailer, platform_team

log = logging.getLogger(__name__)


def _abs(link: str | None) -> str | None:
    if not link:
        return None
    base = (get_settings().app_url or "").rstrip("/")
    return f"{base}{link}" if base and link.startswith("/") else link


def email_html(title: str, body: str, link: str | None = None, button: str = "Open") -> str:
    paras = "".join(f"<p>{html.escape(line)}</p>" for line in body.split("\n") if line.strip())
    url = _abs(link)
    btn = (f'<p><a href="{html.escape(url)}" style="background:#4f46e5;color:#fff;padding:9px 16px;border-radius:6px;'
           f'text-decoration:none;display:inline-block">{html.escape(button)}</a></p>') if url and url.startswith("http") else ""
    return mailer.layout(html.escape(title), paras + btn)


def queue_mail(db: Session, to: list[str], subject: str, html_body: str, cfg: mailer.Smtp | None = None) -> None:
    """Send after the commit (see module note). cfg defaults to the platform sender."""
    cfg = cfg or mailer.system_smtp(db)
    to = [t for t in dict.fromkeys(to) if t]
    if cfg is None or not to:
        return
    db.info.setdefault("mail_queue", []).append((cfg, to, subject, html_body))


def users(db: Session, people: list[User], kind: str, title: str, body: str = "", link: str | None = None,
          email: bool = True, email_subject: str | None = None) -> None:
    """Bell alert for each person (once each); e-mail them too unless email=False."""
    seen: set[str] = set()
    for u in people:
        if not u or u.id in seen:
            continue
        seen.add(u.id)
        db.add(Notification(user_id=u.id, kind=kind, title=title[:200], body=body or None, link=link))
        if email and u.email:
            queue_mail(db, [u.email], email_subject or title, email_html(title, body, link))


def team(db: Session, area: str, kind: str, title: str, body: str = "", link: str | None = None, email: bool = True,
         exclude: str | None = None) -> None:
    """Alert the super admins and the team members who work in this admin area."""
    users(db, [u for u in platform_team.members(db, area) if u.id != exclude], kind, title, body, link, email)


@event.listens_for(Session, "after_commit")
def _send_queued(session: Session) -> None:
    for cfg, to, subject, body in session.info.pop("mail_queue", []):
        try:
            mailer.send(cfg, to, subject, body)
        except Exception as e:  # noqa: BLE001 — an alert e-mail must never break the action
            log.warning("Alert e-mail to %s not sent: %s", to, getattr(e, "detail", e))


@event.listens_for(Session, "after_rollback")
def _drop_queued(session: Session) -> None:
    session.info.pop("mail_queue", None)
