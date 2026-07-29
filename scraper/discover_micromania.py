"""Discover sealed Pokemon products on micromania.fr (Imperva/Incapsula-gated).

Micromania is a Salesforce Commerce Cloud (Demandware) shop with no public JSON
API and an Incapsula JS challenge in front of it, so we drive a single stealthy
headless Chromium session (see `stealth_browser`). We crawl the Pokemon card
category grid (paginated via the SFCC `Search-Show?cgid=...&start=&sz=` endpoint),
extract each tile (id / title / url / price / dispoweb), then visit a *capped*
number of detail pages to enrich the description for the sealed/kind gate.

Pipeline integration
--------------------
Micromania can't share the requests-based `discover_pokemon` flow (it needs a
browser), so this module is self-contained: it discovers, categorizes with
`scraper.games.pokemon`, and upserts directly into `products` (+ one snapshot)
with `ON CONFLICT`. To stay compatible with `categorize_pokemon.load()` — which
deletes pokemon rows before reloading — that DELETE was narrowed to
`... AND platform != 'micromania'`, so the two pipelines never clobber each other.

Politeness / safety
-------------------
One reused browser session, sequential PDP visits with a >= PER_DOMAIN_DELAY
delay, and an Incapsula-challenge guard that aborts cleanly (logs + stops) if a
page comes back as the interstitial. Keep `--limit` small for real runs.

Run:
    python -m scraper.discover_micromania --limit 3 --dry-run
    python -m scraper.discover_micromania            # full (be polite!)
"""
from __future__ import annotations

import argparse
import datetime as dt
import time

from .config import PER_DOMAIN_DELAY
from .db import connect, init_db
from .games import pokemon
from .micromania_parse import (parse_listing_tiles, parse_detail_description,
                               parse_detail_title)
from .stealth_browser import stealth_page, goto, settle, looks_like_challenge

PLATFORM = "micromania"
SHOP = "micromania.fr"
BASE = "https://www.micromania.fr"

# SFCC category grid endpoint. `cgid=toutes-les-cartes-pokemon` is the full
# Pokemon trading-card category (boosters / displays / coffrets / decks / tins).
# `sz` is the page size SFCC returns; `start` is the offset for pagination.
CATEGORY_CGID = "toutes-les-cartes-pokemon"
GRID_URL = (BASE + "/on/demandware.store/Sites-Micromania-Site/fr_FR/"
            "Search-Show?cgid={cgid}&start={start}&sz={sz}")
# Marketing landing page (carousels) — a cheap first hit to acquire incap cookies.
CATEGORY_HOME = BASE + "/c/cartespokemon"

PAGE_SIZE = 60          # tiles per grid request
MAX_PAGES = 12          # hard cap (720 tiles) so a layout glitch can't loop forever
HOME_SETTLE = 6         # seconds to let the Incapsula challenge run on first hit


def _extra(title: str, description: str) -> str:
    return " ".join(p for p in (description,) if p)


def crawl(page, limit: int | None, visit_details: bool = True) -> list[dict]:
    """Crawl the Pokemon category grid; return raw product dicts.

    Returns a list of {platform_pid, title, url, price, available, ean,
    description}. Stops early on `limit`, on an empty page, or on a challenge.
    """
    # 1) Warm up on the marketing page to clear the challenge / get incap cookies.
    print(f"[micromania] warm-up GET {CATEGORY_HOME}")
    resp = goto(page, CATEGORY_HOME)
    time.sleep(HOME_SETTLE)
    settle(page)
    html = page.content()
    if looks_like_challenge(html, resp.status if resp else None):
        print("[micromania] ABORT: Incapsula challenge on warm-up page "
              f"(status={resp.status if resp else None}, bytes={len(html)}).")
        return []

    # 2) Page through the category grid.
    products: dict[str, dict] = {}
    for pageno in range(MAX_PAGES):
        start = pageno * PAGE_SIZE
        url = GRID_URL.format(cgid=CATEGORY_CGID, start=start, sz=PAGE_SIZE)
        print(f"[micromania] grid start={start} sz={PAGE_SIZE}")
        resp = goto(page, url)
        settle(page)
        html = page.content()
        status = resp.status if resp else None
        if looks_like_challenge(html, status):
            print(f"[micromania] ABORT: challenge on grid page start={start} "
                  f"(status={status}, bytes={len(html)}).")
            break
        tiles = parse_listing_tiles(html, BASE)
        new = 0
        for t in tiles:
            if t["platform_pid"] not in products:
                products[t["platform_pid"]] = t
                new += 1
        print(f"  parsed {len(tiles)} tiles, {new} new (total {len(products)})")
        if new == 0:
            break  # reached the end of the grid (or duplicate carousel content)
        if limit and len(products) >= limit:
            break
        time.sleep(max(PER_DOMAIN_DELAY, 1.0))

    rows = list(products.values())
    if limit:
        rows = rows[:limit]

    # 3) Optionally enrich with the PDP description (used by the sealed gate).
    if visit_details:
        from bs4 import BeautifulSoup
        for i, r in enumerate(rows):
            if not r.get("url"):
                r["description"] = ""
                continue
            time.sleep(max(PER_DOMAIN_DELAY, 1.0))
            resp = goto(page, r["url"])
            settle(page)
            html = page.content()
            if looks_like_challenge(html, resp.status if resp else None):
                print(f"[micromania] ABORT details: challenge on {r['url']}")
                # leave remaining descriptions empty; don't hammer further
                for rest in rows[i:]:
                    rest.setdefault("description", "")
                break
            soup = BeautifulSoup(html, "html.parser")
            r["description"] = parse_detail_description(soup)
            # prefer a clean PDP title if the grid title looked truncated
            dt_title = parse_detail_title(soup)
            if dt_title and len(dt_title) > len(r.get("title") or ""):
                r["title"] = dt_title
    else:
        for r in rows:
            r.setdefault("description", "")
    return rows


