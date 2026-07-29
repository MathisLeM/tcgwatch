"""One-time data-quality pass: drop OPTCG / Naruto products that are actually
non-French editions (JP / EN / KO / ...).

OPTCG is tracked **French-only**, but the original `cleanup.is_foreign` looked
only at the title + URL, so editions whose language shows only in the shop's
category / breadcrumb / description — e.g. jmcards' "Japonais" category,
lerepairetcg's "Produits Japonais" breadcrumb — or via a "VO" marker
(troll2jeux's OP16 "VO" = version originale = English) were stored as 'fr'.

This re-checks every OPTCG/Naruto product with the enhanced `cleanup.is_foreign`:
  - title + URL for every product (catches "VO" and any title/URL marker);
  - for WooCommerce products it also pulls the live category/description signal
    — Store API per-product `categories`, else the product page's
    `product_cat-*` classes + breadcrumb — which is where JP usually hides.

Dry-run by default: prints what it would delete (grouped by shop) and writes an
audit CSV to data/. Pass --apply to delete (snapshots cascade via ON DELETE
CASCADE).

Run:  python -m scraper.recategorize_optcg            # dry-run
      python -m scraper.recategorize_optcg --apply    # delete
"""
import argparse
import csv
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from .db import connect
from .config import USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY, DATA_DIR
from . import cleanup

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}
OPTCG_GAMES = ("optcg", "naruto_mythos")


def _get(url, accept_json=False):
    h = dict(HEADERS)
    if accept_json:
        h["Accept"] = "application/json"
    try:
        r = requests.get(url, headers=h, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return r if r.status_code == 200 else None
    except Exception:
        return None


def wc_category_via_api(shop, pid):
    """Category names from the WC Store API single-product endpoint. Returns the
    text blob, or None if the endpoint is unavailable (so the caller can fall
    back to the product page).

    Only the *categories* are used for the language decision — the free-text
    description routinely mentions other editions / "EN" / "VO" and would cause
    false positives. The JP flag emoji (🇯🇵) in the description is the one
    exception worth keeping."""
    if not pid:
        return None
    r = _get(f"https://{shop}/wp-json/wc/store/products/{pid}", accept_json=True)
    if not r:
        return None
    try:
        d = r.json()
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    cats = " ".join(c.get("name", "") or "" for c in (d.get("categories") or []))
    sd = (d.get("short_description") or "") + " " + (d.get("description") or "")
    flag = " japonais" if ("1f1ef-1f1f5" in sd or "🇯🇵" in sd) else ""
    return f"{cats}{flag}".strip()


def wc_category_via_page(url):
    """Category signal scraped from a WooCommerce product page: the product's
    own `.posted_in` category links + the breadcrumb. Both are product-scoped
    (unlike free-text descriptions or related-product tiles), so they don't
    drag in unrelated language tokens."""
    r = _get(url)
    if not r:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    return " ".join(a.get_text(" ", strip=True) for a in soup.select(
        ".posted_in a, .product_meta a[rel=tag], "
        "nav.woocommerce-breadcrumb, .woocommerce-breadcrumb")).strip()


def check_shop(platform, shop, products):
    """Return rows from `products` that are foreign editions to be dropped.
    Each result row is the product dict plus a 'reason' string."""
    drop = []
    api_dead = False  # once the Store API 404s for a shop, use pages for the rest
    for p in products:
        title, url = p["title"] or "", p["url"] or ""
        category = ""
        # Cheap check first: title/URL alone (catches "VO" and any tag there).
        if not cleanup.is_foreign(title, url):
            if platform == "woocommerce":
                if not api_dead:
                    category = wc_category_via_api(shop, p["platform_pid"])
                    if category is None:
                        api_dead = True
                        category = wc_category_via_page(url)
                else:
                    category = wc_category_via_page(url)
                category = category or ""
                time.sleep(PER_DOMAIN_DELAY)
            if not cleanup.is_foreign(title, url, category):
                continue
        reason = "title/url" if cleanup.is_foreign(title, url) else "category"
        drop.append({**p, "category": category, "reason": reason})
    return drop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Delete the foreign products (default: dry-run report only).")
    args = ap.parse_args()

    with connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, platform, shop, platform_pid, game, set_code, title, url "
            "FROM products WHERE game IN (?, ?)", OPTCG_GAMES).fetchall()]

    by_shop = defaultdict(list)
    for r in rows:
        by_shop[(r["platform"], r["shop"])].append(r)
    print(f"Re-checking {len(rows)} OPTCG/Naruto products across {len(by_shop)} shops...\n")

    to_drop = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(check_shop, plat, shop, ps): (plat, shop)
                for (plat, shop), ps in by_shop.items()}
        for fut in as_completed(futs):
            plat, shop = futs[fut]
            try:
                to_drop.extend(fut.result())
            except Exception as e:
                print(f"  {shop:<28} ERROR: {type(e).__name__}: {e}")

    if not to_drop:
        print("No foreign editions found. Nothing to do.")
        return

    # Report, grouped by shop.
    to_drop.sort(key=lambda r: (r["shop"], r["set_code"] or ""))
    print(f"Found {len(to_drop)} foreign editions to drop:\n")
    cur_shop = None
    for r in to_drop:
        if r["shop"] != cur_shop:
            cur_shop = r["shop"]
            print(f"  {cur_shop}")
        title = (r["title"] or "").encode("ascii", "replace").decode()
        print(f"    [{r['set_code'] or '?':<10}] ({r['reason']:<8}) {title[:60]}")

    audit = DATA_DIR / "recategorize_optcg_dropped.csv"
    with open(audit, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "platform", "shop", "set_code", "game", "reason", "title", "url", "category"])
        for r in to_drop:
            w.writerow([r["id"], r["platform"], r["shop"], r["set_code"], r["game"],
                        r["reason"], r["title"], r["url"], r.get("category", "")])
    print(f"\nAudit written to: {audit}")

    if not args.apply:
        print(f"\nDry-run. Re-run with --apply to delete these {len(to_drop)} products.")
        return

    ids = [r["id"] for r in to_drop]
    with connect() as conn:
        conn.executemany("DELETE FROM products WHERE id = ?", [(i,) for i in ids])
        conn.commit()
        remaining = conn.execute(
            "SELECT COUNT(*) FROM products WHERE game IN (?, ?)", OPTCG_GAMES).fetchone()[0]
    print(f"\nDeleted {len(ids)} products (snapshots cascaded). "
          f"OPTCG/Naruto products remaining: {remaining}")


if __name__ == "__main__":
    main()
