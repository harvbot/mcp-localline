from __future__ import annotations

import json
import os
import typer

from .auth import auth_status, bootstrap_and_store, get_access_token
from .client import get_json, post_form

app = typer.Typer(help="Local Line MCP boundary CLI")


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
def picklists_create(start_date: str = typer.Option(...), end_date: str = typer.Option(...)) -> None:
    _, api, svc = _cfg()
    token, source = get_access_token(api, svc)
    if not token:
        print(json.dumps({"ok": False, "status": "AUTH_FAILED", "fix": "Run mcp-localline auth-bootstrap with LOCALLINE_USERNAME/PASSWORD env vars"}, indent=2))
        raise typer.Exit(code=2)
    out = get_json(f"{api}/orders/create-vendor-picklists/", token, {"fulfillment_date_start": start_date, "fulfillment_date_end": end_date})
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
