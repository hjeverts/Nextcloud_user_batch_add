"""
app.py — Nextcloud User Batch Add

A Dash web application that reads a CSV of users, creates their accounts on a
Nextcloud server via the OCS Provisioning API, and e-mails each user their
generated credentials.

Usage
-----
    pip install -r requirements.txt
    cp .env.example .env          # fill in your settings
    python app.py

Then open http://localhost:8050 in your browser.
"""

import base64
import io
import os
import secrets
import smtplib
import string

import requests

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback, dcc, html
from dotenv import load_dotenv

import dash

from email_utils import send_welcome_email
from nextcloud import create_nextcloud_user

load_dotenv()

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,   # dynamic children inside preview-section
)
app.title = "Nextcloud User Batch Add"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SPECIAL = "!@#$%^&*()"


def _default_smtp_security_mode() -> str:
    """Resolve the default SMTP security mode from the environment."""
    smtp_security = os.getenv("SMTP_SECURITY", "").strip().lower()
    if smtp_security in {"auto", "starttls", "ssl"}:
        return smtp_security

    smtp_use_tls = os.getenv("SMTP_USE_TLS", "").strip().lower()
    if smtp_use_tls:
        return "starttls" if smtp_use_tls != "false" else "ssl"

    return "auto"


def generate_password(length: int = 16) -> str:
    """Return a cryptographically secure random password.

    Guarantees at least one uppercase letter, one lowercase letter, one digit,
    and one special character from ``_SPECIAL``.
    """
    alphabet = string.ascii_letters + string.digits + _SPECIAL
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SPECIAL),
    ] + [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def parse_csv(contents: str, filename: str):
    """Decode a base64-encoded upload and return (DataFrame | None, error | None)."""
    _content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)

    try:
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
    except UnicodeDecodeError:
        return None, (
            "File encoding error: the CSV must be UTF-8 encoded. "
            "Please re-save the file as UTF-8 and try again."
        )
    except (pd.errors.ParserError, ValueError) as exc:
        return None, f"Could not parse CSV file: {exc}"

    # Normalise column names
    df.columns = df.columns.str.strip().str.lower()

    required = {"username", "email"}
    missing = required - set(df.columns)
    if missing:
        return None, f"Missing required column(s): {', '.join(sorted(missing))}"

    # Ensure optional columns exist
    for col in ("displayname", "groups"):
        if col not in df.columns:
            df[col] = ""

    df["username"] = df["username"].astype(str).str.strip()
    df["email"] = df["email"].astype(str).str.strip()
    df["displayname"] = df["displayname"].fillna("").astype(str).str.strip()
    df["groups"] = df["groups"].fillna("").astype(str).str.strip()

    return df, None


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _config_card() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H5("Configuration", className="mb-0")),
            dbc.CardBody(
                dbc.Tabs(
                    [
                        # ---- Nextcloud tab ----
                        dbc.Tab(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Nextcloud URL"),
                                            dbc.Input(
                                                id="nc-url",
                                                placeholder="https://nextcloud.example.com",
                                                value=os.getenv("NC_URL", ""),
                                                type="url",
                                            ),
                                        ],
                                        md=6,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Admin Username"),
                                            dbc.Input(
                                                id="nc-admin-user",
                                                placeholder="admin",
                                                value=os.getenv("NC_ADMIN_USER", ""),
                                            ),
                                        ],
                                        md=3,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Admin Password"),
                                            dbc.Input(
                                                id="nc-admin-pass",
                                                placeholder="••••••••",
                                                value=os.getenv("NC_ADMIN_PASS", ""),
                                                type="password",
                                            ),
                                        ],
                                        md=3,
                                        className="mb-3",
                                    ),
                                ],
                                className="mt-3",
                            ),
                            label="Nextcloud Server",
                            tab_id="tab-nc",
                        ),
                        # ---- SMTP tab ----
                        dbc.Tab(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("SMTP Host"),
                                            dbc.Input(
                                                id="smtp-host",
                                                placeholder="smtp.example.com",
                                                value=os.getenv("SMTP_HOST", ""),
                                            ),
                                        ],
                                        md=4,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Port"),
                                            dbc.Input(
                                                id="smtp-port",
                                                placeholder="587",
                                                value=os.getenv("SMTP_PORT", "587"),
                                                type="number",
                                                min=1,
                                                max=65535,
                                            ),
                                        ],
                                        md=2,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Security"),
                                            dbc.Select(
                                                id="smtp-security",
                                                options=[
                                                    {"label": "Automatic", "value": "auto"},
                                                    {"label": "STARTTLS", "value": "starttls"},
                                                    {"label": "SSL/TLS", "value": "ssl"},
                                                ],
                                                value=_default_smtp_security_mode(),
                                            ),
                                        ],
                                        md=2,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("SMTP Username"),
                                            dbc.Input(
                                                id="smtp-user",
                                                placeholder="user@example.com",
                                                value=os.getenv("SMTP_USER", ""),
                                            ),
                                        ],
                                        md=4,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("SMTP Password"),
                                            dbc.Input(
                                                id="smtp-password",
                                                placeholder="••••••••",
                                                value=os.getenv("SMTP_PASSWORD", ""),
                                                type="password",
                                            ),
                                        ],
                                        md=4,
                                        className="mb-3",
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("From Email"),
                                            dbc.Input(
                                                id="smtp-from",
                                                placeholder="admin@example.com",
                                                value=os.getenv("SMTP_FROM", ""),
                                            ),
                                        ],
                                        md=4,
                                        className="mb-3",
                                    ),
                                ],
                                className="mt-3",
                            ),
                            label="Email (SMTP)",
                            tab_id="tab-smtp",
                        ),
                    ]
                )
            ),
        ],
        className="mb-4",
    )


