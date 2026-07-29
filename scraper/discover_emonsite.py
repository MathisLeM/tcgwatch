"""Discover OPTCG + Naruto Mythos booster/display products on e-monsite shops.

Output: data/discovered_emonsite.xlsx (same columns as the WooCommerce file)

e-monsite is a French hosted-shop platform (detection: `X-EMS-Server` response
header). Every product detail page embeds a clean schema.org JSON-LD Product
(name, price, availability), but category listings vary, so we enumerate via the
sitemap: filter product URLs to One Piece / Naruto, then read the JSON-LD.
Category URLs have no Product JSON-LD and are skipped automatically.
"""
import re
import time
import json
import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from .shop_registry import all_shops

# mystic-ambre.fr serves an incomplete TLS chain (missing intermediate CA), which
# the OS trust store tolerates but Python's certifi bundle rejects. These are
# read-only shop pages, so skip verification for this platform.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BUILTIN_EMONSITE = ["www.mystic-ambre.fr"]
EMONSITE_SHOPS = all_shops("emonsite", _BUILTIN_EMONSITE)

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}

URL_KEEP = ("one-piece", "onepiece", "naruto")
KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ", "protege-carte",
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]


def get(url, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                             allow_redirects=True, verify=False)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.8)
    return None


def product_jsonld(html):
    """Return the JSON-LD Product dict from an e-monsite page, or None."""
    soup = BeautifulSoup(html, "html.parser")
    for b in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(b.string or b.get_text())
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return None


def parse_offer(d):
    """(price, available) from a JSON-LD Product dict."""
    o = d.get("offers") or {}
    if isinstance(o, list):
        o = o[0] if o else {}
    price = o.get("price")
    try:
        price = float(str(price).replace(",", ".")) if price not in (None, "") else None
    except Exception:
        price = None
    avail = (o.get("availability") or "")
    available = 1 if "InStock" in avail else (0 if "OutOfStock" in avail or "SoldOut" in avail else None)
    return price, available


def is_booster_or_display(title):
    t = (title or "").lower()
    if not any(k in t for k in KEEP_KW):
        return False
    if any(k in t for k in DROP_KW):
        return False
    return True


def sitemap_product_urls(shop):
    """Candidate product URLs (One Piece / Naruto) from the shop sitemap."""
    r = get(f"https://{shop}/sitemap.xml")
    if not r:
        return []
    urls = set()
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text):
        low = loc.lower()
        if low.endswith(".html") and any(k in low for k in URL_KEEP):
            urls.add(loc)
    return sorted(urls)


def discover_shop(shop):
    urls = sitemap_product_urls(shop)
    out = []

    def one(url):
        r = get(url)
        if not r:
            return None
        d = product_jsonld(r.text)
        if not d:
            return None  # category / non-product page
        price, available = parse_offer(d)
        title = d.get("name", "") or ""
        blob = (title + " " + url).lower()
        game = "naruto_mythos" if "naruto" in blob else "optcg"
        return {
            "game": game,
            "shop": shop,
            "title": title,
            "price_min": price,
            "available": available,
            "product_pid": urlparse(url).path,  # stable per-product identifier
            "url": url,
            "source": "emonsite-jsonld",
        }

    with ThreadPoolExecutor(max_workers=5) as ex:
        for row in ex.map(one, urls):
            if row and is_booster_or_display(row["title"]):
                out.append(row)
    return out


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for shop in EMONSITE_SHOPS:
        try:
            r = discover_shop(shop)
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
    out = DATA_DIR / "discovered_emonsite.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"Total rows: {len(df)}\nUnique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
