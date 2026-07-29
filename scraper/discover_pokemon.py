"""Big first-pass Pokemon discovery across all tracked shops.

Reuses the existing per-platform access helpers (Shopify collections.json,
WooCommerce Store API, PrestaShop search) but with Pokemon collection/search
terms, and captures broadly: title + description + tags + collection + price +
availability. NO sealed/kind filtering here — that happens in
`categorize_pokemon.py`. Output: data/discovered_pokemon_raw.xlsx.

Run:  python -m scraper.discover_pokemon
"""
import re
import html as _html
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from urllib.parse import urlparse

from .config import DATA_DIR
from .games import pokemon
# Reuse platform access helpers from the OPTCG discoverers.
from .discover_shopify import _get as sf_get, fetch_collection_products, SHOPIFY_SHOPS
from .discover_woocommerce import get as woo_get, parse_price_cents, WOOCOMMERCE_SHOPS
from .discover_prestashop import get as ps_get, extract_tiles, PRESTASHOP_SHOPS
# Small platforms.
from .discover_wix import (get_instance as wix_instance, _post_gql as wix_gql,
                           CAT_LIST_Q, fetch_category_products as wix_products,
                           ALL_PRODUCTS_CID, WIX_SHOPS)
from .discover_powerboutique import (get as pb_get, fetch_category as pb_fetch_category,
                                     POWERBOUTIQUE_SHOPS)
from .discover_nextjs import (_get as nx_get, playin_product_jsonld, playin_parse_offer,
                              PLAYIN_SITEMAP_INDEX, NEXTJS_SHOPS)
from .discover_emonsite import (get as em_get, product_jsonld as em_jsonld,
                                parse_offer as em_offer, EMONSITE_SHOPS)
from .discover_fantasysphere import (get as fs_get, fetch_category as fs_fetch_category,
                                     CATEGORIES as FS_CATEGORIES, FANTASYSPHERE_SHOPS)

POKEMON_QUERIES = ["pokemon", "pokémon", "coffret pokemon", "display pokemon"]


