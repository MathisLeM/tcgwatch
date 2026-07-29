"""Micromania per-product fetcher (Imperva/Incapsula-gated, browser-driven).

Unlike the 8 requests-based fetchers, Micromania needs a real browser to clear
the Incapsula challenge, so this fetcher drives ONE reused stealthy Chromium
session (see `stealth_browser`) and visits each tracked product page SEQUENTIALLY
with polite delays. It is wired into `run.py` only for the Pokemon scope, so it
never slows the other (game-agnostic) fetchers.

It mirrors the fetch_prestashop contract:
  * `fetch_micromania_all(games)` reads products WHERE platform='micromania',
    re-visits each PDP, parses price + availability (+ stock when exposed), and
    returns rows `(product_id, price, available, raw_variant_count, stock_remaining)`.
  * `write_snapshots(rows)` inserts into `snapshots`, identical to the others.

No-op fast path: if `games` is set and does NOT include 'pokemon', returns []
immediately (no browser launched).
"""
from __future__ import annotations

import datetime as dt
import time

from bs4 import BeautifulSoup

from .config import PER_DOMAIN_DELAY
from .db import connect, game_filter_sql
from .micromania_parse import parse_price, parse_availability, parse_stock_count
from .stealth_browser import stealth_page, goto, settle, looks_like_challenge

PLATFORM = "micromania"
# Be a little more patient than the shared per-domain delay: this is a heavy,
# single-session crawl and we want to stay well under any rate threshold.
DELAY = max(PER_DOMAIN_DELAY, 1.5)


def _fetch_one(page, product) -> tuple:
    """Visit one PDP and return the snapshot tuple. Never raises."""
    pid = product["id"]
    url = product["url"]
    try:
        resp = goto(page, url)
        settle(page)
        html = page.content()
        status = resp.status if resp else None
        if looks_like_challenge(html, status):
            # Signal the caller to abort the whole run (raise a sentinel).
            raise _Challenged(url, status, len(html))
        soup = BeautifulSoup(html, "html.parser")
        price = parse_price(soup)
        avail = parse_availability(soup)
        stock = parse_stock_count(soup) if avail == 1 else None
        return pid, price, avail, 1, stock
    except _Challenged:
        raise
    except Exception as e:
        print(f"  [micromania] product {pid} failed: {type(e).__name__}: {e}")
        return pid, None, None, 0, None


class _Challenged(Exception):
    """Raised when a PDP comes back as the Incapsula interstitial."""


def fetch_micromania_all(games=None):
    """Re-check every tracked Micromania product. Pokemon-scope only."""
    # No-op fast path: don't launch a browser outside the Pokemon scope.
    if games is not None and "pokemon" not in games:
        return []

    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop FROM products WHERE platform = 'micromania'" + gsql,
            gparams).fetchall()]

    if not products:
        print("  [micromania] no tracked products.")
        return []

    results = []
    aborted = False
    with stealth_page() as (page, _ctx):
        # Warm up once on the home page to acquire incap cookies before PDPs.
        resp = goto(page, "https://www.micromania.fr/")
        time.sleep(5)
        settle(page)
        if looks_like_challenge(page.content(), resp.status if resp else None):
            print("  [micromania] ABORT: challenge on warm-up; no snapshots taken.")
            return []

        for p in products:
            try:
                results.append(_fetch_one(page, p))
            except _Challenged as c:
                print(f"  [micromania] ABORT: challenge at {c.args[0]} "
                      f"(status={c.args[1]}, bytes={c.args[2]}). "
                      f"Stopping after {len(results)} products.")
                aborted = True
                break
            time.sleep(DELAY)

    ok = sum(1 for r in results if r[1] is not None)
    known = sum(1 for r in results if r[2] is not None)
    state = "PARTIAL (aborted)" if aborted else "ok"
    print(f"  {'micromania.fr':<32} price={ok}/{len(results)}  "
          f"stock_known={known}/{len(results)}  [{state}]")
    return results


def write_snapshots(rows):
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.executemany("""
            INSERT INTO snapshots (product_id, observed_at, price_eur, available,
                                   raw_variant_count, stock_remaining)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(pid, now, price, avail, vc, stock)
              for pid, price, avail, vc, stock in rows])
        conn.commit()


from .timing import timed_main


@timed_main
def main():
    print("=== Micromania snapshot run ===")
    rows = fetch_micromania_all(["pokemon"])
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    unk = sum(1 for r in rows if r[2] is None)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  "
          f"out: {out}  unknown: {unk}")


if __name__ == "__main__":
    main()
