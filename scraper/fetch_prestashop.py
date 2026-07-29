"""PrestaShop per-product fetcher.

PS has no public JSON API on most installs, so we hit each product detail page
and parse the schema.org markup (which every PS theme exposes consistently):
  <meta itemprop="price" content="159.90">
  <link itemprop="availability" href="https://schema.org/InStock">
"""
import datetime as dt
import re
import time
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db import connect, game_filter_sql
from .config import USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}


def _pid_in_url(pid, url) -> bool:
    """True if the PrestaShop product id still appears in `url`'s path.

    PS product URLs are `/<id>-slug.html` (the id may carry a date prefix, e.g.
    `/36485--03-04-2026-...`). When a product is delisted, PS 301/302-redirects to
    the parent *category* (e.g. `/180-one-piece`), dropping the product id. We use
    this to tell a delisted product apart from a legitimate canonical redirect
    (which keeps the same id)."""
    if not pid:
        return True  # can't tell — assume the page is still the product
    from urllib.parse import urlparse
    for seg in urlparse(url).path.strip("/").split("/"):
        if seg == str(pid) or seg.startswith(f"{pid}-"):
            return True
    return False


def parse_price(soup, fallback_text=""):
    """Parse price from PrestaShop product detail page."""
    # 1) Schema.org meta tag (most reliable)
    m = soup.select_one('meta[itemprop="price"]')
    if m and m.get("content"):
        try: return float(m["content"])
        except Exception: pass
    # 2) Span/div with itemprop="price"
    m = soup.select_one('[itemprop="price"]')
    if m:
        v = m.get("content") or m.get_text(strip=True)
        v = re.sub(r"[^\d.,]", "", v).replace(",", ".")
        try: return float(v)
        except Exception: pass
    # 3) .current-price / .product-price visible value
    for sel in [".current-price .price", ".product-price", ".price"]:
        e = soup.select_one(sel)
        if e:
            txt = e.get_text()
            mm = re.search(r"(\d{1,4}(?:[ .]\d{3})*[,.]\d{2})", txt)
            if mm:
                raw = mm.group(1)
                try: return float(raw.replace(" ", "").replace(".", "").replace(",", ".") if "," in raw else raw.replace(" ", ""))
                except Exception: pass
    return None


def parse_availability(soup):
    """Parse availability. Returns 1 (in stock), 0 (out), or None.
    Priority: add-to-cart button > text on page > schema.org meta.
    Schema.org markup on some PS themes (ludifolie, ikaipaka) lies, so it's last."""
    # 1) Add-to-cart button state — most reliable when it exists
    btn = soup.select_one('button[data-button-action="add-to-cart"], '
                          'button.add-to-cart, button#add-to-cart, '
                          'button[name="add-to-cart"]')
    btn_disabled = False
    if btn:
        btn_disabled = btn.has_attr("disabled") or "disabled" in (btn.get("class") or [])
        if btn_disabled:
            return 0  # button explicitly disabled => out of stock

    # 2) Text-based detection — OUT keywords FIRST (avoid "disponible" matching "indisponible")
    OUT_KW = ["rupture", "indisponible", "épuisé", "epuise", "out of stock",
              "pas assez de produits", "temporairement", "sold out", "non disponible"]
    IN_KW  = ["en stock", "in stock", "disponible", "available"]
    for sel in ["#product-availability", ".product-availability", ".availability"]:
        e = soup.select_one(sel)
        if e:
            t = e.get_text(strip=True).lower()
            if not t: continue
            if any(k in t for k in OUT_KW): return 0
            if any(k in t for k in IN_KW): return 1

    # 3) Schema.org as last resort (unreliable on some shops)
    link = soup.select_one('link[itemprop="availability"]')
    if link and link.get("href"):
        h = link["href"].lower()
        if "outofstock" in h or "soldout" in h: return 0
        if "preorder" in h or "backorder" in h: return 1
        if "instock" in h: return 1

    # 4) Enabled add-to-cart button is a weak positive
    if btn and not btn_disabled:
        return 1
    return None


def parse_stock_count(soup):
    """Extract 'X products/articles in stock' count from common PS availability text."""
    for sel in ["#product-availability", ".product-availability", ".availability",
                ".product-quantities"]:
        e = soup.select_one(sel)
        if not e: continue
        t = e.get_text(" ", strip=True).lower()
        # "Il ne reste que 3 produits en stock" / "3 articles en stock" / "3 disponibles"
        for pat in [r"(\d+)\s+(?:produit|article)s?\s+en\s+stock",
                    r"(?:reste que|reste|que)\s+(\d+)\s+(?:produit|article)",
                    r"(\d+)\s+disponible",
                    r"(\d+)\s+in\s+stock"]:
            m = re.search(pat, t)
            if m:
                try: return int(m.group(1))
                except Exception: pass
    return None


def fetch_one(product):
    pid = product["id"]
    try:
        r = requests.get(product["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return pid, None, None, 0, None
        # Delisted product: PS redirected us to the parent category (the product
        # id vanished from the URL). Scraping that listing page would harvest a
        # random product's price + "in stock". Treat as out-of-stock, no price.
        if r.history and not _pid_in_url(product.get("platform_pid"), r.url):
            return pid, None, 0, 1, None
        soup = BeautifulSoup(r.text, "html.parser")
        price = parse_price(soup)
        avail = parse_availability(soup)
        stock = parse_stock_count(soup) if avail == 1 else None
        return pid, price, avail, 1, stock
    except Exception:
        return pid, None, None, 0, None


def fetch_prestashop_all(games=None):
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop, platform_pid FROM products WHERE platform = 'prestashop'" + gsql,
            gparams).fetchall()]
    by_shop = defaultdict(list)
    for p in products: by_shop[p["shop"]].append(p)

    results = []
    def worker(shop_products):
        out = []
        for p in shop_products:
            out.append(fetch_one(p))
            time.sleep(PER_DOMAIN_DELAY)
        return out

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(worker, ps): shop for shop, ps in by_shop.items()}
        for fut in as_completed(futs):
            shop = futs[fut]
            try:
                rs = fut.result()
                results.extend(rs)
                ok = sum(1 for r in rs if r[1] is not None)
                avail_known = sum(1 for r in rs if r[2] is not None)
                print(f"  {shop:<32} price={ok}/{len(rs)}  stock_known={avail_known}/{len(rs)}")
            except Exception as e:
                print(f"  {shop:<32} ERROR: {e}")
    return results


def write_snapshots(rows):
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.executemany("""
            INSERT INTO snapshots (product_id, observed_at, price_eur, available, raw_variant_count, stock_remaining)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(pid, now, price, avail, vc, stock) for pid, price, avail, vc, stock in rows])
        conn.commit()


from .timing import timed_main


@timed_main
def main():
    print("=== PrestaShop snapshot run ===")
    rows = fetch_prestashop_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    unk = sum(1 for r in rows if r[2] is None)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}  unknown: {unk}")


if __name__ == "__main__":
    main()
