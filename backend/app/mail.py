# Import libraries
import logging
import smtplib
from email.message import EmailMessage
from flask import current_app

# Log singleton
log = logging.getLogger(__name__)


# Send a plain text email through SMTP
def send(recipient: str, subject: str, body: str) -> bool:
	message = EmailMessage()
	message["From"] = current_app.config["MAIL_FROM"]
	message["To"] = recipient
	message["Subject"] = subject
	message.set_content(body)

	# Log the failure and return False instead of stopping the request
	try:
		with smtplib.SMTP(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=5) as smtp:
			smtp.send_message(message)
		return True
	except (OSError, smtplib.SMTPException):
		log.exception("Could not send email '%s'", subject)
		return False
