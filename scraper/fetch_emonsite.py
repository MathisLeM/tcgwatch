"""e-monsite per-product fetcher.

Each product detail page embeds a schema.org JSON-LD Product; we re-read it per
product for a fresh price / availability snapshot.
"""
import datetime as dt
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db import connect, game_filter_sql
from .config import PER_DOMAIN_DELAY
from .discover_emonsite import get, product_jsonld, parse_offer


def fetch_one(product):
    pid = product["id"]
    r = get(product["url"])
    if not r:
        return pid, None, None, 1, None
    d = product_jsonld(r.text)
    if not d:
        return pid, None, None, 1, None
    price, available = parse_offer(d)
    return pid, price, available, 1, None


def fetch_emonsite_all(games=None):
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop FROM products WHERE platform = 'emonsite'" + gsql,
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

    with ThreadPoolExecutor(max_workers=6) as ex:
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
    print("=== e-monsite snapshot run ===")
    rows = fetch_emonsite_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}")


if __name__ == "__main__":
    main()
