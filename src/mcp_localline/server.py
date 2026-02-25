from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .auth import auth_status, bootstrap_and_store, get_access_token
from .client import get_json, post_form, post_json

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:  # pragma: no cover
    FastMCP = None
    _IMPORT_ERROR = e


def _cfg() -> tuple[str, str, str]:
    site = os.getenv("LOCAL_LINE_BASE_URL", "https://cfc.localline.ca").rstrip("/")
    api = os.getenv("LOCAL_LINE_API_BASE", f"{site}/api/backoffice/v2").rstrip("/")
    keychain_service = os.getenv("LOCAL_LINE_KEYCHAIN_SERVICE", "mcp.localline")
    return site, api, keychain_service


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _default_picklist_name(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.strftime('%A')}, {d.strftime('%b')} {_ordinal(d.day)} Deliveries"


def _current_week_window() -> tuple[str, str]:
    today = datetime.now(ZoneInfo("America/Toronto")).date()
    offset_to_thu = (3 - today.weekday()) % 7
    thu = today + timedelta(days=offset_to_thu)
    fri = thu - timedelta(days=6)
    return fri.isoformat(), thu.isoformat()


def _managed_vendor_ids(api: str, token: str) -> list[int]:
    out = get_json(f"{api}/vendors/", token, {"page_size": 500})
    if not out.get("ok"):
        return []
    data = out.get("data")
    if isinstance(data, dict):
        items = data.get("results") if isinstance(data.get("results"), list) else []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    vendor_ids: list[int] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        if v.get("connected") is True:
            continue
        vid = v.get("id")
        if isinstance(vid, int):
            vendor_ids.append(vid)
    return vendor_ids


if FastMCP is not None:
    mcp = FastMCP("localline")

    @mcp.tool(name="auth.status")
    def tool_auth_status() -> dict:
        _, api, svc = _cfg()
        return auth_status(api, svc)

    @mcp.tool(name="auth.bootstrap")
    def tool_auth_bootstrap() -> dict:
        _, api, svc = _cfg()
        try:
            return bootstrap_and_store(api, svc)
        except Exception as e:
            return {"ok": False, "status": "AUTH_FAILED", "error": str(e)}

    @mcp.tool(name="picklists.create")
    def tool_picklists_create(start_date: str, end_date: str, name: str = "", note: str = "", allow_outside_current_week: bool = False) -> dict:
        if not allow_outside_current_week:
            exp_start, exp_end = _current_week_window()
            if start_date != exp_start or end_date != exp_end:
                return {
                    "ok": False,
                    "status": "GUARD_BLOCKED",
                    "expected_start_date": exp_start,
                    "expected_end_date": exp_end,
                    "provided_start_date": start_date,
                    "provided_end_date": end_date,
                    "fix": "Use the expected current-week range or pass allow_outside_current_week=true intentionally.",
                }

        _, api, svc = _cfg()
        token, source = get_access_token(api, svc)
        if not token:
            return {"ok": False, "status": "AUTH_FAILED", "fix": "Run auth.bootstrap with env creds"}
        picklist_name = name.strip() or _default_picklist_name(end_date)
        vendor_ids = _managed_vendor_ids(api, token)
        out = post_json(
            f"{api}/orders/create-vendor-picklists/",
            token,
            {
                "name": picklist_name,
                "hub_note": (note.strip() or None),
                "send_to_all": True,
                "vendor_ids": vendor_ids,
                "copy_on_emails": False,
            },
            params={
                "fulfillment_date_start": start_date,
                "fulfillment_date_end": end_date,
                "status": ["OPEN", "NEEDS_APPROVAL", "CANCELLED", "CLOSED"],
            },
        )
        out["vendor_ids_count"] = len(vendor_ids)
        out["auth_source"] = source
        if not out.get("ok") and out.get("status_code") == 401:
            out["status"] = "AUTH_FAILED"
        return out

    @mcp.tool(name="orders.export")
    def tool_orders_export(start_date: str, end_date: str) -> dict:
        _, api, svc = _cfg()
        token, source = get_access_token(api, svc)
        if not token:
            return {"ok": False, "status": "AUTH_FAILED", "fix": "Run auth.bootstrap with env creds"}
        out = get_json(f"{api}/orders/", token, {"start_date": start_date, "end_date": end_date, "expand": "order_entries.package_price_list_entry", "page_size": 500})
        out["auth_source"] = source
        return out

    @mcp.tool(name="customers.email.proof")
    def tool_customers_email_proof(subject: str, body: str, customer_id: str = "744150") -> dict:
        _, api, svc = _cfg()
        token, source = get_access_token(api, svc)
        if not token:
            return {"ok": False, "status": "AUTH_FAILED"}
        out = post_form(f"{api}/customers/email?id={customer_id}", token, {"subject": subject, "body": body, "send_to_all": "false"})
        out["auth_source"] = source
        return out

    @mcp.tool(name="customers.email.send_all")
    def tool_customers_email_send_all(subject: str, body: str) -> dict:
        _, api, svc = _cfg()
        token, source = get_access_token(api, svc)
        if not token:
            return {"ok": False, "status": "AUTH_FAILED"}
        out = post_form(f"{api}/customers/email", token, {"subject": subject, "body": body, "send_to_all": "true"})
        out["auth_source"] = source
        return out


def main() -> None:
    if FastMCP is None:
        raise RuntimeError(f"mcp package not installed: {_IMPORT_ERROR}")
    mcp.run()


if __name__ == "__main__":
    main()
