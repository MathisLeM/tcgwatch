"""Wix Stores per-product fetcher.

For each Wix product in the DB, re-query the storefront GraphQL API by product
id to get a fresh price / availability / stock snapshot.

A Wix instance token is short-lived, so we fetch one per shop per run (via
discover_wix.get_instance) and reuse it for that shop's products.
"""
import datetime as dt
import time
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db import connect, game_filter_sql
from .config import USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY
from .discover_wix import get_instance, GQL_PATH, HEADERS

PRODUCT_Q = (
    "query($id:String!){catalog{product(productId:$id)"
    "{id formattedPrice price isInStock inventory{quantity}}}}"
)


def fetch_one(shop, instance, product):
    """Return (product_id, price, available, variants_count, stock_remaining)."""
    pid = product["id"]
    if not instance:
        return pid, None, None, 0, None
    url = f"https://{shop}{GQL_PATH}"
    headers = {**HEADERS, "Content-Type": "application/json", "Authorization": instance}
    body = {"query": PRODUCT_Q, "variables": {"id": product["platform_pid"]}}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return pid, None, None, 0, None
        prod = (((r.json().get("data") or {}).get("catalog") or {}).get("product"))
        if not prod:
            return pid, None, None, 0, None
        price = prod.get("price")
        in_stock = prod.get("isInStock")
        available = None if in_stock is None else (1 if in_stock else 0)
        qty = (prod.get("inventory") or {}).get("quantity")
        stock = qty if isinstance(qty, int) and qty > 0 else None
        return pid, (float(price) if price is not None else None), available, 1, stock
    except Exception:
        return pid, None, None, 0, None


def fetch_wix_all(games=None):
    """Fetch snapshots for every Wix product in the DB."""
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop, platform_pid FROM products WHERE platform = 'wix'" + gsql,
            gparams).fetchall()]
    by_shop = defaultdict(list)
    for p in products:
        by_shop[p["shop"]].append(p)

    results = []
    def worker(shop, shop_products):
        instance = get_instance(shop)
        out = []
        for p in shop_products:
            out.append(fetch_one(shop, instance, p))
            time.sleep(PER_DOMAIN_DELAY)
        return out

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(worker, shop, ps): shop for shop, ps in by_shop.items()}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                rs = fut.result()
                results.extend(rs)
                ok = sum(1 for r in rs if r[1] is not None)
                avail_known = sum(1 for r in rs if r[2] is not None)
                print(f"  {shop:<28} price={ok}/{len(rs)}  stock_known={avail_known}/{len(rs)}")
            except Exception as e:
                print(f"  {shop:<28} ERROR: {type(e).__name__}: {e}")
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
    print("=== Wix snapshot run ===")
    rows = fetch_wix_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    unk = sum(1 for r in rows if r[2] is None)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}  unknown: {unk}")


if __name__ == "__main__":
    main()
