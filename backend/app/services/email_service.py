import smtplib
import logging
from email.mime.text import MIMEText
from app.core.config import settings

logger = logging.getLogger("sre_pipeline")


def send_critical_alert(
    to_email: str,
    issue_number: int,
    issue_title: str,
    risk_score: int,
    root_cause: str,
    pr_url: str | None = None,
) -> None:
    """Sends a synchronous SMTP email alert for critical-risk issues. Blocking — call via run_in_threadpool.
    Always sends from the platform's own configured SMTP address (settings.SMTP_USER /
    ALERT_EMAIL_FROM) — to_email is just the recipient, not a per-subscriber mail config."""
    if not settings.SMTP_HOST or not to_email:
        logger.warning("Email alert skipped: SMTP_HOST not configured or no recipient given.")
        return

    from_addr = settings.ALERT_EMAIL_FROM or settings.SMTP_USER

    pr_line = (
        f"Pull request: {pr_url}"
        if pr_url
        else "No pull request was opened yet (sandbox verification may have failed, or it's still awaiting human approval)."
    )

    body = f"""Critical issue detected and auto-triaged by Sentinel SRE.

Issue: #{issue_number} - {issue_title}
Risk score: {risk_score}/10

Root cause:
{root_cause}

{pr_line}
"""

    msg = MIMEText(body)
    msg["Subject"] = (
        f"[Sentinel SRE] Critical issue #{issue_number} (risk {risk_score}/10)"
    )
    msg["From"] = from_addr
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(from_addr, [to_email], msg.as_string())
        logger.info(f"📧 Critical alert email sent for issue #{issue_number}")
    except Exception as e:
        logger.error(f"⚠️ Failed to send critical alert email: {e}")
