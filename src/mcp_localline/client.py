from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


def get_json(url: str, token: str | None = None, params: dict | None = None, extra_headers: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urlencode(params)}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url=url, method="GET", headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            return {"status_code": resp.status, "ok": 200 <= resp.status < 300, "url": url, "data": json.loads(resp.read().decode("utf-8", errors="ignore"))}
    except HTTPError as e:
        txt = e.read().decode("utf-8", errors="ignore") if e.fp else str(e)
        return {"status_code": e.code, "ok": False, "url": url, "error": txt}


def post_json(url: str, token: str | None, payload: dict, params: dict | None = None, extra_headers: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    body = json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url=url, data=body, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            txt = resp.read().decode("utf-8", errors="ignore")
            parsed = json.loads(txt) if txt.strip().startswith("{") or txt.strip().startswith("[") else {"raw": txt}
            return {"status_code": resp.status, "ok": 200 <= resp.status < 300, "url": url, "data": parsed}
    except HTTPError as e:
        txt = e.read().decode("utf-8", errors="ignore") if e.fp else str(e)
        return {"status_code": e.code, "ok": False, "url": url, "error": txt}


def post_form(url: str, token: str | None, fields: dict) -> dict:
    """Send multipart/form-data payload.

    Local Line customers/email endpoints reject application/x-www-form-urlencoded
    and require multipart/form-data.
    """
    boundary = f"----mcp-localline-{uuid4().hex}"
    body_parts: list[bytes] = []
    for key, value in fields.items():
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body_parts.append(str(value).encode("utf-8"))
        body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(body_parts)

    headers = {
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url=url, data=body, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            txt = resp.read().decode("utf-8", errors="ignore")
            parsed = json.loads(txt) if txt.strip().startswith("{") or txt.strip().startswith("[") else {"raw": txt}
            return {"status_code": resp.status, "ok": 200 <= resp.status < 300, "url": url, "data": parsed}
    except HTTPError as e:
        txt = e.read().decode("utf-8", errors="ignore") if e.fp else str(e)
        return {"status_code": e.code, "ok": False, "url": url, "error": txt}
