"""Отправка писем: подтверждение почты и сброс пароля.

Если SMTP_HOST не задан (локальная разработка), письмо не отправляется,
а печатается в консоль сервера вместе со ссылкой - по ней можно перейти руками.
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("phishdet.mail")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "PhishDet <no-reply@phishdet.ru>")
# ssl - порт 465, starttls - порт 587, none - без шифрования (только локально)
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "starttls").lower()


def send_email(to: str, subject: str, text: str) -> None:
    if not SMTP_HOST:
        # Без SMTP письмо идёт в консоль. print, а не logger: uvicorn по умолчанию
        # не показывает INFO-логи приложения, а ссылка нужна разработчику.
        print(f"\n--- Письмо (SMTP не настроен) ---\nКому: {to}\nТема: {subject}\n\n{text}\n---------------------------------\n",
              flush=True)
        return

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)

    try:
        if SMTP_SECURITY == "ssl":
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context(), timeout=15) as smtp:
                _login_and_send(smtp, msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
                if SMTP_SECURITY == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                _login_and_send(smtp, msg)
    except Exception:
        # Письмо уходит в фоне после ответа клиенту, поэтому ошибку только логируем
        logger.exception("Не удалось отправить письмо на %s", to)


def _login_and_send(smtp: smtplib.SMTP, msg: EmailMessage) -> None:
    if SMTP_USER:
        smtp.login(SMTP_USER, SMTP_PASSWORD)
    smtp.send_message(msg)


def send_verification_email(to: str, link: str) -> None:
    send_email(
        to,
        "Подтвердите почту - PhishDet",
        "Здравствуйте!\n\n"
        "Чтобы подтвердить почту и получить 3 бесплатные проверки, перейдите по ссылке:\n"
        f"{link}\n\n"
        "Ссылка действует 24 часа. Если вы не регистрировались в PhishDet, просто удалите это письмо.\n",
    )


def send_password_reset_email(to: str, link: str) -> None:
    send_email(
        to,
        "Сброс пароля - PhishDet",
        "Здравствуйте!\n\n"
        "Кто-то (надеемся, вы) запросил сброс пароля в PhishDet. Задать новый пароль:\n"
        f"{link}\n\n"
        "Ссылка действует 1 час и срабатывает один раз. "
        "Если вы не запрашивали сброс, ничего делать не нужно - пароль останется прежним.\n",
    )
