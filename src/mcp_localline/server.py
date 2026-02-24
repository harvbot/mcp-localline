from __future__ import annotations

import os

from .auth import auth_status, bootstrap_and_store, get_access_token
from .client import get_json, post_form

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
    def tool_picklists_create(start_date: str, end_date: str) -> dict:
        _, api, svc = _cfg()
        token, source = get_access_token(api, svc)
        if not token:
            return {"ok": False, "status": "AUTH_FAILED", "fix": "Run auth.bootstrap with env creds"}
        out = get_json(f"{api}/orders/create-vendor-picklists/", token, {"fulfillment_date_start": start_date, "fulfillment_date_end": end_date})
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
