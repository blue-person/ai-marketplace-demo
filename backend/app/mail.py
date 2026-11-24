"""Sends email. In the template every message goes to Mailpit (http://localhost:8025)."""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)


def send(recipient: str, subject: str, body: str) -> bool:
    message = EmailMessage()
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=5) as smtp:
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        log.exception("Could not send email '%s'", subject)
        return False