def _text(s: str, limit: int = 600) -> str:
    """Strip HTML tags/entities from a description, collapse whitespace, truncate."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()[:limit]


def _is_pokemon_collection(handle: str, title: str) -> bool:
    text = f"{title} {handle}".lower()
    if "one piece" in text or "naruto" in text:
        return False
    return any(k in text for k in pokemon.COLLECTION_KEYWORDS)


# --------------------------------------------------------------------------- #
# Shopify
# --------------------------------------------------------------------------- #
def discover_shopify_shop(shop):
    r = sf_get(f"https://{shop}/collections.json?limit=250")
    if not r:
        return []
    try:
        cols = r.json().get("collections", [])
    except Exception:
        return []
    handles = [(c["handle"], c.get("title", "")) for c in cols
               if _is_pokemon_collection(c["handle"], c.get("title", ""))]
    rows, seen = [], set()
    for handle, ctitle in handles:
        for p in fetch_collection_products(shop, handle):
            pid = p.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            variants = p.get("variants", []) or []
            prices = [float(v["price"]) for v in variants if v.get("price")]
            rows.append({
                "platform": "shopify", "shop": shop,
                "platform_pid": pid,
                "title": p.get("title", "") or "",
                "description": _text(p.get("body_html", "")),
                "tags": ", ".join(p.get("tags", []) or []) if isinstance(p.get("tags"), list) else (p.get("tags") or ""),
                "product_type": p.get("product_type", "") or "",
                "vendor": p.get("vendor", "") or "",
                "collection": f"{ctitle}|{handle}",
                "price_min": min(prices) if prices else None,
                "available": 1 if any(v.get("available") for v in variants) else 0,
                "variants_count": len(variants),
                "url": f"https://{shop}/products/{p.get('handle','')}",
            })
    return rows


# --------------------------------------------------------------------------- #
# WooCommerce (Store API carries description + categories)
# --------------------------------------------------------------------------- #
def discover_woo_shop(shop):
    rows, seen = [], set()
    for q in POKEMON_QUERIES[:2]:
        for page in range(1, 6):
            url = (f"https://{shop}/wp-json/wc/store/products"
                   f"?search={q}&per_page=100&page={page}")
            r = woo_get(url, accept_json=True)
            if not r:
                break
            try:
                items = r.json()
            except Exception:
                break
            if not isinstance(items, list) or not items:
                break
            for p in items:
                pid = p.get("id")
                if pid in seen:
                    continue
                seen.add(pid)
                cats = ", ".join(c.get("name", "") for c in (p.get("categories") or []))
                desc = _text((p.get("short_description") or "") + " " + (p.get("description") or ""))
                rows.append({
                    "platform": "woocommerce", "shop": shop,
                    "platform_pid": pid,
                    "title": p.get("name", "") or "",
                    "description": desc,
                    "tags": "", "product_type": cats, "vendor": "",
                    "collection": cats,
                    "price_min": parse_price_cents((p.get("prices") or {}).get("price")),
                    "available": 1 if p.get("is_in_stock") else 0,
                    "variants_count": None,
                    "url": p.get("permalink", "") or "",
                })
            if len(items) < 100:
                break
            time.sleep(0.2)
    return rows


# --------------------------------------------------------------------------- #
# PrestaShop (search; title + price only, no description)
# --------------------------------------------------------------------------- #
_PS_SEARCH = [
    "/recherche?controller=search&s={q}",
    "/module/ambjolisearch/jolisearch?s={q}",
    "/module/iqitsearch/searchiqit?s={q}",
]


def discover_ps_shop(shop):
    from urllib.parse import quote_plus
    rows, seen = [], set()
    for path in _PS_SEARCH:
        url = f"https://{shop}{path.format(q=quote_plus('pokemon'))}"
        r = ps_get(url)
        if not r:
            continue
        tiles, next_url = extract_tiles(r.text, url)
        if not tiles:
            continue
        for _ in range(4):
            if not next_url:
                break
            r2 = ps_get(next_url)
            if not r2:
                break
            more, next_url = extract_tiles(r2.text, next_url)
            if not more:
                break
            tiles.extend(more)
            time.sleep(0.3)
        for t in tiles:
            key = (t.get("product_pid") or "", t["title"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "platform": "prestashop", "shop": shop,
                "platform_pid": t.get("product_pid") or "",
                "title": t["title"], "description": "", "tags": "",
                "product_type": "", "vendor": "", "collection": "",
                "price_min": t.get("price_min"),
                "available": (1 if t["available"] else 0) if t.get("available") is not None else None,
                "variants_count": None,
                "url": t.get("url", ""),
            })
        break  # first working endpoint
    return rows


# --------------------------------------------------------------------------- #
# Small platforms (~8 shops): Wix, Powerboutique, Next.js(PlayIn), e-monsite, FantasySphere
# --------------------------------------------------------------------------- #
def _mk(platform, shop, pid, title, url, price=None, available=None,
        description="", collection=""):
    return {"platform": platform, "shop": shop, "platform_pid": str(pid or ""),
            "title": title or "", "description": description, "tags": "",
            "product_type": "", "vendor": "", "collection": collection,
            "price_min": price,
            "available": None if available is None else int(available),
            "variants_count": None, "url": url or ""}


def _find_pokemon_category_urls(shop, get_fn, max_urls=5):
    """Scan a shop homepage for menu links pointing at a Pokemon category."""
    r = get_fn(f"https://{shop}/")
    if not r:
        return []
    urls = []
    seen = set()
    for a in BeautifulSoup(r.text, "html.parser").select("a[href]"):
        href = a.get("href", "") or ""
        blob = f"{href} {a.get_text(' ', strip=True)}".lower()
        if "pokemon" not in blob and "pokémon" not in blob:
            continue
        if "one piece" in blob or "naruto" in blob:
            continue
        full = href if href.startswith("http") else f"https://{shop}/{href.lstrip('/')}"
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls[:max_urls]


def discover_wix_shop(shop):
    try:
        instance = wix_instance(shop)
        if not instance:
            return []
        data = wix_gql(shop, instance, CAT_LIST_Q)
        cids, fallback = [], False
        if data:
            cats = (((data.get("catalog") or {}).get("categories") or {}).get("list")) or []
            for c in cats:
                n = (c.get("name") or "").lower()
                if "one piece" in n or "naruto" in n:
                    continue
                if any(k in n for k in pokemon.COLLECTION_KEYWORDS):
                    cids.append(c["id"])
        if not cids:
            cids, fallback = [ALL_PRODUCTS_CID], True
        rows, seen = [], set()
        for cid in cids:
            for p in wix_products(shop, instance, cid):
                pid = p.get("id")
                title = p.get("name", "") or ""
                if not pid or pid in seen:
                    continue
                if fallback and "pokemon" not in title.lower() and "pokémon" not in title.lower():
                    continue
                seen.add(pid)
                up = p.get("urlPart", "") or ""
                rows.append(_mk("wix", shop, pid, title,
                                f"https://{shop}/product-page/{up}" if up else f"https://{shop}",
                                price=p.get("price"),
                                available=1 if p.get("isInStock") else 0))
        return rows
    except Exception:
        return []


def discover_pb_shop(shop):
    try:
        rows, seen = [], set()
        for url in _find_pokemon_category_urls(shop, pb_get):
            for pid, purl, title, price, avail in pb_fetch_category(shop, url):
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                rows.append(_mk("powerboutique", shop, pid, title, purl, price, avail))
        return rows
    except Exception:
        return []


_PLAYIN_KEEP = ("booster", "display", "coffret", "etb", "tin", "bundle", "blister", "boite")


def discover_nextjs_shop(shop):
    # Parkage needs an internal product_type_id we can't derive — skip for now.
    if "play-in" not in shop:
        return []
    try:
        r = nx_get(PLAYIN_SITEMAP_INDEX)
        if not r:
            return []
        sitemaps = [u for u in re.findall(r"https://[^<]+\.xml", r.text)
                    if "/produits/sitemap/" in u]
        urls = set()
        for sm in sitemaps:
            rs = nx_get(sm)
            if not rs:
                continue
            for loc in re.findall(r"https://www\.play-in\.com/fr/produit/\d+/[a-z0-9-]+", rs.text):
                slug = loc.rsplit("/", 1)[-1]
                if "pokemon" in slug and any(k in slug for k in _PLAYIN_KEEP):
                    urls.add(loc)

        def one(u):
            rr = nx_get(u)
            if not rr:
                return None
            d = playin_product_jsonld(rr.text)
            if not d:
                return None
            price, avail = playin_parse_offer(d)
            m = re.search(r"/produit/(\d+)/", u)
            return _mk("nextjs", shop, m.group(1) if m else u, d.get("name", "") or "", u,
                       price, avail, description=_text(d.get("description", "")))

        out = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            for row in ex.map(one, sorted(urls)):
                if row:
                    out.append(row)
        return out
    except Exception:
        return []


def discover_emonsite_shop(shop):
    try:
        r = em_get(f"https://{shop}/sitemap.xml")
        if not r:
            return []
        urls = {loc for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
                if loc.lower().endswith(".html") and "pokemon" in loc.lower()}

        def one(u):
            rr = em_get(u)
            if not rr:
                return None
            d = em_jsonld(rr.text)
            if not d:
                return None
            price, avail = em_offer(d)
            return _mk("emonsite", shop, urlparse(u).path, d.get("name", "") or "", u,
                       price, avail, description=_text(d.get("description", "")))

        out = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            for row in ex.map(one, sorted(urls)):
                if row:
                    out.append(row)
        return out
    except Exception:
        return []


def discover_fs_shop(shop):
    try:
        # Pokemon category links from the menu, plus a guess from the OPTCG URL.
        urls = _find_pokemon_category_urls(shop, fs_get)
        for _g, optcg_url in FS_CATEGORIES.get(shop, []):
            guess = re.sub(r"one-piece[a-z-]*", "pokemon", optcg_url)
            if guess != optcg_url:
                urls.append(guess)
        rows, seen = [], set()
        for url in dict.fromkeys(urls):
            for pid, purl, title, price, avail in fs_fetch_category(url):
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                full = purl if purl.startswith("http") else f"https://{shop}{purl}"
                rows.append(_mk("fantasysphere", shop, pid, title, full, price, avail))
        return rows
    except Exception:
        return []


PLATFORMS = [
    ("shopify",       SHOPIFY_SHOPS,       discover_shopify_shop),
    ("woocommerce",   WOOCOMMERCE_SHOPS,   discover_woo_shop),
    ("prestashop",    PRESTASHOP_SHOPS,    discover_ps_shop),
    ("wix",           WIX_SHOPS,           discover_wix_shop),
    ("powerboutique", POWERBOUTIQUE_SHOPS, discover_pb_shop),
    ("nextjs",        NEXTJS_SHOPS,        discover_nextjs_shop),
    ("emonsite",      EMONSITE_SHOPS,      discover_emonsite_shop),
    ("fantasysphere", FANTASYSPHERE_SHOPS, discover_fs_shop),
]


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for label, shops, fn in PLATFORMS:
        print(f"\n=== {label} ({len(shops)} shops) ===")
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(fn, s): s for s in shops}
            for fut in as_completed(futs):
                shop = futs[fut]
                try:
                    r = fut.result()
                    if r:
                        print(f"  {shop:<32} {len(r)} products")
                    all_rows.extend(r)
                except Exception as e:
                    print(f"  {shop:<32} ERROR: {type(e).__name__}: {e}")

    df = pd.DataFrame(all_rows)
    out = DATA_DIR / "discovered_pokemon_raw.xlsx"
    if df.empty:
        print("\nNo products found.")
        return
    df = df.sort_values(["platform", "shop", "title"])
    df.to_excel(out, index=False)
    print(f"\n=== RAW SUMMARY ===")
    print(df.groupby("platform").size().to_string())
    print(f"Total raw rows: {len(df)}  |  shops with hits: {df['shop'].nunique()}")
    print(f"Written to: {out}")


if __name__ == "__main__":
    main()
