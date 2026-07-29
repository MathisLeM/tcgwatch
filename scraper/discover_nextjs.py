"""Discover OPTCG booster/display products on Next.js shops (PlayIn, Parkage).

Output: data/discovered_nextjs.xlsx (same columns as the WooCommerce file)

These two are bespoke Next.js storefronts whose catalogue grids are fetched
client-side, so each needs its own strategy (no shared scraping path):

* Parkage -> Strapi backend JSON API.
    https://back.parkage.com/api/parkage/search/get?product_type_id=<id>&locale=fr&limit=N
    Resolve a category permalink once via /api/parkage/permalink/params to get
    the product_type_id / category_id. Products carry price/stock inline.
* PlayIn  -> products sitemap + schema.org JSON-LD.
    The catalogue is client-rendered, but every product is in the products
    sitemap and every detail page embeds a JSON-LD Product with price +
    availability. We filter the sitemap to One Piece sealed URLs, then read the
    JSON-LD per product.
"""
import re
import json
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from .shop_registry import all_shops
from .cleanup import is_foreign

_BUILTIN_NEXTJS = ["www.play-in.com", "www.parkage.com"]
NEXTJS_SHOPS = all_shops("nextjs", _BUILTIN_NEXTJS)

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}

KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ", "rangement",
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]

# ------------------------------------------------------------------ Parkage --
PARKAGE_API = "https://back.parkage.com/api/parkage/search/get"
# host -> list of (game, query-params, category-page-url-for-display)
PARKAGE_CONFIG = {
    "www.parkage.com": [
        ("optcg", {"product_type_id": "9885"},
         "https://www.parkage.com/fr/boites-de-boosters-one-piece-card-game"),
    ],
}

# -------------------------------------------------------------------- PlayIn --
PLAYIN_SITEMAP_INDEX = "https://www.play-in.com/sitemap_index.xml"
PLAYIN_SLUG_KEEP = ("booster", "display", "boite-de-24", "boite-de-12", "coffret")
PLAYIN_SLUG_DROP = ("rangement", "tapis", "sleeve", "protege", "deck-de-demarrage",
                    "playmat", "premium-card-collection")


def _get(url, params=None, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS,
                             timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.8)
    return None


def is_booster_or_display(title):
    t = (title or "").lower()
    if not any(k in t for k in KEEP_KW):
        return False
    if any(k in t for k in DROP_KW):
        return False
    return True


# ------------------------------------------------------------------ Parkage --
def parkage_price(p):
    """Pick the live selling price from the Strapi product object."""
    if p.get("isDiscount") and p.get("price_discount"):
        return float(p["price_discount"])
    if p.get("price"):
        return float(p["price"])
    if p.get("price_catalog"):
        return float(p["price_catalog"])
    return None


def parkage_rows(p):
    """Normalize one Strapi product to a discovery row dict (minus game/url)."""
    name = p.get("name") or p.get("name_fr") or p.get("name_en") or ""
    stock = p.get("stock")
    return {
        "title": name,
        "price_min": parkage_price(p),
        "available": 1 if p.get("isStock") else 0,
        "product_pid": str(p.get("id")),
        "stock": stock if isinstance(stock, int) and stock > 0 else None,
    }


def discover_parkage(shop):
    out, seen = [], set()
    for game, params, page_url in PARKAGE_CONFIG.get(shop, []):
        r = _get(PARKAGE_API, params={**params, "locale": "fr", "limit": "500"})
        if not r:
            continue
        try:
            items = r.json().get("data", {}).get("list", []) or []
        except Exception:
            continue
        for p in items:
            # Language isn't in the product name on Parkage; the Strapi `lang`
            # field is the reliable signal. Keep French only (drop jp/en/kr/cn).
            lang = (p.get("lang") or "").lower()
            if lang and not lang.startswith("fr"):
                continue
            row = parkage_rows(p)
            pid = row["product_pid"]
            if not pid or pid in seen:
                continue
            if not is_booster_or_display(row["title"]):
                continue
            seen.add(pid)
            row.update(game=game, shop=shop, url=page_url, source="parkage-api")
            out.append(row)
    return out


# -------------------------------------------------------------------- PlayIn --
def playin_product_jsonld(html):
    """Return the JSON-LD Product dict from a PlayIn detail page, or None."""
    soup = BeautifulSoup(html, "html.parser")
    for b in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(b.string or b.get_text())
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return None


def playin_parse_offer(d):
    """(price, available) from a JSON-LD Product dict."""
    o = d.get("offers") or {}
    if isinstance(o, list):
        o = o[0] if o else {}
    price = o.get("price")
    try:
        price = float(price) if price is not None else None
    except Exception:
        price = None
    avail = o.get("availability") or ""
    available = 1 if "InStock" in avail else (0 if "OutOfStock" in avail or "SoldOut" in avail else None)
    return price, available


def _playin_sitemap_urls():
    """Collect One Piece sealed-product /fr/ URLs from the products sitemap(s)."""
    r = _get(PLAYIN_SITEMAP_INDEX)
    if not r:
        return []
    sitemaps = [u for u in re.findall(r"https://[^<]+\.xml", r.text)
                if "/produits/sitemap/" in u]
    urls = set()
    for sm in sitemaps:
        rs = _get(sm)
        if not rs:
            continue
        for loc in re.findall(r"https://www\.play-in\.com/fr/produit/\d+/[a-z0-9-]+", rs.text):
            slug = loc.rsplit("/", 1)[-1]
            if "one-piece" not in slug:
                continue
            if not any(k in slug for k in PLAYIN_SLUG_KEEP):
                continue
            if any(k in slug for k in PLAYIN_SLUG_DROP):
                continue
            if is_foreign("", loc):   # skip -en / -ko / opk slugs up front
                continue
            urls.add(loc)
    return sorted(urls)


def discover_playin(shop):
    urls = _playin_sitemap_urls()
    out = []

    def one(url):
        r = _get(url)
        if not r:
            return None
        d = playin_product_jsonld(r.text)
        if not d:
            return None
        price, available = playin_parse_offer(d)
        m = re.search(r"/produit/(\d+)/", url)
        return {
            "game": "optcg",
            "shop": shop,
            "title": d.get("name", "") or "",
            "price_min": price,
            "available": available,
            "product_pid": m.group(1) if m else "",
            "url": url,
            "source": "playin-jsonld",
        }

    with ThreadPoolExecutor(max_workers=6) as ex:
        for row in ex.map(one, urls):
            if row and is_booster_or_display(row["title"]):
                out.append(row)
            time.sleep(0)  # cooperative; map already parallel
    return out


# -------------------------------------------------------------------- common --
def discover_shop(shop):
    if shop in PARKAGE_CONFIG:
        return discover_parkage(shop)
    if "play-in" in shop:
        return discover_playin(shop)
    return []


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(discover_shop, s): s for s in NEXTJS_SHOPS}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                r = fut.result()
                src = r[0]["source"] if r else "-"
                print(f"  {shop:<28} {len(r)} products  ({src})")
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
    out = DATA_DIR / "discovered_nextjs.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"Total rows: {len(df)}")
    print(f"Unique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
