"""Next.js per-product fetcher (PlayIn, Parkage).

Mirrors the discovery strategies:
* Parkage -> one bulk Strapi call per configured category, then map by id.
* PlayIn  -> fetch each detail page, read the JSON-LD Product offer.
"""
import datetime as dt
import time
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db import connect, game_filter_sql
from .config import REQUEST_TIMEOUT, PER_DOMAIN_DELAY
from .discover_nextjs import (
    HEADERS, PARKAGE_API, PARKAGE_CONFIG, parkage_price,
    playin_product_jsonld, playin_parse_offer, _get,
)


def _fetch_parkage(shop, products):
    """Bulk-load configured categories, map id -> (price, avail, stock)."""
    idmap = {}
    for game, params, page_url in PARKAGE_CONFIG.get(shop, []):
        r = _get(PARKAGE_API, params={**params, "locale": "fr", "limit": "500"})
        if not r:
            continue
        try:
            items = r.json().get("data", {}).get("list", []) or []
        except Exception:
            continue
        for p in items:
            stock = p.get("stock")
            idmap[str(p.get("id"))] = (
                parkage_price(p),
                1 if p.get("isStock") else 0,
                stock if isinstance(stock, int) and stock > 0 else None,
            )
    out = []
    for prod in products:
        v = idmap.get(str(prod["platform_pid"]))
        if v:
            out.append((prod["id"], v[0], v[1], 1, v[2]))
        else:
            out.append((prod["id"], None, None, 1, None))
    return out


def _fetch_playin(shop, products):
    out = []
    def one(prod):
        r = _get(prod["url"])
        if not r:
            return (prod["id"], None, None, 1, None)
        d = playin_product_jsonld(r.text)
        if not d:
            return (prod["id"], None, None, 1, None)
        price, available = playin_parse_offer(d)
        return (prod["id"], price, available, 1, None)
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(one, p) for p in products]
        for f in as_completed(futs):
            out.append(f.result())
            time.sleep(PER_DOMAIN_DELAY / 6)
    return out


def fetch_nextjs_all(games=None):
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop, platform_pid FROM products WHERE platform = 'nextjs'" + gsql,
            gparams).fetchall()]
    by_shop = defaultdict(list)
    for p in products:
        by_shop[p["shop"]].append(p)

    results = []
    for shop, ps in by_shop.items():
        try:
            if shop in PARKAGE_CONFIG:
                rs = _fetch_parkage(shop, ps)
            elif "play-in" in shop:
                rs = _fetch_playin(shop, ps)
            else:
                rs = [(p["id"], None, None, 1, None) for p in ps]
            results.extend(rs)
            ok = sum(1 for r in rs if r[1] is not None)
            avail_known = sum(1 for r in rs if r[2] is not None)
            print(f"  {shop:<28} price={ok}/{len(rs)}  stock_known={avail_known}/{len(rs)}")
        except Exception as e:
            print(f"  {shop:<28} ERROR: {type(e).__name__}: {e}")
            results.extend((p["id"], None, None, 1, None) for p in ps)
    return results


def write_snapshots(rows):
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.executemany("""
            INSERT INTO snapshots (product_id, observed_at, price_eur, available, raw_variant_count, stock_remaining)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(pid, now, price, avail, vc, stock) for pid, price, avail, vc, stock in rows])
        conn.commit()


from .timing import timed_main


@timed_main
def main():
    print("=== Next.js snapshot run ===")
    rows = fetch_nextjs_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    unk = sum(1 for r in rows if r[2] is None)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}  unknown: {unk}")


if __name__ == "__main__":
    main()
