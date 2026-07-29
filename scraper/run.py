"""Main runner: take a fresh snapshot across all 3 platforms, then report
what changed since the previous run (restocks + price changes + stockouts)."""
import sys, io, os
# Force UTF-8 stdout on Windows. Skip under pytest (its capture stream must not
# be re-wrapped, or it gets closed when our wrapper is GC'd at exit).
if (sys.platform == "win32" and "pytest" not in sys.modules
        and "PYTEST_CURRENT_TEST" not in os.environ
        and hasattr(sys.stdout, "buffer")):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass
import time
import datetime as dt
import argparse
from .db import connect
from .timing import format_timings
from . import (fetch_shopify, fetch_prestashop, fetch_woocommerce, fetch_wix,
               fetch_powerboutique, fetch_nextjs, fetch_emonsite, fetch_fantasysphere,
               fetch_micromania)

# (label, fetch_all fn, write_snapshots fn) for every platform
FETCHERS = [
    ("Shopify",       fetch_shopify.fetch_shopify_all,             fetch_shopify.write_snapshots),
    ("PrestaShop",    fetch_prestashop.fetch_prestashop_all,       fetch_prestashop.write_snapshots),
    ("WooCommerce",   fetch_woocommerce.fetch_woocommerce_all,     fetch_woocommerce.write_snapshots),
    ("Wix",           fetch_wix.fetch_wix_all,                     fetch_wix.write_snapshots),
    ("Powerboutique", fetch_powerboutique.fetch_powerboutique_all, fetch_powerboutique.write_snapshots),
    ("Next.js",       fetch_nextjs.fetch_nextjs_all,               fetch_nextjs.write_snapshots),
    ("e-monsite",     fetch_emonsite.fetch_emonsite_all,           fetch_emonsite.write_snapshots),
    ("FantasySphere", fetch_fantasysphere.fetch_fantasysphere_all, fetch_fantasysphere.write_snapshots),
    # Micromania is browser-driven (Incapsula) and Pokemon-only; its fetcher
    # short-circuits to [] outside the Pokemon scope so it never slows the rest.
    ("Micromania",    fetch_micromania.fetch_micromania_all,        fetch_micromania.write_snapshots),
]


# Map the dashboard toggle / .bat selection to the underlying DB game ids.
GAME_GROUPS = {
    "optcg":   ["optcg", "naruto_mythos"],
    "pokemon": ["pokemon"],
    "all":     None,
}


def take_snapshot(games=None):
    """Run every platform fetcher, write snapshots, and report per-scraper timing."""
    timings = []
    for label, fetch_all, write in FETCHERS:
        print(f"\n=== {label} ===")
        t0 = time.perf_counter()
        rows = fetch_all(games)
        write(rows)
        timings.append((label, len(rows), time.perf_counter() - t0))
    print(format_timings(timings))


def report_changes(games=None):
    """Compare latest snapshot vs. previous one per product."""
    gsql, gparams = "", []
    if games:
        gsql = " WHERE p.game IN (%s)" % ",".join("?" * len(games))
        gparams = list(games)
    with connect() as conn:
        # Get the two most recent snapshots per product
        cur_then = conn.execute(f"""
            WITH ranked AS (
                SELECT s.*, p.title, p.shop, p.set_code, p.game, p.url, p.platform,
                       ROW_NUMBER() OVER (PARTITION BY s.product_id ORDER BY s.observed_at DESC) rn
                FROM snapshots s JOIN products p ON p.id = s.product_id{gsql}
            )
            SELECT
                a.product_id, a.title, a.shop, a.set_code, a.url, a.platform,
                a.price_eur AS price_now, b.price_eur AS price_prev,
                a.available AS avail_now, b.available AS avail_prev
            FROM ranked a
            LEFT JOIN ranked b ON b.product_id = a.product_id AND b.rn = 2
            WHERE a.rn = 1
        """, gparams).fetchall()

    restocks, stockouts, price_drops, price_rises = [], [], [], []
    for r in cur_then:
        an, ap = r["avail_now"], r["avail_prev"]
        if ap == 0 and an == 1: restocks.append(r)
        if ap == 1 and an == 0: stockouts.append(r)
        pn, pp = r["price_now"], r["price_prev"]
        if pn is not None and pp is not None:
            diff = pn - pp
            if diff < -0.5: price_drops.append((r, diff))
            elif diff > 0.5: price_rises.append((r, diff))

    print("\n" + "="*60)
    print("CHANGES SINCE LAST RUN")
    print("="*60)
    print(f"\n>>> RESTOCKS ({len(restocks)})  (out → in stock)")
    for r in restocks:
        price = f"€{r['price_now']:.2f}" if r['price_now'] is not None else "?"
        print(f"  [{r['set_code']:<10}] {price:<9} {r['shop']:<22} {r['title'][:55]}")
        print(f"             {r['url']}")
    print(f"\n>>> NEW STOCKOUTS ({len(stockouts)})  (in stock → out)")
    for r in stockouts:
        print(f"  [{r['set_code']:<10}] {r['shop']:<22} {r['title'][:55]}")
    print(f"\n>>> PRICE DROPS ({len(price_drops)})")
    for r, d in price_drops:
        print(f"  [{r['set_code']:<10}] €{r['price_prev']:.2f} → €{r['price_now']:.2f}  ({d:+.2f})  [{r['shop']}] {r['title'][:45]}")
    print(f"\n>>> PRICE RISES ({len(price_rises)})")
    for r, d in price_rises:
        print(f"  [{r['set_code']:<10}] €{r['price_prev']:.2f} → €{r['price_now']:.2f}  ({d:+.2f})  [{r['shop']}] {r['title'][:45]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", choices=list(GAME_GROUPS), default="all",
                    help="Which TCG to snapshot/report (default: all)")
    ap.add_argument("--no-fetch", action="store_true", help="Skip fetching, only report")
    ap.add_argument("--report-only", action="store_true", help="Same as --no-fetch")
    args = ap.parse_args()
    games = GAME_GROUPS[args.game]
    print(f"Game scope: {args.game} ({games or 'all games'})")
    if not (args.no_fetch or args.report_only):
        take_snapshot(games)
    report_changes(games)


if __name__ == "__main__":
    main()
