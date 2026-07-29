"""Shopify per-product fetcher.

For each Shopify product in DB, hit <url>.json and write a snapshot row.
"""
import datetime as dt
import time
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from .db import connect, game_filter_sql
from .config import USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def fetch_one(product):
    """Fetch one product via /<handle>.js.
    Returns (product_id, price, available, variants_count, stock_remaining)."""
    pid = product["id"]
    url = product["url"].rstrip("/") + ".js"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return pid, None, None, 0, None
        data = r.json()
        variants = data.get("variants", []) or []
        prices, stocks = [], []
        for v in variants:
            p = v.get("price")
            if p is not None:
                try: prices.append(float(p) / 100 if isinstance(p, int) or (isinstance(p, str) and p.isdigit()) else float(p))
                except Exception: pass
            iq = v.get("inventory_quantity")
            if isinstance(iq, int) and iq >= 0:
                stocks.append(iq)
        available = 1 if any(v.get("available") for v in variants) else 0
        stock = sum(stocks) if stocks else None
        return pid, (min(prices) if prices else None), available, len(variants), stock
    except Exception:
        return pid, None, None, 0, None


def fetch_shopify_all(games=None):
    """Fetch snapshots for every Shopify product in the DB. Returns rows for the snapshots table."""
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = conn.execute(
            "SELECT id, url, shop FROM products WHERE platform = 'shopify'" + gsql,
            gparams).fetchall()
    products = [dict(p) for p in products]
    # Group by shop so we can rate-limit per domain
    by_shop = defaultdict(list)
    for p in products:
        by_shop[p["shop"]].append(p)

    results = []
    def worker(shop_products):
        out = []
        for p in shop_products:
            out.append(fetch_one(p))
            time.sleep(PER_DOMAIN_DELAY)
        return out

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(worker, ps): shop for shop, ps in by_shop.items()}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                shop_results = fut.result()
                results.extend(shop_results)
                ok = sum(1 for r in shop_results if r[1] is not None)
                print(f"  {shop:<35} {ok}/{len(shop_results)} ok")
            except Exception as e:
                print(f"  {shop:<35} ERROR: {e}")
    return results


def write_snapshots(rows):
    """rows: list of (product_id, price, available, variants_count, stock_remaining)."""
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
    print("=== Shopify snapshot run ===")
    rows = fetch_shopify_all()
    write_snapshots(rows)
    with connect() as conn:
        ok = sum(1 for r in rows if r[1] is not None)
        avail = sum(1 for r in rows if r[2] == 1)
        n_snap = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    print(f"\nFetched: {len(rows)}  with price: {ok}  available: {avail}")
    print(f"Total snapshots in DB: {n_snap}")


if __name__ == "__main__":
    main()
