"""
email_utils.py — Send welcome e-mails with Nextcloud login credentials.
"""

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_SMTP_TIMEOUT = 30  # seconds


def _resolve_security_mode(security_mode: str | None, smtp_port: int) -> str:
    """Return the SMTP security mode to use."""
    mode = (security_mode or "auto").strip().lower()
    if mode == "auto":
        return "ssl" if smtp_port == 465 else "starttls"
    if mode in {"starttls", "ssl"}:
        return mode
    return "starttls"


def send_welcome_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    security_mode: str,
    from_email: str,
    to_email: str,
    username: str,
    password: str,
    nextcloud_url: str,
    display_name: str = "",
) -> dict:
    """Send a welcome e-mail containing the generated Nextcloud credentials.

    Returns a dict with keys ``success`` (bool) and ``message`` (str).
    """
    name = display_name.strip() or username
    resolved_security_mode = _resolve_security_mode(security_mode, smtp_port)
    safe_name = html.escape(name)
    safe_nextcloud_url = html.escape(nextcloud_url, quote=True)
    safe_username = html.escape(username)
    safe_password = html.escape(password)

    subject = "Your Nextcloud Account Has Been Created"

    text_body = (
        f"Dear {name},\n\n"
        "Your Nextcloud account has been created. "
        "Please find your login credentials below:\n\n"
        f"  Server:   {nextcloud_url}\n"
        f"  Username: {username}\n"
        f"  Password: {password}\n\n"
        "IMPORTANT: You will be required to change your password on first login.\n\n"
        "Please keep your credentials safe and do not share them with anyone.\n\n"
        "Best regards,\n"
        "Nextcloud Administrator"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
  <p>Dear {safe_name},</p>
  <p>Your Nextcloud account has been created.
     Please find your login credentials below:</p>
  <table style="border-collapse: collapse; margin: 12px 0;">
    <tr>
      <td style="padding: 4px 12px 4px 0; font-weight: bold;">Server</td>
      <td style="padding: 4px 0;">
        <a href="{safe_nextcloud_url}">{safe_nextcloud_url}</a>
      </td>
    </tr>
    <tr>
      <td style="padding: 4px 12px 4px 0; font-weight: bold;">Username</td>
      <td style="padding: 4px 0;">{safe_username}</td>
    </tr>
    <tr>
      <td style="padding: 4px 12px 4px 0; font-weight: bold;">Password</td>
      <td style="padding: 4px 0;
                 font-family: monospace; font-size: 1.05em;">{safe_password}</td>
    </tr>
  </table>
  <p style="color: #c0392b; font-weight: bold;">
    &#9888; You will be required to change your password on first login.
  </p>
  <p>Please keep your credentials safe and do not share them with anyone.</p>
  <br>
  <p>Best regards,<br>Nextcloud Administrator</p>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if resolved_security_mode == "starttls":
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=_SMTP_TIMEOUT)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=_SMTP_TIMEOUT)
    except (ConnectionRefusedError, OSError, smtplib.SMTPConnectError) as exc:
        security_label = "STARTTLS" if resolved_security_mode == "starttls" else "SSL/TLS"
        return {
            "success": False,
            "message": (
                f"SMTP connection failed using {security_label} "
                f"({smtp_host}:{smtp_port}): {exc}"
            ),
        }

    try:
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
    except smtplib.SMTPAuthenticationError as exc:
        server.quit()
        return {
            "success": False,
            "message": f"SMTP authentication rejected for '{smtp_user}': {exc}",
        }

    try:
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return {"success": True, "message": f"Email sent to {to_email}"}
    except smtplib.SMTPRecipientsRefused as exc:
        return {
            "success": False,
            "message": f"Recipient address rejected by server ({to_email}): {exc}",
        }
    except smtplib.SMTPException as exc:
        return {"success": False, "message": f"Email send failed: {exc}"}
