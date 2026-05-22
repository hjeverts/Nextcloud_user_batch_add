# Nextcloud User Batch Add

A Python web application (Dash) that lets you add many Nextcloud accounts at
once from a CSV file.  For every user it will:

- **Generate** a cryptographically-secure random password
- **Create** the account via the Nextcloud OCS Provisioning API
- **Request** a password change on first login (`nextLoginPasswordChange`; support depends on your Nextcloud setup)
- **Send** a welcome e-mail with the login credentials via SMTP

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in the configuration
cp .env.example .env
$EDITOR .env

# 3. Run the app
python app.py
```

Then open **http://localhost:8050** in your browser.

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `NC_URL` | Nextcloud server URL, e.g. `https://cloud.example.com` |
| `NC_ADMIN_USER` | Nextcloud admin username |
| `NC_ADMIN_PASS` | Nextcloud admin password |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP port (default `587`) |
| `SMTP_SECURITY` | SMTP security mode: `auto`, `starttls`, or `ssl` (default `auto`) |
| `SMTP_USER` | SMTP login username (leave blank if no auth) |
| `SMTP_PASSWORD` | SMTP login password |
| `SMTP_FROM` | From address for outgoing e-mails |
| `HOST` | Interface to bind to (default `127.0.0.1`; use `0.0.0.0` for LAN access) |
| `PORT` | Port to listen on (default `8050`) |

If `SMTP_SECURITY=auto`, the app uses SSL/TLS for port `465` and STARTTLS for
other ports. Legacy `SMTP_USE_TLS` values are still supported for backwards
compatibility.

All settings can also be entered directly in the browser UI.

## CSV format

| Column | Required | Description |
|---|---|---|
| `username` | ✔ | Nextcloud login name (no spaces) |
| `displayname` | — | Full name of the user |
| `email` | ✔ | Email address — receives the welcome message |
| `groups` | — | Semicolon-separated list of groups, e.g. `staff;it` |

A sample file is available at `assets/sample_users.csv` and can also be
downloaded directly from the web UI.

## Project structure

```
app.py               Main Dash application
nextcloud.py         Nextcloud OCS API wrapper (create user, force password change)
email_utils.py       SMTP e-mail helper
requirements.txt     Python dependencies
.env.example         Configuration template
assets/
  sample_users.csv   Sample CSV to get started
```