def categorize(rows: list[dict]) -> list[dict]:
    """Apply the sealed gate + Pokemon categorization (language/set/series/kind)."""
    kept = []
    dropped = 0
    for r in rows:
        title = r.get("title") or ""
        url = r.get("url") or ""
        desc = r.get("description") or ""
        lang = pokemon.detect_language(title, url, desc)  # Micromania is FR
        if not pokemon.is_sealed(title, desc, language=lang, shop=SHOP):
            dropped += 1
            continue
        sets = pokemon.extract_sets(title, url, lang, desc)
        set_code = sets[0] if sets else ""
        blob = f"{title} {desc} {url}".lower()
        if "pokemon" not in blob and "pokémon" not in blob and not set_code:
            dropped += 1
            continue
        kind = pokemon.classify_kind(title, extra=desc, language=lang)
        series = pokemon.extract_series(title, url, lang, desc, set_code)
        kept.append({
            "platform_pid": str(r["platform_pid"]),
            "language": lang, "set": set_code, "set_codes": ";".join(sets),
            "series": series, "kind": kind, "title": title, "url": url,
            "price": r.get("price"), "available": r.get("available"),
        })
    print(f"[micromania] sealed kept {len(kept)}, dropped {dropped}")
    return kept


def load(rows: list[dict]) -> int:
    """Upsert categorized rows into products (+ one snapshot each). Idempotent."""
    init_db()
    today = dt.date.today().isoformat()
    now = dt.datetime.now().isoformat(timespec="seconds")
    ins = 0
    with connect() as conn:
        cat = {(r["language"], r["set_code"], r["kind"]): r["id"] for r in conn.execute(
            "SELECT id, language, set_code, kind FROM catalog WHERE game='pokemon'")}
        for r in rows:
            if not r["platform_pid"]:
                continue
            cid = cat.get((r["language"], r["set"], r["kind"]))
            conn.execute("""
                INSERT INTO products (platform, shop, platform_pid, game, language,
                                      set_code, set_codes, series, kind, catalog_id,
                                      title, url, first_seen_at)
                VALUES (?, ?, ?, 'pokemon', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, shop, platform_pid) DO UPDATE SET
                    language=excluded.language, set_code=excluded.set_code,
                    set_codes=excluded.set_codes, series=excluded.series,
                    kind=excluded.kind, catalog_id=excluded.catalog_id,
                    title=excluded.title, url=excluded.url
            """, (PLATFORM, SHOP, r["platform_pid"], r["language"], r["set"],
                  r["set_codes"], r["series"], r["kind"], cid, r["title"], r["url"], today))
            pid = conn.execute(
                "SELECT id FROM products WHERE platform=? AND shop=? AND platform_pid=?",
                (PLATFORM, SHOP, r["platform_pid"])).fetchone()[0]
            price = None if r.get("price") is None else float(r["price"])
            avail = None if r.get("available") is None else int(r["available"])
            conn.execute("""
                INSERT INTO snapshots (product_id, observed_at, price_eur, available,
                                       raw_variant_count, stock_remaining)
                VALUES (?, ?, ?, ?, NULL, NULL)
            """, (pid, now, price, avail))
            ins += 1
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM products WHERE platform='micromania'").fetchone()[0]
    print(f"[micromania] upserted {ins} listings. Total micromania products in DB: {n}")
    return ins


def main(argv=None):
    ap = argparse.ArgumentParser(description="Discover sealed Pokemon on micromania.fr")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N discovered products (polite testing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="crawl + categorize but do not write to the DB")
    ap.add_argument("--no-details", action="store_true",
                    help="skip per-product PDP visits (grid data only)")
    ap.add_argument("--headful", action="store_true", help="visible browser (debug)")
    args = ap.parse_args(argv)

    with stealth_page(headful=args.headful) as (page, _ctx):
        rows = crawl(page, limit=args.limit, visit_details=not args.no_details)
    print(f"[micromania] discovered {len(rows)} raw products")
    if not rows:
        return
    kept = categorize(rows)
    print("\nSample categorized:")
    for r in kept[:5]:
        price = f"{r['price']:.2f}" if r.get("price") is not None else "?"
        print(f"  [{r['set'] or '-':<8}] {r['kind']:<9} {price:>7}  "
              f"avail={r['available']}  {r['title'][:50]}")
    if args.dry_run:
        print("\n[dry-run] not writing to DB.")
        return
    if kept:
        load(kept)


if __name__ == "__main__":
    main()
