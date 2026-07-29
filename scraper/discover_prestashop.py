"""Discover OPTCG + Naruto Mythos booster/display products on PrestaShop shops.

Output: data/discovered_prestashop.xlsx

Approach:
1. For each of the 26 confirmed PS shops, hit the search endpoint.
   - Standard:    /recherche?controller=search&s=<q>
   - ambjolisearch fallback: /module/ambjolisearch/jolisearch?s=<q>
   - iqitsearch fallback:    /module/iqitsearch/searchiqit?s=<q>
2. Search for "one piece" and "naruto mythos" separately.
3. Parse product tiles with multiple selector fallbacks (theme variance).
4. Filter to booster/display only.
5. Stock: read .product-availability when present, else None.
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

_BUILTIN_PRESTASHOP = [
    "www.bcd-jeux.fr", "fungamesnet.fr", "www.hobby-max.fr",
    "ikaipaka.com", "investcollect.com", "kamegeek.fr",
    "lesamisludiques.com", "lesgentlemendujeu.com", "www.ludifolie.com",
    "luditoyz-jeux-jouets.com", "www.ludocortex.fr", "magic55.fr",
    "www.mondes-fantastiques.com", "www.monsieurde.com", "nordikards.com",
    "www.pokezenith.com", "rebelforge.fr", "www.starplayer.fr",
    "www.tales-of-games.fr", "tontonpiketpok.com", "www.tzp.fr",
    "www.variantes.com", "www.warhousegames.com", "www.wavgames.fr",
]
from .shop_registry import all_shops, all_direct_urls
PRESTASHOP_SHOPS = all_shops("prestashop", _BUILTIN_PRESTASHOP)

# Shops where the standard /recherche endpoint returns 0 — use direct category URLs instead.
# Each tuple: (game_label, url, scope). scope="dedicated" => category is OPTCG-only,
# accept any booster/display. scope="generic" => category mixes TCGs, require explicit
# OPTCG signal in title.
DIRECT_URLS = {
    "rebelforge.fr":          [("optcg", "https://rebelforge.fr/fr/1766-one-piece-tcg", "dedicated")],
    "www.tales-of-games.fr":  [("optcg", "https://www.tales-of-games.fr/344-jcc-one-piece", "dedicated")],
    "www.warhousegames.com":  [("optcg", "https://www.warhousegames.com/store/fr/1172-one-piece", "dedicated")],
    "magic55.fr":             [("optcg", "https://magic55.fr/recherche?controller=search&s=one+piece+booster", "dedicated")],
}

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

SEARCH_PATHS = [
    "/recherche?controller=search&s={q}",
    "/module/ambjolisearch/jolisearch?s={q}",
    "/module/iqitsearch/searchiqit?s={q}",
    "/search?controller=search&s={q}",
]

QUERIES = [("optcg", "one piece"), ("naruto_mythos", "naruto mythos")]

KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ",
           # ED.2 / 2nd edition reprints (mostly Naruto Konoha Shidō ED.2)
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]

TILE_SELECTORS = [
    "article.product-miniature", ".js-product-miniature",
    ".product-miniature", "article[data-id-product]",
    ".thumbnail-container", ".product-item",
]
TITLE_SELECTORS = [".product-title a", ".product-title", "h2.h3 a", "h3.h3 a",
                   ".product-name", "h2 a", "h3 a"]
PRICE_SELECTORS = [".product-price-and-shipping .price", ".price", ".product-price",
                   "[itemprop=price]"]
AVAIL_SELECTORS = [".product-availability", ".availability", ".label-stock",
                   ".out-of-stock", ".product-flag.on-sale"]


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
    if not text: return None
    text = text.replace(" ", " ").replace("&nbsp;", " ")
    m = re.search(r"(\d{1,4}(?:[ .]\d{3})*[,.]\d{2})", text)
    if not m: return None
    raw = m.group(1).replace(" ", "").replace(".", "").replace(",", ".") if "," in m.group(1) else m.group(1).replace(" ", "")
    try:
        return float(raw)
    except Exception:
        return None


def select_first(node, selectors):
    for s in selectors:
        e = node.select_one(s)
        if e: return e
    return None


def extract_tiles(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    tiles = []
    for sel in TILE_SELECTORS:
        found = soup.select(sel)
        if found:
            tiles = found
            break
    rows = []
    for t in tiles:
        title_el = select_first(t, TITLE_SELECTORS)
        title = title_el.get_text(strip=True) if title_el else ""
        url_el = t.select_one("a[href]")
        url = urljoin(base_url, url_el["href"]) if url_el and url_el.get("href") else ""
        price_el = select_first(t, PRICE_SELECTORS)
        price = parse_price(price_el.get_text() if price_el else "")
        avail_el = select_first(t, AVAIL_SELECTORS)
        avail_text = (avail_el.get_text(strip=True).lower() if avail_el else "") or ""
        available = None
        if avail_text:
            if any(k in avail_text for k in ["en stock", "disponible", "in stock"]):
                available = True
            elif any(k in avail_text for k in ["rupture", "indisponible", "out of stock", "épuisé", "epuise"]):
                available = False
        pid = t.get("data-id-product") or t.get("data-product-id") or ""
        if title and url:
            rows.append({"title": title, "url": url, "price_min": price, "available": available,
                         "product_pid": pid})
    next_url = None
    next_link = soup.select_one('link[rel="next"]') or soup.select_one('a[rel="next"]') or soup.select_one('.pagination a.next')
    if next_link and next_link.get("href"):
        next_url = urljoin(base_url, next_link["href"])
    return rows, next_url


def is_booster_or_display(title, url=""):
    """Check title + URL slug — many PS themes truncate titles server-side."""
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


def search_shop(shop, game_label, query):
    """Try search endpoints in order. Returns the first that returns >0 tiles."""
    rows_acc = []
    for path_tmpl in SEARCH_PATHS:
        url = f"https://{shop}{path_tmpl.format(q=quote_plus(query))}"
        r = get(url)
        if not r: continue
        rows, next_url = extract_tiles(r.text, url)
        if not rows: continue
        rows_acc.extend(rows)
        # Follow up to 4 next pages
        for _ in range(4):
            if not next_url: break
            r2 = get(next_url)
            if not r2: break
            more, next_url = extract_tiles(r2.text, next_url)
            if not more: break
            rows_acc.extend(more)
            time.sleep(0.3)
        break  # first endpoint that worked
    # tag and filter
    out = []
    seen = set()
    for r in rows_acc:
        key = (r["product_pid"] or "", r["title"])
        if key in seen: continue
        seen.add(key)
        if not is_booster_or_display(r["title"], r.get("url", "")): continue
        # OPTCG is FR-only: drop non-French editions (e.g. "VO" = version
        # originale = English, "japonais", "(JP)").
        if cleanup.is_foreign(r["title"], r.get("url", "")): continue
        r["game"] = game_label
        r["shop"] = shop
        out.append(r)
    return out


def fetch_category(shop, url, game_label, scope):
    """Fetch a direct category URL and paginate. scope: 'dedicated' or 'generic'."""
    rows_acc = []
    r = get(url)
    if not r: return []
    rows, next_url = extract_tiles(r.text, url)
    rows_acc.extend(rows)
    for _ in range(6):
        if not next_url: break
        r2 = get(next_url)
        if not r2: break
        more, next_url = extract_tiles(r2.text, next_url)
        if not more: break
        rows_acc.extend(more); time.sleep(0.3)
    out, seen = [], set()
    for row in rows_acc:
        key = (row["product_pid"] or "", row["title"])
        if key in seen: continue
        seen.add(key)
        if not is_booster_or_display(row["title"], row.get("url", "")): continue
        if cleanup.is_foreign(row["title"], row.get("url", "")): continue
        if scope == "generic":
            # Generic category mixes TCGs — require explicit signal
            t = row["title"].lower()
            optcg_sig = ("one piece" in t or "onepiece" in t
                         or re.search(r"\bop[-\s]?\d{1,2}\b", t)
                         or re.search(r"\b(prb|eb)[-\s]?\d{1,2}\b", t))
            naruto_sig = "naruto" in t
            if game_label == "optcg" and not optcg_sig: continue
            if game_label == "naruto_mythos" and not naruto_sig: continue
        # scope == "dedicated": keep all booster/display in this category
        row["game"] = game_label
        row["shop"] = shop
        out.append(row)
    return out


def discover_shop(shop):
    rows = []
    merged = all_direct_urls(DIRECT_URLS)
    if shop in merged:
        for game_label, url, scope in merged[shop]:
            rows.extend(fetch_category(shop, url, game_label, scope))
        # Also try Naruto via search even if OPTCG was direct
        rows.extend(search_shop(shop, "naruto_mythos", "naruto mythos"))
    else:
        for game_label, q in QUERIES:
            rows.extend(search_shop(shop, game_label, q))
    return rows


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(discover_shop, s): s for s in PRESTASHOP_SHOPS}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                r = fut.result()
                print(f"  {shop:<32} {len(r)} products")
                all_rows.extend(r)
            except Exception as e:
                print(f"  {shop:<32} ERROR: {type(e).__name__}: {e}")
    df = pd.DataFrame(all_rows)
    if df.empty:
        print("\nNo products found.")
        return
    df["price_max"] = df["price_min"]
    df["set"] = ""
    df = df[["game", "shop", "title", "set", "price_min", "price_max",
             "available", "product_pid", "url"]]
    df["_n"] = df["title"].str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    df = df.sort_values(["game", "_n", "shop"]).drop(columns=["_n"])
    out = DATA_DIR / "discovered_prestashop.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"\nTotal rows: {len(df)}")
    print(f"Unique shops: {df['shop'].nunique()}")
    print(f"With stock signal: {df['available'].notna().sum()} ({df['available'].notna().sum()*100//len(df)}%)")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
