"""WooCommerce per-product fetcher.

Use the WC Store API single-product endpoint:
  /wp-json/wc/store/products/<id>
Returns clean JSON with prices.price (cents) and is_in_stock (bool).

Fallback to HTML detail page parsing if the Store API is unavailable.
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
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
}


def _price_from_minor(v):
    if v is None: return None
    try:
        s = str(v).replace(",", ".")
        n = float(s)
        if "." not in s and n > 99: return n / 100
        return n
    except Exception:
        return None


def fetch_via_api(shop, pid):
    url = f"https://{shop}/wp-json/wc/store/products/{pid}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200: return None
        data = r.json()
        prices = data.get("prices", {}) or {}
        price = _price_from_minor(prices.get("price"))
        in_stock = data.get("is_in_stock")
        available = None if in_stock is None else (1 if in_stock else 0)
        stock = data.get("low_stock_remaining")
        return price, available, stock if isinstance(stock, int) else None
    except Exception:
        return None


def fetch_via_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200: return None, None, None
        soup = BeautifulSoup(r.text, "html.parser")
        price = None
        for sel in ['meta[itemprop="price"]', 'p.price ins .amount', 'p.price .amount',
                    '.price ins .amount', '.price .amount', '.summary .price']:
            e = soup.select_one(sel)
            if e:
                v = e.get("content") or e.get_text()
                m = re.search(r"(\d{1,4}(?:[ .]\d{3})*[,.]\d{2})", v)
                if m:
                    raw = m.group(1)
                    try:
                        price = float(raw.replace(" ", "").replace(".", "").replace(",", ".") if "," in raw else raw.replace(" ", ""))
                        break
                    except Exception: pass
        available = None
        link = soup.select_one('link[itemprop="availability"]')
        if link and link.get("href"):
            h = link["href"].lower()
            if "instock" in h: available = 1
            elif "outofstock" in h or "soldout" in h: available = 0
        if available is None:
            if soup.select_one(".out-of-stock, .outofstock"): available = 0
            elif soup.select_one(".in-stock, .stock.in-stock"): available = 1
            elif soup.select_one("form.cart button.single_add_to_cart_button"): available = 1
        # Stock count: ".stock.in-stock" often says "3 en stock" / "3 in stock"
        stock = None
        e = soup.select_one(".stock.in-stock, p.stock, .stock")
        if e:
            m = re.search(r"(\d+)\s+(?:en\s+stock|in\s+stock|disponibles?|available)", e.get_text(strip=True).lower())
            if m:
                try: stock = int(m.group(1))
                except Exception: pass
        return price, available, stock
    except Exception:
        return None, None, None


def fetch_one(product):
    pid = product["id"]
    api = fetch_via_api(product["shop"], product["platform_pid"])
    if api is not None:
        return pid, api[0], api[1], 1, api[2]
    price, avail, stock = fetch_via_html(product["url"])
    return pid, price, avail, 1, stock


def fetch_woocommerce_all(games=None):
    gsql, gparams = game_filter_sql(games)
    with connect() as conn:
        products = [dict(p) for p in conn.execute(
            "SELECT id, url, shop, platform_pid FROM products WHERE platform = 'woocommerce'" + gsql,
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
                print(f"  {shop:<28} price={ok}/{len(rs)}  stock_known={avail_known}/{len(rs)}")
            except Exception as e:
                print(f"  {shop:<28} ERROR: {e}")
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
    print("=== WooCommerce snapshot run ===")
    rows = fetch_woocommerce_all()
    write_snapshots(rows)
    ok = sum(1 for r in rows if r[1] is not None)
    avail = sum(1 for r in rows if r[2] == 1)
    out = sum(1 for r in rows if r[2] == 0)
    unk = sum(1 for r in rows if r[2] is None)
    print(f"\nFetched: {len(rows)}  price ok: {ok}  in stock: {avail}  out: {out}  unknown: {unk}")


if __name__ == "__main__":
    main()
