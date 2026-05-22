"""
nextcloud.py — Nextcloud OCS Provisioning API wrapper.

Supported operations:
- create_nextcloud_user  : create a new user account
- force_password_change  : require the user to change password on next login
"""

import xml.etree.ElementTree as ET

import requests

_REQUEST_TIMEOUT = 30  # seconds


def _parse_ocs_response(response: requests.Response) -> dict:
    """Parse the XML body of an OCS API response into a dict."""
    try:
        root = ET.fromstring(response.text)
        status = root.findtext("./meta/status") or ""
        statuscode_text = root.findtext("./meta/statuscode") or "-1"
        message = root.findtext("./meta/message") or ""
        return {
            "status": status,
            "statuscode": int(statuscode_text),
            "message": message,
        }
    except ET.ParseError as exc:
        return {
            "status": "error",
            "statuscode": -1,
            "message": (
                f"XML parsing failed (HTTP {response.status_code}): {exc}. "
                f"Response preview: {response.text[:200]!r}"
            ),
        }
    except (ValueError, KeyError) as exc:
        return {
            "status": "error",
            "statuscode": -1,
            "message": f"Unexpected OCS response structure: {exc}",
        }


def create_nextcloud_user(
    nextcloud_url: str,
    admin_user: str,
    admin_password: str,
    username: str,
    password: str,
    display_name: str = "",
    email: str = "",
    groups: list | None = None,
) -> dict:
    """Create a new user account via the Nextcloud OCS Provisioning API.

    Returns a dict with keys ``status``, ``statuscode``, and ``message``.
    A ``statuscode`` of 100 means success.
    """
    url = f"{nextcloud_url.rstrip('/')}/ocs/v1.php/cloud/users"

    data: dict = {
        "userid": username,
        "password": password,
    }
    if display_name:
        data["displayName"] = display_name
    if email:
        data["email"] = email
    if groups:
        # The OCS API expects repeated form fields for groups
        data["groups[]"] = groups

    headers = {"OCS-APIREQUEST": "true"}

    response = requests.post(
        url,
        auth=(admin_user, admin_password),
        data=data,
        headers=headers,
        timeout=_REQUEST_TIMEOUT,
    )
    return _parse_ocs_response(response)


def force_password_change(
    nextcloud_url: str,
    admin_user: str,
    admin_password: str,
    username: str,
) -> dict:
    """Require *username* to change their password on the next login.

    Uses the ``nextLoginPasswordChange`` key introduced in Nextcloud 21.
    Returns a dict with keys ``status``, ``statuscode``, and ``message``.
    """
    url = f"{nextcloud_url.rstrip('/')}/ocs/v1.php/cloud/users/{username}"

    data = {
        "key": "nextLoginPasswordChange",
        "value": "true",
    }
    headers = {"OCS-APIREQUEST": "true"}

    response = requests.put(
        url,
        auth=(admin_user, admin_password),
        data=data,
        headers=headers,
        timeout=_REQUEST_TIMEOUT,
    )
    return _parse_ocs_response(response)
