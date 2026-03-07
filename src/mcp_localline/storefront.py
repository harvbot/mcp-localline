from __future__ import annotations

import os
from urllib.parse import urlparse

from .client import get_json, post_json


def cfg() -> tuple[str, str]:
    """Return (storefront_api_base, subdomain) derived from LOCAL_LINE_BASE_URL."""
    site = os.getenv("LOCAL_LINE_BASE_URL", "https://cfc.localline.ca").rstrip("/")
    host = urlparse(site).hostname or ""
    subdomain = host.split(".")[0] if "." in host else host
    return f"{site}/api/storefront/v2", subdomain


def get_token() -> tuple[str, str]:
    """Obtain an anonymous storefront token. Returns (access_token, subdomain)."""
    sf_base, subdomain = cfg()
    result = post_json(
        f"{sf_base}/token/anonymous/",
        None,
        {},
        extra_headers={"subdomain": subdomain},
    )
    access = str((result.get("data") or {}).get("access", "")).strip()
    if not access:
        raise RuntimeError(f"Storefront anonymous token request failed: {result}")
    return access, subdomain


def price_list_default(token: str) -> dict:
    sf_base, _ = cfg()
    return get_json(f"{sf_base}/price-lists/default/", token)


def products(token: str, price_list_id: int | str) -> dict:
    sf_base, _ = cfg()
    return get_json(f"{sf_base}/price-lists/{price_list_id}/products/", token)
