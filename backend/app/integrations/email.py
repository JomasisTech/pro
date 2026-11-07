"""Outgoing email for account security messages (password reset).

Delivery is deliberately small and dependency-free (standard-library SMTP). The API depends on the
`send_email` function only, so a hosted provider can replace it later without touching the routes.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings

log = logging.getLogger(__name__)


def send_email(settings: Settings, to_address: str, subject: str, body: str, *, log_body: bool = True) -> bool:
    """Send a plain-text email. Returns True when the message was handed to an SMTP server.

    Never raises: callers run this in a background task after the HTTP response is sent, and a mail
    failure must not change what the requester sees (that would reveal whether an account exists).
    """
    if not settings.smtp_host:
        if settings.app_env.lower() == "production":
            log.error("SMTP_HOST is not configured; email '%s' was not sent", subject)
        else:
            # Development convenience only. Security messages may include links; callers can suppress body logging.
            if log_body:
                log.warning("SMTP not configured; development email to %s\nSubject: %s\n\n%s", to_address, subject, body)
            else:
                log.warning("SMTP not configured; email to %s was not sent (subject: %s)", to_address, subject)
        return False

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError):
        log.exception("Could not send email '%s'", subject)
        return False
