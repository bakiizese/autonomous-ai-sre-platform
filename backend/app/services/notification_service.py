import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmailSubscriber, RemediationRun
from app.services.email_service import send_critical_alert


def notify_subscribers(db: Session, run: RemediationRun) -> None:
    """Fires synchronously at run-completion time — no batching, no queue.
    Everyone watching this repo (or globally, repo_id=NULL) gets alerted off
    the single global settings.CRITICAL_RISK_THRESHOLD; there's no
    per-subscriber override. Since PR creation now waits for human approval,
    run.pr_url is almost always None here — the email links to the dashboard's
    approval view via issue/run identifiers, not a live PR."""
    if run.risk_score is None or run.risk_score <= settings.CRITICAL_RISK_THRESHOLD:
        return

    subscribers = (
        db.query(EmailSubscriber)
        .filter(
            EmailSubscriber.unsubscribed_at.is_(None),
            (EmailSubscriber.repo_id == run.repo_id) | (EmailSubscriber.repo_id.is_(None)),
        )
        .all()
    )
    if not subscribers:
        return

    issue_number = run.issue.issue_number if run.issue is not None else None
    issue_title = run.diagnosis_summary or (f"Issue #{issue_number}" if issue_number else "Untitled issue")

    for subscriber in subscribers:
        send_critical_alert(
            subscriber.email,
            issue_number,
            issue_title,
            run.risk_score,
            run.root_cause_analysis or "",
            run.pr_url,
        )


def seed_admin_subscriber(db: Session) -> None:
    """Preserves the old 'always email the platform owner' behavior — seeds
    one global (repo_id=NULL) subscriber row from ADMIN_ALERT_EMAIL (or its
    deprecated alias ALERT_EMAIL_TO, aliased in config.py) instead of hardcoding
    a single recipient at send time like the old email_service did."""
    if not settings.ADMIN_ALERT_EMAIL:
        return

    existing = (
        db.query(EmailSubscriber)
        .filter_by(email=settings.ADMIN_ALERT_EMAIL, repo_id=None, is_admin_fallback=True)
        .one_or_none()
    )
    if existing is not None:
        return

    db.add(
        EmailSubscriber(
            email=settings.ADMIN_ALERT_EMAIL,
            repo_id=None,
            is_admin_fallback=True,
            unsubscribe_token=secrets.token_urlsafe(24),
        )
    )
    db.commit()


def subscribe(db: Session, email: str, repo_id: int | None) -> EmailSubscriber:
    existing = db.query(EmailSubscriber).filter_by(email=email, repo_id=repo_id).one_or_none()
    if existing is not None:
        if existing.unsubscribed_at is not None:
            existing.unsubscribed_at = None
            db.commit()
        return existing

    subscriber = EmailSubscriber(email=email, repo_id=repo_id, unsubscribe_token=secrets.token_urlsafe(24))
    db.add(subscriber)
    db.commit()
    return subscriber


def unsubscribe(db: Session, token: str) -> bool:
    subscriber = db.query(EmailSubscriber).filter_by(unsubscribe_token=token).one_or_none()
    if subscriber is None:
        return False
    subscriber.unsubscribed_at = datetime.now(timezone.utc)
    db.commit()
    return True
