"""Listing query — the latest (and previous) snapshot per product, with filters.

This is the API port of the Streamlit dashboard's `load_data` query (app.py).
The ROW_NUMBER() window + COUNT(*) OVER() work identically on SQLite (3.25+) and
PostgreSQL, so the same SQL runs in dev and prod.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

# Columns selected for each listing (kept aligned with schemas.ProductListing).
_SELECT_COLS = """
    l.product_id, l.platform, l.shop, l.game, l.language, l.set_code, l.set_codes,
    l.series, l.kind, l.title, l.url, l.price_eur AS price_now, l.available,
    l.stock_remaining, l.observed_at, pr.price_prev, pr.avail_prev
"""

# Ordering options. `release_date` comes from a LEFT JOIN on `sets` (chronological
# set ordering); NULLs (unidentified sets) are always pushed to the end.
_ORDERS = {
    # Default = newest sets first, then kind, then cheapest in-stock at top.
    "default": "(l.release_date IS NULL), l.release_date DESC, l.set_code, l.kind, "
               "(l.price_eur IS NULL), l.price_eur",
    "set_new": "(l.release_date IS NULL), l.release_date DESC, l.set_code, l.kind, "
               "(l.price_eur IS NULL), l.price_eur",
    "set_old": "(l.release_date IS NULL), l.release_date ASC, l.set_code, l.kind, "
               "(l.price_eur IS NULL), l.price_eur",
    # Group by block/series (unidentified series last), then newest set within block.
    "block": "(l.series IS NULL OR l.series = ''), l.series, "
             "(l.release_date IS NULL), l.release_date DESC, l.set_code, "
             "l.kind, (l.price_eur IS NULL), l.price_eur",
    "price_asc": "(l.price_eur IS NULL), l.price_eur ASC",
    "price_desc": "(l.price_eur IS NULL), l.price_eur DESC",
    "recent": "l.observed_at DESC",
}

_STATUS_SQL = {
    "In Stock": "l.available = 1",
    "Out": "l.available = 0",
    "Unknown": "l.available IS NULL",
}


def _in_clause(field: str, values: Sequence, prefix: str, params: dict) -> str:
    keys = []
    for i, v in enumerate(values):
        k = f"{prefix}{i}"
        params[k] = v
        keys.append(f":{k}")
    return f"{field} IN ({', '.join(keys)})"


def query_listings(
    db: Session,
    *,
    games: Optional[Sequence[str]] = None,
    platforms: Optional[Sequence[str]] = None,
    product_ids: Optional[Sequence[int]] = None,
    languages: Optional[Sequence[str]] = None,
    set_codes: Optional[Sequence[str]] = None,
    series: Optional[Sequence[str]] = None,
    kinds: Optional[Sequence[str]] = None,
    shops: Optional[Sequence[str]] = None,
    statuses: Optional[Sequence[str]] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    order: str = "default",
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    """Return (total_matching, page_rows)."""
    params: dict = {}
    cte_filters: list[str] = []   # filters on product columns (inside the window CTE)
    out_filters: list[str] = []   # filters on the latest projection (status, price)

    if games:
        cte_filters.append(_in_clause("p.game", games, "g", params))
    if platforms:
        cte_filters.append(_in_clause("p.platform", platforms, "plat", params))
    if product_ids is not None:
        if not product_ids:
            return 0, []  # empty filter -> no results
        cte_filters.append(_in_clause("p.id", product_ids, "pid", params))
    if languages:
        cte_filters.append(_in_clause("p.language", languages, "lng", params))
    if series:
        cte_filters.append(_in_clause("p.series", series, "ser", params))
    if kinds:
        cte_filters.append(_in_clause("p.kind", kinds, "knd", params))
    if shops:
        cte_filters.append(_in_clause("p.shop", shops, "shp", params))
    if search:
        params["q"] = f"%{search.lower()}%"
        cte_filters.append("lower(p.title) LIKE :q")
    if set_codes:
        # Match the primary set_code OR any code inside a multi-set lot (';'-joined).
        ors = []
        for i, code in enumerate(set_codes):
            params[f"sc{i}"] = code
            params[f"scl{i}"] = f"%;{code};%"
            ors.append(
                f"p.set_code = :sc{i} OR "
                f"(';' || COALESCE(p.set_codes, '') || ';') LIKE :scl{i}"
            )
        cte_filters.append("(" + " OR ".join(ors) + ")")

    if statuses:
        conds = [_STATUS_SQL[s] for s in statuses if s in _STATUS_SQL]
        if conds:
            out_filters.append("(" + " OR ".join(conds) + ")")
    if max_price is not None and max_price > 0:
        params["maxp"] = max_price
        out_filters.append("(l.price_eur IS NULL OR l.price_eur <= :maxp)")

    cte_where = (" WHERE " + " AND ".join(cte_filters)) if cte_filters else ""
    out_where = (" WHERE " + " AND ".join(out_filters)) if out_filters else ""
    order_by = _ORDERS.get(order, _ORDERS["default"])

    base = f"""
        WITH ranked AS (
            SELECT s.product_id, s.observed_at, s.price_eur, s.available, s.stock_remaining,
                   p.platform, p.shop, p.set_code, p.set_codes, p.series, p.game,
                   p.language, p.kind, p.title, p.url, se.release_date,
                   ROW_NUMBER() OVER (PARTITION BY s.product_id
                                      ORDER BY s.observed_at DESC) AS rn
            FROM snapshots s
            JOIN products p ON p.id = s.product_id
            LEFT JOIN sets se ON se.game = p.game
                             AND se.language = p.language
                             AND se.set_code = p.set_code{cte_where}
        ),
        latest AS (SELECT * FROM ranked WHERE rn = 1),
        prev   AS (SELECT product_id, price_eur AS price_prev, available AS avail_prev
                   FROM ranked WHERE rn = 2)
        SELECT {_SELECT_COLS}, COUNT(*) OVER() AS _total
        FROM latest l LEFT JOIN prev pr ON pr.product_id = l.product_id
        {out_where}
        ORDER BY {order_by}
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    rows = db.execute(text(base), params).mappings().all()
    total = rows[0]["_total"] if rows else 0
    items = [dict(r) for r in rows]
    for it in items:
        it.pop("_total", None)
    return total, items


def status_of(available: Optional[int]) -> str:
    return {1: "In Stock", 0: "Out"}.get(available, "Unknown")
