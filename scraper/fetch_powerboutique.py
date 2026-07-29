"""Powerboutique per-product fetcher.

For each Powerboutique product in the DB, fetch its detail page and read the
schema.org microdata for the main product:
  [itemprop=price]         -> price
  [itemprop=availability]  -> .../InStock | .../OutOfStock

Detail pages also embed related-product tiles (each with their own .bp_prix /
.bp_stock), so the microdata is the only contamination-free signal.
"""
import datetime as dt
import time
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db import connect, game_filter_sql
from .config import REQUEST_TIMEOUT, PER_DOMAIN_DELAY
from .discover_powerboutique import HEADERS, parse_price


def _availability(href_or_text):
    if not href_or_text:
        return None
    t = href_or_text.lower()
    if "outofstock" in t or "soldout" in t or "rupture" in t:
        return 0
    if "instock" in t or "disponible" in t:
        return 1
    return None


def fetch_one(product):
    """Return (product_id, price, available, variants_count, stock_remaining)."""
    pid = product["id"]
    try:
        r = requests.get(product["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return pid, None, None, 1, None
        soup = BeautifulSoup(r.text, "html.parser")
        price = None
        pe = soup.select_one("[itemprop=price]")
        if pe:
            price = parse_price(pe.get("content") or pe.get_text(" ", strip=True))
            if price is None and pe.get("content"):
                try: price = float(pe["content"])
                except Exception: pass
        ae = soup.select_one("[itemprop=availability]")
        available = _availability(ae.get("href") or ae.get("content")) if ae else None
        # Fallback to the main product tile if microdata is absent
        if price is None:
            t = soup.select_one(".bp_prix")
            if t: price = parse_price(t.get_text(" ", strip=True))
        if available is None:
            t = soup.select_one(".bp_stock")
            if t: available = _availability(t.get_text(" ", strip=True))
        return pid, price, available, 1, None
    except Exception:
        return pid, None, None, 1, None


def fetch_powerboutique_all(games=None):
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop, platform_pid FROM products WHERE platform = 'powerboutique'" + gsql,
            gparams).fetchall()]
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

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(worker, ps): shop for shop, ps in by_shop.items()}
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
    print("=== Powerboutique snapshot run ===")
    rows = fetch_powerboutique_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    unk = sum(1 for r in rows if r[2] is None)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}  unknown: {unk}")


if __name__ == "__main__":
    main()
