"""Kyivstar programmable SMS — OAuth2 client-credentials + POST /sms.

Ported from open-city-atlantis (apps/accounts/sms.py). Only the sending path is
kept; token is cached in-process. Blank credentials => stub (logged, not sent).
"""
import logging
import os
import time

import httpx

log = logging.getLogger("uvicorn.error")

_ENABLED = os.environ.get("KYIVSTAR_SMS_ENABLED", "").lower() in ("1", "true", "yes")
_CLIENT_ID = os.environ.get("KYIVSTAR_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("KYIVSTAR_CLIENT_SECRET", "")
_SENDER = os.environ.get("KYIVSTAR_SENDER", "School")
_BASE_URL = os.environ.get("KYIVSTAR_SMS_BASE_URL", "https://api-gateway.kyivstar.ua/rest/v1")
_TOKEN_URL = os.environ.get("KYIVSTAR_TOKEN_URL", "https://api-gateway.kyivstar.ua/idp/oauth2/token")
_TIMEOUT = 10

_token = {"value": "", "exp": 0.0}


def configured() -> bool:
    return _ENABLED and bool(_CLIENT_ID and _CLIENT_SECRET)


def _access_token() -> str:
    if _token["value"] and _token["exp"] > time.time():
        return _token["value"]
    try:
        r = httpx.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(_CLIENT_ID, _CLIENT_SECRET),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Kyivstar token request failed: %s", e)
        return ""
    _token["value"] = str(data.get("access_token", ""))
    _token["exp"] = time.time() + max(int(data.get("expires_in", 3600)) - 60, 60)
    return _token["value"]


def send_sms(phone: str, text: str) -> tuple[bool, str]:
    """Returns (ok, error). Stub-success when credentials are blank."""
    if not configured():
        log.warning("Kyivstar SMS not configured — not sending to %s", phone)
        if os.environ.get("SMS_DEBUG"):
            print(f"[SMS] {phone}: {text}")
        return True, ""

    token = _access_token()
    if not token:
        return False, "не вдалося отримати токен Kyivstar"
    try:
        r = httpx.post(
            f"{_BASE_URL.rstrip('/')}/sms",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "from": _SENDER,
                "to": phone.removeprefix("+"),
                "text": text,
                "maxSegments": 1,
                "messageTtlSec": 600,
            },
            timeout=_TIMEOUT,
        )
        data = r.json() if r.content else {}
    except (httpx.HTTPError, ValueError) as e:
        log.exception("Kyivstar SMS send failed")
        return False, str(e)

    if r.is_success:
        log.info("Kyivstar SMS sent to %s (msgId=%s)", phone, data.get("msgId"))
        return True, ""
    err = ""
    if isinstance(data.get("error"), dict):
        err = data["error"].get("message", "")
    return False, err or data.get("errorMsg") or f"HTTP {r.status_code}"
