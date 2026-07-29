"""FantasySphere per-product fetcher.

The detail page mixes cross-sell tiles, so we re-fetch the category listings
(which carry a clean price/stock per tile) and map by product id — one small set
of requests per run.
"""
import datetime as dt
from collections import defaultdict
from .db import connect, game_filter_sql
from .discover_fantasysphere import CATEGORIES, fetch_category, PID_RE


def _shop_pricemap(shop):
    """pid -> (price, available) from this shop's category listings."""
    out = {}
    for game, url in CATEGORIES.get(shop, []):
        for pid, purl, title, price, avail in fetch_category(url):
            if pid:
                out[pid] = (price, avail)
    return out


def fetch_fantasysphere_all(games=None):
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop, platform_pid FROM products WHERE platform = 'fantasysphere'" + gsql,
            gparams).fetchall()]
    by_shop = defaultdict(list)
    for p in products:
        by_shop[p["shop"]].append(p)

    results = []
    for shop, ps in by_shop.items():
        try:
            pmap = _shop_pricemap(shop)
            rs = []
            for p in ps:
                v = pmap.get(str(p["platform_pid"]))
                if v:
                    rs.append((p["id"], v[0], v[1], 1, None))
                else:
                    rs.append((p["id"], None, None, 1, None))
            results.extend(rs)
            ok = sum(1 for r in rs if r[1] is not None)
            print(f"  {shop:<28} price={ok}/{len(rs)}")
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
    print("=== FantasySphere snapshot run ===")
    rows = fetch_fantasysphere_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}")


if __name__ == "__main__":
    main()
