from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass
class TokenPair:
    access: str
    refresh: str


def _keychain_get(service: str, account: str) -> Optional[str]:
    proc = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _keychain_set(service: str, account: str, value: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", value],
        check=True,
        capture_output=True,
        text=True,
    )


def _post_json(url: str, payload: dict) -> tuple[dict, list[str]]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url=url, data=body, method="POST", headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=45) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="ignore"))
            set_cookies = resp.headers.get_all("Set-Cookie") or []
            return parsed, set_cookies
    except HTTPError as e:
        text = e.read().decode("utf-8", errors="ignore") if e.fp else str(e)
        raise RuntimeError(f"HTTP {e.code} @ {url}: {text}")


def _extract_refresh_from_set_cookie(set_cookies: list[str]) -> str:
    candidate_names = {"refresh", "refresh_token", "jwt_refresh_token", "ll_refresh", "token_refresh"}
    for raw in set_cookies:
        c = SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            continue
        for name, morsel in c.items():
            if name.lower() in candidate_names and morsel.value:
                return morsel.value.strip()
    return ""


def bootstrap_from_env(base_url: str) -> TokenPair:
    username = os.getenv("LOCALLINE_USERNAME", "").strip()
    password = os.getenv("LOCALLINE_PASSWORD", "").strip()
    if not username or not password:
        raise RuntimeError("Missing LOCALLINE_USERNAME/LOCALLINE_PASSWORD env vars")
    payload, set_cookies = _post_json(f"{base_url.rstrip('/')}/token/", {"username": username, "password": password})
    access = str(payload.get("access") or "").strip()
    refresh = str(payload.get("refresh") or "").strip() or _extract_refresh_from_set_cookie(set_cookies)
    if not access:
        raise RuntimeError("Login succeeded but no access token returned")
    return TokenPair(access=access, refresh=refresh)


def refresh_access(base_url: str, refresh: str) -> TokenPair:
    payload, _ = _post_json(f"{base_url.rstrip('/')}/token/refresh/", {"refresh": refresh})
    access = str(payload.get("access") or "").strip()
    refresh_out = str(payload.get("refresh") or refresh).strip()
    if not access:
        raise RuntimeError("Refresh succeeded but no access token returned")
    return TokenPair(access=access, refresh=refresh_out)


def get_access_token(base_url: str, keychain_service: str) -> tuple[Optional[str], str]:
    direct = os.getenv("LOCALLINE_API_TOKEN", "").strip()
    if direct:
        return direct, "env:LOCALLINE_API_TOKEN"

    refresh = _keychain_get(keychain_service, "refresh_token")
    if refresh:
        pair = refresh_access(base_url, refresh)
        _keychain_set(keychain_service, "refresh_token", pair.refresh)
        if pair.access:
            _keychain_set(keychain_service, "access_token", pair.access)
        return pair.access, "keychain:refresh"

    access = _keychain_get(keychain_service, "access_token")
    if access:
        return access, "keychain:access"

    return None, "missing_refresh_token"


def bootstrap_and_store(base_url: str, keychain_service: str) -> dict:
    pair = bootstrap_from_env(base_url)
    if pair.refresh:
        _keychain_set(keychain_service, "refresh_token", pair.refresh)
    if pair.access:
        _keychain_set(keychain_service, "access_token", pair.access)
    return {
        "ok": True,
        "auth_base": base_url.rstrip("/"),
        "token_url": f"{base_url.rstrip('/')}/token/",
        "refresh_url": f"{base_url.rstrip('/')}/token/refresh/",
        "stored_refresh": bool(pair.refresh),
        "stored_access": bool(pair.access),
        "note": "Credentials were read from env only; no plaintext persisted in repo files.",
    }


def auth_status(base_url: str, keychain_service: str) -> dict:
    token, source = get_access_token(base_url, keychain_service)
    if not token:
        return {
            "ok": False,
            "status": "AUTH_FAILED",
            "auth_base": base_url.rstrip("/"),
            "token_url": f"{base_url.rstrip('/')}/token/",
            "refresh_url": f"{base_url.rstrip('/')}/token/refresh/",
            "reason": source,
            "fix": "Run: LOCALLINE_USERNAME=... LOCALLINE_PASSWORD=... mcp-localline auth-bootstrap",
        }
    return {
        "ok": True,
        "status": "AUTH_OK",
        "auth_base": base_url.rstrip("/"),
        "token_url": f"{base_url.rstrip('/')}/token/",
        "refresh_url": f"{base_url.rstrip('/')}/token/refresh/",
        "source": source,
    }