def _upload_card() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H5("Upload CSV", className="mb-0")),
            dbc.CardBody(
                [
                    dcc.Upload(
                        id="upload-csv",
                        children=html.Div(
                            [
                                html.I(
                                    className="bi bi-cloud-upload me-2",
                                    style={"fontSize": "1.4rem"},
                                ),
                                "Drag & Drop or ",
                                html.A(
                                    "click to select",
                                    style={"cursor": "pointer"},
                                ),
                                " a CSV file",
                            ]
                        ),
                        style={
                            "width": "100%",
                            "minHeight": "80px",
                            "lineHeight": "80px",
                            "borderWidth": "2px",
                            "borderStyle": "dashed",
                            "borderRadius": "8px",
                            "textAlign": "center",
                            "cursor": "pointer",
                            "backgroundColor": "#f8f9fa",
                        },
                        multiple=False,
                        accept=".csv",
                    ),
                    html.Div(id="upload-status", className="mt-2"),
                    html.Hr(),
                    html.H6("Expected CSV columns"),
                    dbc.Table(
                        [
                            html.Thead(
                                html.Tr(
                                    [
                                        html.Th("Column"),
                                        html.Th("Required"),
                                        html.Th("Description"),
                                    ]
                                )
                            ),
                            html.Tbody(
                                [
                                    html.Tr(
                                        [
                                            html.Td(
                                                html.Code("username"),
                                                style={"whiteSpace": "nowrap"},
                                            ),
                                            html.Td("✔ Yes"),
                                            html.Td(
                                                "Nextcloud login name (no spaces)"
                                            ),
                                        ]
                                    ),
                                    html.Tr(
                                        [
                                            html.Td(html.Code("displayname")),
                                            html.Td("No"),
                                            html.Td("Full name of the user"),
                                        ]
                                    ),
                                    html.Tr(
                                        [
                                            html.Td(html.Code("email")),
                                            html.Td("✔ Yes"),
                                            html.Td(
                                                "Email address — used to send credentials"
                                            ),
                                        ]
                                    ),
                                    html.Tr(
                                        [
                                            html.Td(html.Code("groups")),
                                            html.Td("No"),
                                            html.Td(
                                                "Semicolon-separated list of groups, "
                                                "e.g. group1;group2"
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                        ],
                        bordered=True,
                        size="sm",
                        className="mb-2",
                    ),
                    html.A(
                        [
                            html.I(className="bi bi-download me-1"),
                            "Download sample CSV",
                        ],
                        href="/assets/sample_users.csv",
                        className="btn btn-outline-secondary btn-sm",
                        download="sample_users.csv",
                    ),
                ]
            ),
        ],
        className="mb-4",
    )


# ---------------------------------------------------------------------------
# Full layout
# ---------------------------------------------------------------------------

app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1(
                    [
                        html.I(
                            className="bi bi-person-plus-fill me-2",
                            style={"fontSize": "2rem"},
                        ),
                        "Nextcloud User Batch Add",
                    ],
                    className="text-center my-4",
                )
            )
        ),
        _config_card(),
        _upload_card(),
        # Dynamic section — replaced on every CSV upload
        html.Div(id="preview-section"),
    ],
    fluid=True,
    style={"maxWidth": "1200px"},
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("upload-status", "children"),
    Output("preview-section", "children"),
    Input("upload-csv", "contents"),
    State("upload-csv", "filename"),
    prevent_initial_call=True,
)
def handle_upload(contents, filename):
    """Parse the uploaded CSV and render a preview table + action button."""
    if contents is None:
        return "", ""

    df, error = parse_csv(contents, filename)
    if error:
        return dbc.Alert(error, color="danger", dismissable=True), ""

    status = dbc.Alert(
        [
            html.I(className="bi bi-check-circle me-2"),
            f"Loaded {filename} — {len(df)} user(s) ready to import.",
        ],
        color="success",
        dismissable=True,
    )

    preview_section = dbc.Card(
        [
            dbc.CardHeader(
                html.H5(f"Preview — {len(df)} user(s)", className="mb-0")
            ),
            dbc.CardBody(
                [
                    dag.AgGrid(
                        id="preview-table",
                        rowData=df.to_dict("records"),
                        columnDefs=[
                            {"headerName": c.title(), "field": c}
                            for c in df.columns
                        ],
                        defaultColDef={
                            "resizable": True,
                            "sortable": True,
                            "filter": True,
                        },
                        dashGridOptions={
                            "pagination": True,
                            "paginationPageSize": 10,
                            "paginationPageSizeSelector": [10, 25, 50],
                        },
                        style={"height": "350px"},
                    ),
                    html.Hr(),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    [
                                        html.I(
                                            className="bi bi-people-fill me-2"
                                        ),
                                        "Create Users",
                                    ],
                                    id="create-btn",
                                    color="primary",
                                    size="lg",
                                    n_clicks=0,
                                ),
                                width="auto",
                            ),
                            dbc.Col(
                                dbc.Spinner(
                                    html.Div(id="spinner-placeholder"),
                                    color="primary",
                                    spinner_style={"marginTop": "6px"},
                                ),
                                width="auto",
                            ),
                        ],
                        align="center",
                        className="mt-3",
                    ),
                    # Results appear here after processing
                    html.Div(id="results-div", className="mt-4"),
                ]
            ),
        ],
        className="mb-4",
    )

    return status, preview_section


