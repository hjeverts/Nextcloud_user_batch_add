"""
email_utils.py — Send welcome e-mails with Nextcloud login credentials.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_welcome_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    use_starttls: bool,
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
  <p>Dear {name},</p>
  <p>Your Nextcloud account has been created.
     Please find your login credentials below:</p>
  <table style="border-collapse: collapse; margin: 12px 0;">
    <tr>
      <td style="padding: 4px 12px 4px 0; font-weight: bold;">Server</td>
      <td style="padding: 4px 0;">
        <a href="{nextcloud_url}">{nextcloud_url}</a>
      </td>
    </tr>
    <tr>
      <td style="padding: 4px 12px 4px 0; font-weight: bold;">Username</td>
      <td style="padding: 4px 0;">{username}</td>
    </tr>
    <tr>
      <td style="padding: 4px 12px 4px 0; font-weight: bold;">Password</td>
      <td style="padding: 4px 0;
                 font-family: monospace; font-size: 1.05em;">{password}</td>
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
        if use_starttls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)

        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return {"success": True, "message": f"Email sent to {to_email}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": str(exc)}
