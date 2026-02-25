from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import typer

from .auth import auth_status, bootstrap_and_store, get_access_token
from .client import get_json, post_form, post_json

app = typer.Typer(help="Local Line MCP boundary CLI")


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
    # Current fulfillment week window: Friday..Thursday in America/Toronto.
    today = datetime.now(ZoneInfo("America/Toronto")).date()
    # Find Thursday in the current week bucket.
    offset_to_thu = (3 - today.weekday()) % 7
    thu = today + timedelta(days=offset_to_thu)
    fri = thu - timedelta(days=6)
    return fri.isoformat(), thu.isoformat()


def _guard_current_week(start_date: str, end_date: str, enforce: bool) -> None:
    if not enforce:
        return
    exp_start, exp_end = _current_week_window()
    if start_date != exp_start or end_date != exp_end:
        raise typer.BadParameter(
            f"Guard blocked run: expected current-week range {exp_start}..{exp_end}, got {start_date}..{end_date}. "
            "Use --allow-outside-current-week to override intentionally."
        )


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
        # Per Hank: use vendors endpoint and filter out connected=true
        if v.get("connected") is True:
            continue
        vid = v.get("id")
        if isinstance(vid, int):
            vendor_ids.append(vid)
    return vendor_ids


def _cfg() -> tuple[str, str, str]:
    site = os.getenv("LOCAL_LINE_BASE_URL", "https://cfc.localline.ca").rstrip("/")
    api = os.getenv("LOCAL_LINE_API_BASE", f"{site}/api/backoffice/v2").rstrip("/")
    keychain_service = os.getenv("LOCAL_LINE_KEYCHAIN_SERVICE", "mcp.localline")
    return site, api, keychain_service


@app.command("auth-status")
def auth_status_cmd() -> None:
    _, api, svc = _cfg()
    print(json.dumps(auth_status(api, svc), indent=2))


@app.command("auth-bootstrap")
def auth_bootstrap_cmd() -> None:
    _, api, svc = _cfg()
    try:
        out = bootstrap_and_store(api, svc)
    except Exception as e:
        out = {"ok": False, "status": "AUTH_FAILED", "error": str(e)}
    print(json.dumps(out, indent=2))


@app.command("picklists-create")
def picklists_create(
    start_date: str = typer.Option(...),
    end_date: str = typer.Option(...),
    name: str = typer.Option("", help="Optional picklist batch name"),
    note: str = typer.Option("", help="Optional hub note"),
    allow_outside_current_week: bool = typer.Option(False, help="Override current-week date guard"),
) -> None:
    _guard_current_week(start_date, end_date, enforce=not allow_outside_current_week)

    _, api, svc = _cfg()
    token, source = get_access_token(api, svc)
    if not token:
        print(json.dumps({"ok": False, "status": "AUTH_FAILED", "fix": "Run mcp-localline auth-bootstrap with LOCALLINE_USERNAME/PASSWORD env vars"}, indent=2))
        raise typer.Exit(code=2)
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
    print(json.dumps(out, indent=2))


@app.command("orders-export")
def orders_export(start_date: str = typer.Option(...), end_date: str = typer.Option(...)) -> None:
    _, api, svc = _cfg()
    token, source = get_access_token(api, svc)
    if not token:
        print(json.dumps({"ok": False, "status": "AUTH_FAILED", "fix": "Run mcp-localline auth-bootstrap with LOCALLINE_USERNAME/PASSWORD env vars"}, indent=2))
        raise typer.Exit(code=2)
    out = get_json(f"{api}/orders/", token, {"start_date": start_date, "end_date": end_date, "expand": "order_entries.package_price_list_entry", "page_size": 500})
    out["auth_source"] = source
    print(json.dumps(out, indent=2))


@app.command("customers-email-proof")
def customers_email_proof(subject: str = typer.Option(...), body: str = typer.Option(...), customer_id: str = typer.Option("744150")) -> None:
    _, api, svc = _cfg()
    token, source = get_access_token(api, svc)
    if not token:
        print(json.dumps({"ok": False, "status": "AUTH_FAILED"}, indent=2))
        raise typer.Exit(code=2)
    out = post_form(f"{api}/customers/email?id={customer_id}", token, {"subject": subject, "body": body, "send_to_all": "false"})
    out["auth_source"] = source
    print(json.dumps(out, indent=2))


@app.command("customers-email-send-all")
def customers_email_send_all(subject: str = typer.Option(...), body: str = typer.Option(...)) -> None:
    _, api, svc = _cfg()
    token, source = get_access_token(api, svc)
    if not token:
        print(json.dumps({"ok": False, "status": "AUTH_FAILED"}, indent=2))
        raise typer.Exit(code=2)
    out = post_form(f"{api}/customers/email", token, {"subject": subject, "body": body, "send_to_all": "true"})
    out["auth_source"] = source
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    app()
