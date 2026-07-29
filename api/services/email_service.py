"""Email sending via SMTP (mirrors Vigilyx email_service.py).

If SMTP is not configured, runs in DRY-RUN: the message is logged and reported as
sent so the whole alert flow is testable locally without credentials.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.FROM_EMAIL)


def send_email(to: str, subject: str, body: str, html: str | None = None) -> tuple[bool, str]:
    """Send an email. Returns (ok, detail)."""
    if not is_configured():
        logger.info("[email dry-run] to=%s subject=%r\n%s", to, subject, body)
        return True, "dry-run (SMTP non configuré — message journalisé)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)
        logger.info("Email sent to %s (%r)", to, subject)
        return True, "sent"
    except Exception as exc:  # noqa: BLE001
        logger.error("Email send failed to %s: %s", to, exc)
        return False, f"erreur SMTP: {exc}"
