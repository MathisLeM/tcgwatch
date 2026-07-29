"""Discover OPTCG + Naruto Mythos booster/display products on Powerboutique shops.

Output: data/discovered_powerboutique.xlsx (same columns as the WooCommerce file)

Powerboutique is a French e-commerce SaaS. Detection signature: pages reference
`/dhtml/` endpoints and product tiles use `.product_box` with an `idproduit`
attribute; category listings paginate via `?numPage=N` (60 products/page).

There is no JSON/search API, so — like PrestaShop — each shop declares the
category URL(s) to crawl (DIRECT_URLS / extra_shops.json "direct_urls").
Per category page we parse each `.product_box`:
  - idproduit          -> platform product id
  - img[title]         -> title
  - .bp_image a[href]  -> product URL
  - .bp_prix           -> price ("12,90 €")
  - .bp_stock          -> availability ("En stock" / "Rupture de stock")
"""
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from .shop_registry import all_shops, all_direct_urls

_BUILTIN_POWERBOUTIQUE = [
    "www.antretemps.com", "www.lafourmiludique.fr",
]
POWERBOUTIQUE_SHOPS = all_shops("powerboutique", _BUILTIN_POWERBOUTIQUE)

# Category URLs to crawl per shop. scope="dedicated" => category is OPTCG-only,
# accept any booster/display; scope="generic" => require explicit OPTCG signal.
DIRECT_URLS = {
    "www.antretemps.com": [
        ("optcg", "https://www.antretemps.com/jeux-de-cartes/one-piece-c899.html", "dedicated")],
    "www.lafourmiludique.fr": [
        ("optcg", "https://www.lafourmiludique.fr/jeux-de-cartes-et-jcc/one-piece-c58.html", "dedicated")],
}

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

PER_PAGE = 60  # Powerboutique returns 60 product tiles per category page

KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ",
           # ED.2 / 2nd edition reprints (mostly Naruto Konoha Shidō ED.2)
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]


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
    """'12,90 €' / '1 194,90 €' -> float."""
    if not text:
        return None
    m = re.search(r"(\d{1,4}(?:[ .]\d{3})*[,.]\d{2})", text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "")
    try:
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        return float(raw)
    except Exception:
        return None


def parse_availability(text):
    """'.bp_stock' text -> True / False / None."""
    if not text:
        return None
    t = text.lower()
    if "rupture" in t or "épuisé" in t or "epuise" in t or "indisponible" in t:
        return False
    if "stock" in t or "disponible" in t:
        return True
    return None


def is_booster_or_display(title, url=""):
    slug = ""
    if url:
        try:
            from urllib.parse import urlparse
            slug = urlparse(url).path.split("/")[-1].lower().replace("-", " ").replace("_", " ")
        except Exception:
            pass
    t = (title.lower() + " " + slug).strip()
    if not any(k in t for k in KEEP_KW):
        return False
    if any(k in t for k in DROP_KW):
        return False
    return True


def parse_box(box):
    """Extract (pid, url, title, price, available) from one .product_box."""
    el = box.select_one("[idproduit]")
    pid = el.get("idproduit") if el else ""
    a = box.select_one(".bp_image a[href]") or box.select_one("a[href]")
    url = a.get("href") if a else ""
    img = box.select_one("img[title]") or box.select_one("img[alt]")
    title = ((img.get("title") if img else "") or (img.get("alt") if img else "") or "").strip()
    price_el = box.select_one(".bp_prix")
    price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
    stock_el = box.select_one(".bp_stock")
    avail = parse_availability(stock_el.get_text(" ", strip=True)) if stock_el else None
    return pid, url, title, price, avail


def fetch_category(shop, base_url, max_pages=15):
    """Paginate one category via ?numPage=N; return list of parsed boxes."""
    rows = []
    sep = "&" if "?" in base_url else "?"
    for page in range(1, max_pages + 1):
        url = f"{base_url}{sep}numPage={page}"
        r = get(url)
        if not r:
            break
        boxes = BeautifulSoup(r.text, "html.parser").select(".product_box")
        if not boxes:
            break
        for b in boxes:
            rows.append(parse_box(b))
        if len(boxes) < PER_PAGE:
            break
        time.sleep(0.3)
    return rows


def discover_shop(shop):
    """Return a list of dicts (one per matching product) for a shop."""
    urls = all_direct_urls(DIRECT_URLS).get(shop, [])
    out_rows, seen = [], set()
    for game_label, url, scope in urls:
        for pid, purl, title, price, avail in fetch_category(shop, url):
            if not pid or pid in seen:
                continue
            if not is_booster_or_display(title, purl):
                continue
            if scope == "generic" and not any(
                    k in title.lower() for k in ("one piece", "onepiece", "optcg")):
                continue
            seen.add(pid)
            out_rows.append({
                "game": game_label,
                "shop": shop,
                "title": title,
                "price_min": price,
                "available": avail,
                "product_pid": pid,
                "url": purl,
                "source": "pb-category",
            })
    return out_rows


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(discover_shop, s): s for s in POWERBOUTIQUE_SHOPS}
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
    out = DATA_DIR / "discovered_powerboutique.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"Total rows: {len(df)}")
    print(f"Unique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
