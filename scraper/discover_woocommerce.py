"""Discover OPTCG + Naruto Mythos booster/display products on WooCommerce shops.

Output: data/discovered_woocommerce.xlsx

Approach (try fastest path first):
1. WC Store API:  /wp-json/wc/store/products?search=<q>&per_page=100   (clean JSON)
2. Fallback HTML: /?s=<q>&post_type=product                            (WC search results)
3. Parse uniformly, filter to booster/display, save with same columns as PS/Shopify.
"""
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote_plus
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from . import cleanup

_BUILTIN_WOOCOMMERCE = [
    "www.cardshunter.fr", "shop.cafemeisia.com", "www.lesdesmaskes.fr",
    "maniatcg.com", "www.guizettefamily.com", "lecoindesbarons.com",
    "ludotrotter.fr", "www.atmos-arena.com", "lestresorsdutcg.fr",
    "buy-the-game.fr", "www.placeofgeek.fr", "www.pokelite.fr",
    "collectstoys.com", "diaboluscompagnie.com", "pyrosleep.fr",
    "ecardstore.fr", "manga-story.fr", "www.yukistore.fr",
]
from .shop_registry import all_shops
WOOCOMMERCE_SHOPS = all_shops("woocommerce", _BUILTIN_WOOCOMMERCE)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml;q=0.9,application/json;q=0.9,*/*;q=0.8",
}

QUERIES = [("optcg", "one piece"), ("naruto_mythos", "naruto mythos")]

KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ",
           # ED.2 / 2nd edition reprints (mostly Naruto Konoha Shidō ED.2)
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]


def get(url, retries=2, accept_json=False):
    h = dict(HEADERS)
    if accept_json:
        h["Accept"] = "application/json"
    for i in range(retries):
        try:
            r = requests.get(url, headers=h, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.8)
    return None


def parse_price_cents(v):
    """WC Store API returns prices as a string of minor units OR a float. Normalize."""
    if v is None: return None
    try:
        s = str(v).replace(",", ".")
        n = float(s)
        # If the value has no decimal point and is >100, it's cents (e.g. "9990" = €99.90)
        if "." not in s and n > 99:
            return n / 100
        return n
    except Exception:
        return None


def is_booster_or_display(title, url=""):
    slug = ""
    if url:
        try:
            slug = urlparse(url).path.split("/")[-1].lower().replace("-", " ").replace("_", " ")
        except Exception:
            pass
    t = (title.lower() + " " + slug).strip()
    if not any(k in t for k in KEEP_KW): return False
    if any(k in t for k in DROP_KW): return False
    return True


def _api_category_blob(p):
    """Classification signal from a WC Store API product: the category names,
    plus a synthetic "japonais" when the description carries the JP flag (🇯🇵).

    Only the *categories* are trustworthy for language — the free-text
    description routinely mentions other editions / "EN" / "VO" and would cause
    false positives, so it is used solely to detect the flag emoji."""
    cats = " ".join(c.get("name", "") or "" for c in (p.get("categories") or []))
    sd = (p.get("short_description") or "") + " " + (p.get("description") or "")
    flag = " japonais" if ("1f1ef-1f1f5" in sd or "🇯🇵" in sd) else ""
    return f"{cats}{flag}".strip()


def _html_category_blob(tile):
    """Classification signal from a WC search-result tile: the `product_cat-*`
    CSS classes carry the product's categories (e.g. `product_cat-produits-op
    -japonais`), which is the only place the language shows on shops without the
    Store API (e.g. lerepairetcg)."""
    cats = [c[len("product_cat-"):].replace("-", " ")
            for c in (tile.get("class") or []) if c.startswith("product_cat-")]
    return " ".join(cats)


def fetch_via_store_api(shop, query):
    """Try /wp-json/wc/store/products. Returns rows or None if endpoint unavailable."""
    rows = []
    for per_page in (100,):
        for page in range(1, 6):
            url = f"https://{shop}/wp-json/wc/store/products?search={quote_plus(query)}&per_page={per_page}&page={page}"
            r = get(url, accept_json=True)
            if not r: return None if page == 1 else rows
            try:
                items = r.json()
            except Exception:
                return None if page == 1 else rows
            if not isinstance(items, list): return None if page == 1 else rows
            if not items: break
            for p in items:
                name = p.get("name", "") or ""
                permalink = p.get("permalink", "") or ""
                category = _api_category_blob(p)
                # OPTCG is FR-only: drop any non-French edition (JP/EN/KO/...).
                # The category/description catches editions whose language is
                # absent from the title (e.g. jmcards' "Japonais" category).
                if cleanup.is_foreign(name, permalink, category):
                    continue
                prices = p.get("prices", {}) or {}
                price = parse_price_cents(prices.get("price"))
                rows.append({
                    "title": name,
                    "url": permalink,
                    "price_min": price,
                    "available": p.get("is_in_stock"),
                    "product_pid": p.get("id"),
                    "category": category,
                })
            if len(items) < per_page: break
    return rows


def fetch_via_html_search(shop, query):
    """Fallback: scrape /?s=...&post_type=product"""
    rows = []
    base = f"https://{shop}/?s={quote_plus(query)}&post_type=product"
    url = base
    for _ in range(5):  # up to 5 pages
        r = get(url)
        if not r: break
        soup = BeautifulSoup(r.text, "html.parser")
        tiles = soup.select("ul.products li.product, .products .product, li.product")
        if not tiles:
            break
        for t in tiles:
            title_el = t.select_one(".woocommerce-loop-product__title, .product-title, h2 a, h3 a, h2, h3")
            title = title_el.get_text(strip=True) if title_el else ""
            a = t.select_one("a.woocommerce-LoopProduct-link, a.woocommerce-loop-product__link, a[href]")
            href = a.get("href") if a else ""
            price_el = t.select_one(".price ins .amount, .price .amount, .price")
            price = None
            if price_el:
                m = re.search(r"(\d{1,4}(?:[ .]\d{3})*[,.]\d{2})", price_el.get_text())
                if m:
                    try: price = float(m.group(1).replace(" ", "").replace(".", "").replace(",", ".") if "," in m.group(1) else m.group(1).replace(" ", ""))
                    except Exception: pass
            # availability heuristic
            out_of = t.select_one(".outofstock, .out-of-stock, .out_of_stock")
            add_btn = t.select_one("a.add_to_cart_button, .button.add_to_cart_button")
            available = None
            if out_of: available = False
            elif add_btn: available = True
            pid = ""
            cls = " ".join(t.get("class") or [])
            m = re.search(r"post-(\d+)", cls)
            if m: pid = m.group(1)
            category = _html_category_blob(t)
            # OPTCG is FR-only: drop non-French editions. The `product_cat-*`
            # classes are the only language signal on Store-API-less shops.
            if cleanup.is_foreign(title, href, category):
                continue
            if title and href:
                rows.append({"title": title, "url": href, "price_min": price,
                             "available": available, "product_pid": pid,
                             "category": category})
        # next page
        next_link = soup.select_one('a.next, link[rel="next"], .nav-previous a, .pagination .next a')
        if next_link and next_link.get("href"):
            url = urljoin(url, next_link["href"])
        else:
            break
        time.sleep(0.3)
    return rows


def discover_shop(shop):
    out_rows = []
    for game_label, q in QUERIES:
        rows = fetch_via_store_api(shop, q)
        source = "store-api"
        if rows is None or not rows:
            rows = fetch_via_html_search(shop, q)
            source = "html-search"
        if not rows:
            continue
        seen = set()
        for r in rows:
            key = (str(r.get("product_pid") or ""), r["title"])
            if key in seen: continue
            seen.add(key)
            if not is_booster_or_display(r["title"], r.get("url", "")): continue
            r["game"] = game_label
            r["shop"] = shop
            r["source"] = source
            out_rows.append(r)
    return out_rows


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(discover_shop, s): s for s in WOOCOMMERCE_SHOPS}
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
    if "category" not in df.columns:
        df["category"] = ""
    df = df[["game", "shop", "title", "set", "price_min", "price_max",
             "available", "product_pid", "url", "source", "category"]]
    df["_n"] = df["title"].str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    df = df.sort_values(["game", "_n", "shop"]).drop(columns=["_n"])
    out = DATA_DIR / "discovered_woocommerce.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"Total rows: {len(df)}")
    print(f"Unique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
