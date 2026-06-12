import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


def _publishable_key() -> str:
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if key:
        return key
    return _require_env("SUPABASE_ANON_KEY")


def _auth_base_url() -> str:
    return f"{_require_env('SUPABASE_URL').rstrip('/')}/auth/v1"


def _service_headers() -> dict[str, str]:
    key = _publishable_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _user_headers(access_token: str) -> dict[str, str]:
    key = _publishable_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {access_token}",
    }


def _parse_auth_response(data: dict[str, Any]) -> dict[str, Any]:
    user = data.get("user") or {}
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type", "bearer"),
        "user": {
            "id": user.get("id"),
            "email": user.get("email"),
        },
    }


def _raise_auth_error(response: httpx.Response) -> None:
    detail = "Authentication failed"
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("msg") or payload.get("error_description") or payload.get("message") or detail
    except Exception:
        detail = response.text or detail
    logger.warning("Supabase auth error %s: %s", response.status_code, detail)
    raise AuthError(detail, status_code=response.status_code)


def sign_up(email: str, password: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{_auth_base_url()}/signup",
            headers=_service_headers(),
            json={"email": email, "password": password},
        )
    if response.status_code >= 400:
        _raise_auth_error(response)
    return _parse_auth_response(response.json())


def sign_in(email: str, password: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{_auth_base_url()}/token?grant_type=password",
            headers=_service_headers(),
            json={"email": email, "password": password},
        )
    if response.status_code >= 400:
        _raise_auth_error(response)
    return _parse_auth_response(response.json())


def refresh_session(refresh_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{_auth_base_url()}/token?grant_type=refresh_token",
            headers=_service_headers(),
            json={"refresh_token": refresh_token},
        )
    if response.status_code >= 400:
        _raise_auth_error(response)
    return _parse_auth_response(response.json())


def get_user(access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{_auth_base_url()}/user",
            headers=_user_headers(access_token),
        )
    if response.status_code >= 400:
        _raise_auth_error(response)
    user = response.json()
    return {"id": user.get("id"), "email": user.get("email")}


def sign_out(access_token: str) -> None:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{_auth_base_url()}/logout",
            headers=_user_headers(access_token),
        )
    if response.status_code >= 400:
        _raise_auth_error(response)
