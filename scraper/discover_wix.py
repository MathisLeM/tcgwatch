"""Discover OPTCG + Naruto Mythos booster/display products on Wix Stores shops.

Output: data/discovered_wix.xlsx (same columns as the WooCommerce file)

Wix Stores exposes a GraphQL storefront API. Flow per shop:
1. GET /_api/v1/access-tokens  ->  instance token for the Wix Stores app.
2. GraphQL: list categories, keep the One Piece / Naruto ones
   (fallback: the built-in "All Products" category + title-keyword classify).
3. GraphQL: paginate productsWithMetaData for each kept category.
4. Filter to booster/display only, save with the same columns as PS/Shopify/Woo.
"""
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from .shop_registry import all_shops

_BUILTIN_WIX = [
    "www.passiongeek.fr", "www.ledecale-jeux.com",
]
WIX_SHOPS = all_shops("wix", _BUILTIN_WIX)

# Wix Stores app id — same on every Wix site. Its access token authorises the
# storefront GraphQL endpoint.
STORES_APP_ID = "1380b703-ce81-ff05-f115-39571d94dfcd"
GQL_PATH = "/_api/wix-ecommerce-storefront-web/api"
TOKENS_PATH = "/_api/v1/access-tokens"
ALL_PRODUCTS_CID = "00000000-000000-000000-000000000001"

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}

# Category-name keywords -> which game the category belongs to.
OPTCG_CAT_KW = ["one piece", "onepiece", "optcg", "op-tcg", "op tcg"]
NARUTO_CAT_KW = ["naruto", "mythos"]

KEEP_KW = ["display", "booster", "boîte", "boite", "carton", "case", "scellé", "scelle", "sleeved"]
DROP_KW = ["single", "carte à l'unité", "deck ", "starter", "structure",
           "playmat", "tapis", "protège", "protege", "toploader", "classeur",
           "sleeve ", "sleeves ", "deckbox", "deck-box", "deck box",
           "accessoire", "pochette", "dice ", " dé ",
           # ED.2 / 2nd edition reprints (mostly Naruto Konoha Shidō ED.2)
           "édition 2", "edition 2", "2ème édition", "2eme édition",
           "2eme edition", "2nd edition", "ed.2", "ed. 2"]

CAT_LIST_Q = "query{catalog{categories{list{id name}}}}"
CAT_PRODUCTS_Q = (
    "query($cid:String!,$limit:Int!,$offset:Int!){catalog{category(categoryId:$cid)"
    "{productsWithMetaData(limit:$limit,offset:$offset){totalCount "
    "list{id name formattedPrice price isInStock urlPart}}}}}"
)


def _post_gql(shop, instance, query, variables=None, retries=2):
    """POST a GraphQL query to the Wix Stores storefront API. Returns the
    `data` dict or None."""
    url = f"https://{shop}{GQL_PATH}"
    headers = {**HEADERS, "Content-Type": "application/json", "Authorization": instance}
    body = {"query": query, "variables": variables or {}}
    for i in range(retries):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                if data.get("success") is False:
                    return None
                return data.get("data")
            if r.status_code == 429:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.8)
    return None


def get_instance(shop, retries=2):
    """Fetch a fresh Wix Stores instance token for `shop`, or None."""
    url = f"https://{shop}{TOKENS_PATH}"
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                app = (r.json().get("apps") or {}).get(STORES_APP_ID) or {}
                return app.get("instance")
            if r.status_code == 429:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.8)
    return None


def _game_for_category(name: str):
    """Return 'optcg' / 'naruto_mythos' / None for a category name."""
    n = (name or "").lower()
    if any(k in n for k in OPTCG_CAT_KW):
        return "optcg"
    if any(k in n for k in NARUTO_CAT_KW):
        return "naruto_mythos"
    return None


def _classify_title(title: str):
    """Fallback game classifier when scanning the All-Products category."""
    t = (title or "").lower()
    if "one piece" in t or "onepiece" in t or "optcg" in t:
        return "optcg"
    if "naruto" in t and ("mythos" in t or any(k in t for k in KEEP_KW)):
        return "naruto_mythos"
    return None


def is_booster_or_display(title: str) -> bool:
    t = (title or "").lower()
    if not any(k in t for k in KEEP_KW):
        return False
    if any(k in t for k in DROP_KW):
        return False
    return True


def find_categories(shop, instance):
    """Return list of (category_id, game) for OPTCG/Naruto categories.
    Empty list -> caller should fall back to the All-Products category."""
    data = _post_gql(shop, instance, CAT_LIST_Q)
    if not data:
        return []
    cats = (((data.get("catalog") or {}).get("categories") or {}).get("list")) or []
    out = []
    for c in cats:
        game = _game_for_category(c.get("name", ""))
        if game:
            out.append((c["id"], game))
    return out


def fetch_category_products(shop, instance, cid, limit=100, max_pages=20):
    """Paginate productsWithMetaData for one category. Returns list of product dicts."""
    products, offset = [], 0
    for _ in range(max_pages):
        data = _post_gql(shop, instance, CAT_PRODUCTS_Q,
                         {"cid": cid, "limit": limit, "offset": offset})
        if not data:
            break
        pm = (((data.get("catalog") or {}).get("category") or {})
              .get("productsWithMetaData") or {})
        items = pm.get("list") or []
        if not items:
            break
        products.extend(items)
        offset += len(items)
        if offset >= (pm.get("totalCount") or 0) or len(items) < limit:
            break
        time.sleep(0.3)
    return products


def discover_shop(shop):
    """Return a list of dicts (one per matching product) for a shop."""
    instance = get_instance(shop)
    if not instance:
        return []
    cats = find_categories(shop, instance)
    fallback = not cats
    if fallback:
        cats = [(ALL_PRODUCTS_CID, None)]  # game decided per-title below

    out_rows, seen = [], set()
    for cid, cat_game in cats:
        for p in fetch_category_products(shop, instance, cid):
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            title = p.get("name", "") or ""
            game = cat_game or _classify_title(title)
            if not game:
                continue
            if not is_booster_or_display(title):
                continue
            seen.add(pid)
            url_part = p.get("urlPart", "") or ""
            out_rows.append({
                "game": game,
                "shop": shop,
                "title": title,
                "price_min": p.get("price"),
                "available": p.get("isInStock"),
                "product_pid": pid,
                "url": f"https://{shop}/product-page/{url_part}" if url_part else f"https://{shop}",
                "source": "wix-allproducts" if fallback else "wix-category",
            })
    return out_rows


from .timing import timed_main


@timed_main
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(discover_shop, s): s for s in WIX_SHOPS}
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
    out = DATA_DIR / "discovered_wix.xlsx"
    df.to_excel(out, index=False)
    print(f"\n=== Summary ===")
    print(df.groupby("game").size().to_string())
    print(f"Total rows: {len(df)}")
    print(f"Unique shops: {df['shop'].nunique()}")
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
