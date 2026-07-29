"""Discover all OPTCG and Naruto Mythos booster/display products across Shopify shops.

Output: data/discovered.xlsx — user reviews and prunes to a curated list.

Approach (deliberately broad — user will hand-curate):
1. For each shop, hit /collections.json to find OPTCG + Naruto collections.
2. Pull all products from those collections (paginated).
3. Filter to booster/display only (no singles, decks, accessories).
4. Write one row per (shop, product). Sort by canonical title so duplicates cluster.
"""
import re
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR

_BUILTIN_SHOPIFY = [
    "baroncollections.fr", "bgeek.be", "carteonepiece.fr", "dojodragons.fr",
    "www.dracaugames.com", "hikarudistribution.com", "hitndrop.com", "hobbyhouse.fr",
    "huntersquest.fr", "kyumastore.fr", "labellecarte.fr", "lacarterare.com",
    "lebordelmagique.com", "lorenzone.fr", "www.ludijeux.fr", "ludisphere.fr",
    "masterset.store", "miyatakardmarket.re", "oranatcg.com", "outpostbrussels.be",
    "www.poke-geek.fr", "www.relictcg.com", "rivolitcg.fr", "strikegames.shop",
    "susume.be", "www.vegastore.fr", "zadoys.fr", "tradingcardsxxx.fr",
]
from .shop_registry import all_shops
SHOPIFY_SHOPS = all_shops("shopify", _BUILTIN_SHOPIFY)

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}

# Collection-handle / title keywords (broad — we just want to find the right collections)
COLLECTION_KEYWORDS = [
    "one-piece", "one piece", "onepiece", "optcg", "op-tcg",
    "naruto", "mythos",
]

# Title-level positive markers (after we have the candidate products)
KEEP_KEYWORDS = [
    "display", "booster", "boîte", "boite", "box of", "sealed", "scellé", "scelle",
    "sleeved", "boosterbox", "booster box", "carton", "case",
]
# Drop these even if a positive keyword matches
DROP_KEYWORDS = [
    "single", "carte à l'unité", "deck ", "starter", "structure",
    "playmat", "tapis", "protège", "protege-carte", "toploader",
    "classeur", "sleeve (", "sleeves ", "deckbox", "deck-box", "deck box",
    "accessoire", "pochette", "dice ", "dé ", "set d'accessoires",
    # ED.2 / 2nd edition reprints (mostly Naruto Konoha Shidō ED.2)
    "édition 2", "edition 2", "2ème édition", "2eme édition",
    "2eme edition", "2nd edition", "ed.2", "ed. 2",
]


def _get(url, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(2 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(1)
    return None


def find_collections(shop):
    """Return list of (handle, title) for collections related to OPTCG or Naruto."""
    r = _get(f"https://{shop}/collections.json?limit=250")
    if not r:
        return []
    try:
        cols = r.json().get("collections", [])
    except Exception:
        return []
    out = []
    for c in cols:
        text = f"{c.get('title','')} {c.get('handle','')}".lower()
        if any(k in text for k in COLLECTION_KEYWORDS):
            out.append((c["handle"], c.get("title", "")))
    return out


def classify_game(title, tags, vendor, collection_handle):
    """Return 'optcg' or 'naruto_mythos' (or None to drop)."""
    blob = " ".join([title, " ".join(tags or []) if isinstance(tags, list) else (tags or ""),
                     vendor or "", collection_handle or ""]).lower()
    if "one piece" in blob or "onepiece" in blob or "optcg" in blob or re.search(r"\bop-\d{1,2}\b", blob):
        return "optcg"
    if "naruto mythos" in blob or "naruto-mythos" in blob or "nrt-" in blob:
        return "naruto_mythos"
    if "naruto" in blob and any(k in blob for k in ["display", "booster", "boîte de booster", "boite de booster"]):
        return "naruto_mythos"
    return None


def is_booster_or_display(title, product_type):
    blob = f"{title} {product_type or ''}".lower()
    has_positive = any(k in blob for k in KEEP_KEYWORDS)
    if not has_positive:
        return False
    if any(k in blob for k in DROP_KEYWORDS):
        return False
    return True


def fetch_collection_products(shop, handle):
    """Paginate through a collection's products.json."""
    products = []
    for page in range(1, 11):  # safety cap: 10 pages * 250 = 2500
        r = _get(f"https://{shop}/collections/{handle}/products.json?limit=250&page={page}")
        if not r:
            break
        try:
            items = r.json().get("products", [])
        except Exception:
            break
        if not items:
            break
        products.extend(items)
        if len(items) < 250:
            break
        time.sleep(0.3)  # polite pause
    return products


def discover_shop(shop):
    """Return list of dicts (one per matching product) for a shop."""
    cols = find_collections(shop)
    rows = []
    seen_pids = set()
    for handle, ctitle in cols:
        products = fetch_collection_products(shop, handle)
        for p in products:
            pid = p["id"]
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            title = p.get("title", "")
            ptype = p.get("product_type", "") or ""
            tags = p.get("tags", []) or []
            vendor = p.get("vendor", "") or ""
            game = classify_game(title, tags, vendor, handle)
            if not game:
                continue
            if not is_booster_or_display(title, ptype):
                continue
            variants = p.get("variants", [])
            prices = [float(v["price"]) for v in variants if v.get("price")]
            avail = any(v.get("available") for v in variants)
            rows.append({
                "game": game,
                "shop": shop,
                "title": title,
                "product_type": ptype,
                "vendor": vendor,
                "tags": ", ".join(tags[:5]),
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "available": avail,
                "variants_count": len(variants),
                "shopify_pid": pid,
                "handle": p["handle"],
                "collection": handle,
                "url": f"https://{shop}/products/{p['handle']}",
            })
    return rows


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(discover_shop, s): s for s in SHOPIFY_SHOPS}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                rows = fut.result()
                print(f"  {shop:<35} {len(rows)} products")
                all_rows.extend(rows)
            except Exception as e:
                print(f"  {shop:<35} ERROR: {e}")

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("\nNo products found.")
        return
    # Sort so duplicates across shops cluster
    df["_normtitle"] = df["title"].str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    df = df.sort_values(["game", "_normtitle", "shop"]).drop(columns=["_normtitle"])
    out = DATA_DIR / "discovered_shopify.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"\nTotal rows: {len(df)}")
    print(f"Unique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