@callback(
    Output("results-div", "children"),
    Output("spinner-placeholder", "children"),
    Input("create-btn", "n_clicks"),
    # CSV data reconstructed from the preview table
    State("preview-table", "rowData"),
    # Nextcloud config
    State("nc-url", "value"),
    State("nc-admin-user", "value"),
    State("nc-admin-pass", "value"),
    # SMTP config
    State("smtp-host", "value"),
    State("smtp-port", "value"),
    State("smtp-security", "value"),
    State("smtp-user", "value"),
    State("smtp-password", "value"),
    State("smtp-from", "value"),
    prevent_initial_call=True,
)
def process_users(
    n_clicks,
    table_data,
    nc_url,
    nc_admin_user,
    nc_admin_pass,
    smtp_host,
    smtp_port,
    smtp_security,
    smtp_user,
    smtp_password,
    smtp_from,
):
    """Create each user in Nextcloud and send email."""
    if not n_clicks or not table_data:
        return "", ""

    # Validate required Nextcloud settings
    missing_cfg = []
    if not nc_url:
        missing_cfg.append("Nextcloud URL")
    if not nc_admin_user:
        missing_cfg.append("Admin username")
    if not nc_admin_pass:
        missing_cfg.append("Admin password")
    if missing_cfg:
        return (
            dbc.Alert(
                f"Missing configuration: {', '.join(missing_cfg)}",
                color="danger",
            ),
            "",
        )

    smtp_port_int = int(smtp_port) if smtp_port else 587
    smtp_security_mode = (smtp_security or "auto").strip().lower()
    email_enabled = bool(smtp_host and smtp_from)

    results: list[dict] = []

    for row in table_data:
        username = str(row.get("username", "")).strip()
        email = str(row.get("email", "")).strip()
        display_name = str(row.get("displayname", "")).strip()
        groups_raw = str(row.get("groups", "")).strip()
        groups = [g.strip() for g in groups_raw.split(";") if g.strip()]

        if not username:
            results.append(
                {
                    "Username": "(empty)",
                    "Display Name": display_name,
                    "Email": email,
                    "Status": "⚠ Skipped",
                    "Details": "Username is empty",
                }
            )
            continue

        # Generate a secure random password
        password = generate_password()

        entry: dict = {
            "Username": username,
            "Display Name": display_name,
            "Email": email,
            "Status": "",
            "Details": "",
        }
        notes: list[str] = []

        # 1. Create user in Nextcloud
        try:
            nc_result = create_nextcloud_user(
                nc_url,
                nc_admin_user,
                nc_admin_pass,
                username,
                password,
                display_name,
                email,
                groups if groups else None,
            )
        except requests.exceptions.RequestException as exc:
            entry["Status"] = "✗ Error"
            notes.append(f"User creation failed (network/API error): {exc}")
            entry["Details"] = " | ".join(notes)
            results.append(entry)
            continue

        if nc_result["statuscode"] == 100:
            entry["Status"] = "✓ Created"

            # 2. Send welcome email
            if email_enabled and email:
                try:
                    mail_result = send_welcome_email(
                        smtp_host,
                        smtp_port_int,
                        smtp_user or "",
                        smtp_password or "",
                        smtp_security_mode,
                        smtp_from,
                        email,
                        username,
                        password,
                        nc_url,
                        display_name,
                    )
                    notes.append(
                        "Email sent"
                        if mail_result["success"]
                        else f"Email failed: {mail_result['message']}"
                    )
                except (smtplib.SMTPException, OSError) as exc:
                    notes.append(f"Email error: {exc}")
            elif not email_enabled:
                notes.append("Email skipped (SMTP not configured)")
            else:
                notes.append("Email skipped (no address)")

        else:
            entry["Status"] = "✗ Failed"
            notes.append(
                nc_result.get("message") or f"OCS code {nc_result['statuscode']}"
            )

        entry["Details"] = " | ".join(notes)
        results.append(entry)

    results_df = pd.DataFrame(results)
    success_count = sum(1 for r in results if "✓" in r["Status"])
    fail_count = len(results) - success_count

    summary_color = (
        "success"
        if fail_count == 0
        else ("warning" if success_count > 0 else "danger")
    )

    results_section = [
        dbc.Alert(
            [
                html.I(className="bi bi-info-circle me-2"),
                f"Processed {len(results)} user(s): "
                f"{success_count} created, {fail_count} failed.",
            ],
            color=summary_color,
        ),
        dag.AgGrid(
            rowData=results_df.to_dict("records"),
            columnDefs=[
                {"headerName": c, "field": c} for c in results_df.columns
            ],
            defaultColDef={
                "resizable": True,
                "wrapText": True,
                "autoHeight": True,
            },
            dashGridOptions={
                "pagination": True,
                "paginationPageSize": 20,
                "paginationPageSizeSelector": [20, 50, 100],
            },
            getRowStyle={
                "styleConditions": [
                    {
                        "condition": "params.data.Status.includes('✓')",
                        "style": {
                            "backgroundColor": "#d4edda",
                            "color": "#155724",
                        },
                    },
                    {
                        "condition": "params.data.Status.includes('✗')",
                        "style": {
                            "backgroundColor": "#f8d7da",
                            "color": "#721c24",
                        },
                    },
                    {
                        "condition": "params.data.Status.includes('⚠')",
                        "style": {
                            "backgroundColor": "#fff3cd",
                            "color": "#856404",
                        },
                    },
                ]
            },
            style={"height": "500px"},
        ),
    ]

    return results_section, ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8050"))
    app.run(debug=False, host=host, port=port)
