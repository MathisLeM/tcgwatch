"""Discover OPTCG + Naruto Mythos booster/display products on FantasySphere.

Output: data/discovered_fantasysphere.xlsx (same columns as the WooCommerce file)

FantasySphere is a bespoke custom storefront (no standard CMS signature). The
category listing is the clean data source — each `.product-item-info` tile holds
title, price and stock; the product detail page mixes in cross-sell tiles so its
main price is ambiguous. We therefore crawl the category pages (paginated via
`?page=N`) and parse the tiles directly.
"""
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from .shop_registry import all_shops

_BUILTIN_FANTASYSPHERE = ["www.fantasysphere.net"]
FANTASYSPHERE_SHOPS = all_shops("fantasysphere", _BUILTIN_FANTASYSPHERE)

# host -> list of (game, category_url)
CATEGORIES = {
    "www.fantasysphere.net": [
        ("optcg", "https://www.fantasysphere.net/jeux-de-cartes-a-collectionner/one-piece-tcg/"),
        ("naruto_mythos", "https://www.fantasysphere.net/jeux-de-cartes-a-collectionner/naruto-mythos-tcg/"),
    ],
}

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}

KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ", "proteges cartes",
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]

PID_RE = re.compile(r"/product/[a-z0-9-]+-(\d{5,10})")


def get(url, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.8)
    return None


def parse_price(text):
    if not text:
        return None
    m = re.search(r"(\d{1,4}(?:[ .]\d{3})*[,.]\d{2})", text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "")
    try:
        return float(raw.replace(".", "").replace(",", ".") if "," in raw else raw)
    except Exception:
        return None


def is_booster_or_display(title):
    t = (title or "").lower()
    if not any(k in t for k in KEEP_KW):
        return False
    if any(k in t for k in DROP_KW):
        return False
    return True


def parse_tile(tile):
    """(pid, url, title, price, available) from one .product-item-info tile."""
    a = tile.select_one('a[href*="/product/"]')
    if not a:
        return None
    url = a.get("href", "")
    m = PID_RE.search(url)
    pid = m.group(1) if m else ""
    name_el = tile.select_one(".product-item-name")
    title = name_el.get_text(" ", strip=True) if name_el else ""
    # promo price wins over base/strikethrough price
    price_el = tile.select_one(".product-item-price.promo") or tile.select_one(".product-item-price")
    price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
    out = tile.select_one(".product-item-label.outofstock, .outofstock")
    available = 0 if out else 1
    return pid, url, title, price, available


def fetch_category(base_url, max_pages=15):
    """Paginate a category via ?page=N, accumulating distinct tiles."""
    rows, seen = [], set()
    for page in range(1, max_pages + 1):
        sep = "&" if "?" in base_url else "?"
        r = get(f"{base_url}{sep}page={page}" if page > 1 else base_url)
        if not r:
            break
        tiles = BeautifulSoup(r.text, "html.parser").select(".product-item-info")
        new = 0
        for t in tiles:
            parsed = parse_tile(t)
            if not parsed or not parsed[0] or parsed[0] in seen:
                continue
            seen.add(parsed[0])
            rows.append(parsed)
            new += 1
        if new == 0:
            break
        time.sleep(0.3)
    return rows


def discover_shop(shop):
    out_rows, seen = [], set()
    for game_label, url in CATEGORIES.get(shop, []):
        for pid, purl, title, price, avail in fetch_category(url):
            if not pid or pid in seen:
                continue
            if not is_booster_or_display(title):
                continue
            seen.add(pid)
            # normalize relative URLs
            full = purl if purl.startswith("http") else f"https://{shop}{purl}"
            out_rows.append({
                "game": game_label,
                "shop": shop,
                "title": title,
                "price_min": price,
                "available": avail,
                "product_pid": pid,
                "url": full,
                "source": "fs-category",
            })
    return out_rows


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(discover_shop, s): s for s in FANTASYSPHERE_SHOPS}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                r = fut.result()
                print(f"  {shop:<28} {len(r)} products")
                all_rows.extend(r)
            except Exception as e:
                print(f"  {shop:<28} ERROR: {type(e).__name__}: {e}")

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("\nNo products found.")
        return
    df["price_max"] = df["price_min"]
    df["set"] = ""
    df = df[["game", "shop", "title", "set", "price_min", "price_max",
             "available", "product_pid", "url", "source"]]
    df["_n"] = df["title"].str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    df = df.sort_values(["game", "_n", "shop"]).drop(columns=["_n"])
    out = DATA_DIR / "discovered_fantasysphere.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"Total rows: {len(df)}\nUnique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
