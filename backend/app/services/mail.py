import logging
import smtplib
import threading
from email.message import EmailMessage
from ..core.config import MAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

log = logging.getLogger("techdesk.mail")
sent = []

def configured():
    return bool(SMTP_HOST and MAIL_FROM)

def deliver(message):
    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()
        with server:
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
    except Exception:
        log.exception("Не вдалося надіслати лист на %s", message["To"])

def send(to, subject, text):
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = f"TechDesk <{MAIL_FROM}>", to, subject
    message.set_content(text)
    sent.append(message)
    if not configured():
        log.warning("SMTP не налаштовано. Лист для %s: %s\n%s", to, subject, text)
        return
    threading.Thread(target=deliver, args=(message,), daemon=True).start()
