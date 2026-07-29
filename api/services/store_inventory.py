"""Per-store stock for Micromania (SFCC), on demand, via the stealth browser.

Validated flow (behind Incapsula, called from inside the browser page so it carries
the session cookies):
  1. Stores-InventorySearch?postalCode=&radius=&pid=  -> nearby stores (geo, hours...)
  2. Stores-getAtsValue?storeId=&pid=                 -> exact qty + availability/store

Parsing is split from the browser orchestration so it can be unit-tested offline.
Playwright is imported lazily (only when a live query runs).
"""
from __future__ import annotations

import time
from typing import Optional

_SFCC_BASE = "/on/demandware.store/Sites-Micromania-Site/fr_FR"

# Small in-process cache: (pid, postal, radius) -> (ts, stores). On-demand by default;
# the hybrid pre-scrape (favorited items) will reuse the same fetch function.
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
_TTL = 600  # seconds


# ── Pure parsing (unit-tested) ───────────────────────────────────────────────
def parse_stores(inv_json: dict, limit: int = 20) -> list[dict]:
    """Extract store metadata from a Stores-InventorySearch JSON payload."""
    out = []
    for s in (inv_json.get("stores") or [])[:limit]:
        out.append({
            "store_id": s.get("ID"),
            "name": s.get("name"),
            "address": " ".join(x for x in (s.get("address1"), s.get("address2")) if x) or None,
            "city": s.get("city"),
            "postal_code": s.get("postalCode"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "phone": s.get("formattedPhone") or s.get("phone"),
            "click_and_collect": bool(s.get("click_and_collect")),
            "pickup_in_store": bool(s.get("pickupInStore")),
            "ats_value": None,       # filled by apply_ats
            "available": None,
        })
    return out


def parse_ats(ats_json: dict) -> tuple[Optional[int], Optional[bool]]:
    """(atsValue, available) from a Stores-getAtsValue JSON payload."""
    qty = ats_json.get("atsValue")
    prod = ats_json.get("product") or {}
    avail = prod.get("available")
    try:
        qty = int(qty) if qty is not None else None
    except (TypeError, ValueError):
        qty = None
    return qty, (bool(avail) if avail is not None else (qty is not None and qty > 0))


def apply_ats(stores: list[dict], ats_by_id: dict[str, tuple[Optional[int], Optional[bool]]]) -> list[dict]:
    for s in stores:
        if s["store_id"] in ats_by_id:
            s["ats_value"], s["available"] = ats_by_id[s["store_id"]]
    return stores


# ── Browser orchestration ────────────────────────────────────────────────────
def fetch_store_stock(
    product_url: str,
    pid: str,
    postal: str,
    *,
    radius: int = 100,
    limit: int = 15,
    use_cache: bool = True,
) -> list[dict]:
    """Live per-store stock for a Micromania product near a postal code.

    Returns a list of store dicts (nearest first) with ats_value/available filled.
    Heavy (drives a browser) — short-cached. For prod, prefer a warm/pooled browser
    or delegate to the scraper worker.
    """
    key = (pid, postal, radius)
    if use_cache and key in _CACHE:
        ts, val = _CACHE[key]
        if time.time() - ts < _TTL:
            return val

    from scraper.stealth_browser import stealth_page, goto, settle  # lazy

    def _get_json(page, path: str) -> dict:
        return page.evaluate(
            """async (u) => {
                const r = await fetch(u, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
                try { return await r.json(); } catch (e) { return {}; }
            }""",
            path,
        )

    with stealth_page() as (page, _ctx):
        goto(page, product_url)
        settle(page)
        inv = _get_json(
            page,
            f"{_SFCC_BASE}/Stores-InventorySearch?postalCode={postal}&radius={radius}"
            f"&pid={pid}&showMap=false&isForm=true&isPDP=true",
        )
        stores = parse_stores(inv, limit=limit)
        ats_by_id: dict[str, tuple] = {}
        for s in stores:
            sid = s["store_id"]
            if not sid:
                continue
            ats = _get_json(page, f"{_SFCC_BASE}/Stores-getAtsValue?storeId={sid}&pid={pid}")
            ats_by_id[sid] = parse_ats(ats)
        stores = apply_ats(stores, ats_by_id)

    _CACHE[key] = (time.time(), stores)
    return stores
