import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.core.settings import settings
import logging

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Envia um email via SMTP."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("Credenciais SMTP não configuradas. Email não enviado.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            if settings.SMTP_STARTTLS:
                server.starttls()
                server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())

        logger.info(f"Email enviado para {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar email para {to_email}: {e}")
        return False


def send_password_reset_email(user_email: str, user_name: str, reset_token: str) -> bool:
    """Envia email de redefinição de senha."""
    reset_url = f"{settings.FRONTEND_URL}/redefinir-senha?token={reset_token}"
    subject = "Redefinição de Senha - O Toque de Mulher"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto;">
        <div style="background: linear-gradient(135deg, #c0392b, #8e44ad); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">O Toque de Mulher</h1>
        </div>
        <div style="padding: 30px;">
            <h2>Olá, {user_name.split()[0]}!</h2>
            <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
            <p>Clique no botão abaixo para criar uma nova senha. Este link é válido por <strong>1 hora</strong>.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}"
                   style="background: #c0392b; color: white; padding: 15px 30px;
                          text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Redefinir Senha
                </a>
            </div>
            <p style="color: #666; font-size: 12px;">
                Se você não solicitou a redefinição de senha, ignore este email.
                Sua senha permanecerá a mesma.
            </p>
        </div>
    </body>
    </html>
    """
    return send_email(user_email, subject, html_body)
