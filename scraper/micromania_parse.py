"""Offline HTML parsing for Micromania (Salesforce Commerce Cloud / Demandware).

Kept free of Playwright / network so it can be unit-tested against the POC's
saved HTML fixtures. Two layers:

* listing tiles  -> `parse_listing_tiles(html, base_url)`  (category / search grid)
* product detail -> `parse_price(soup)`, `parse_availability(soup)`,
                    `parse_stock_count(soup)`  (mirrors fetch_prestashop's API)

Micromania renders each product tile as
    <div class="product-tile" itemscope itemtype=".../Product" data-pid="158435">
      <a class="product-name-link" href=".../p/...-158435.html"
         data-gtm='{"...":{"products":[{"id":"158435","name":"...","price":19.99,
                                        "EAN":"...","dispoweb":1, ...}]}}'>
      <span class="value" itemprop="price" content="19.99">
    </div>
The `data-gtm` JSON is the most stable signal (id / name / price / dispoweb),
with schema.org `itemprop` markup as a fallback. `dispoweb` is 1 (sellable
online) / 0 (not).  The platform_pid is the trailing number of the /p/ URL.
"""
from __future__ import annotations

import html as _html
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# Trailing numeric id in a Micromania PDP URL: /p/<slug>-158435.html -> 158435
_PID_RE = re.compile(r"-(\d+)\.html(?:[?#].*)?$")
_PRICE_RE = re.compile(r"(\d{1,4}(?:[  . ]\d{3})*[,.]\d{2})")


def pid_from_url(url: str | None) -> str | None:
    """Extract the platform product id (trailing number) from a PDP URL."""
    if not url:
        return None
    m = _PID_RE.search(url)
    return m.group(1) if m else None


def parse_price_text(text: str | None):
    """Parse a EUR price out of free text. Returns float or None."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(" ", "").replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Listing grid (category / search results)
# --------------------------------------------------------------------------- #
def _gtm_product(raw_gtm: str | None) -> dict | None:
    """Pull the first product dict out of a tile's data-gtm JSON blob."""
    if not raw_gtm:
        return None
    try:
        data = json.loads(_html.unescape(raw_gtm))
    except Exception:
        return None
    # Shape: {"ecommerce": {"click": {"products": [ {...} ]}}}  (or impressions)
    ecommerce = data.get("ecommerce") if isinstance(data, dict) else None
    if not isinstance(ecommerce, dict):
        return None
    for section in ("click", "impressions", "detail"):
        node = ecommerce.get(section)
        if isinstance(node, dict):
            products = node.get("products")
            if isinstance(products, list) and products:
                return products[0]
        elif isinstance(node, list) and node:  # impressions can be a bare list
            return node[0]
    return None


def parse_listing_tiles(html: str, base_url: str = "https://www.micromania.fr/") -> list[dict]:
    """Return one dict per product tile found in a category/search grid page.

    Each dict: platform_pid, title, url, price, available, ean. Defensive: a tile
    missing a field yields None for it rather than raising, and tiles without a
    usable id/url are skipped (logged by the caller via the skip count).
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    seen: set[str] = set()

    for tile in soup.select("div.product-tile[data-pid], div.product-tile"):
        try:
            row = _parse_one_tile(tile, base_url)
        except Exception:
            row = None
        if not row:
            continue
        if row["platform_pid"] in seen:
            continue
        seen.add(row["platform_pid"])
        out.append(row)
    return out


def _parse_one_tile(tile, base_url: str) -> dict | None:
    # Primary link carries the canonical PDP url + the data-gtm JSON.
    link = tile.select_one("a.product-name-link[href]") or tile.select_one("a.pdp-link[href]")
    href = link.get("href") if link else None
    url = urljoin(base_url, href) if href else None

    # Require a real PDP url ('/p/...-<id>.html'): merchandising / banner tiles
    # also carry data-pid (e.g. 'mb537') but no product page, so they're skipped.
    pid = pid_from_url(url)
    if not pid:
        return None

    gtm = _gtm_product(link.get("data-gtm") if link else None)
    if gtm is None:
        # try any element on the tile carrying data-gtm
        any_gtm = tile.find(attrs={"data-gtm": True})
        gtm = _gtm_product(any_gtm.get("data-gtm")) if any_gtm else None

    # Title: gtm name -> product-name div -> link title attribute.
    title = None
    if gtm and gtm.get("name"):
        title = str(gtm["name"]).strip()
    if not title:
        name_el = tile.select_one('.product-name[itemprop="name"], .product-name')
        if name_el:
            title = name_el.get_text(" ", strip=True)
    if not title and link and link.get("title"):
        # link title uses " | " separators; normalise to a plain title
        title = re.sub(r"\s*\|\s*", " ", link["title"]).strip()
    if not title:
        return None

    # Price: gtm price -> schema.org meta -> visible sales value.
    price = None
    if gtm and gtm.get("price") is not None:
        try:
            price = float(gtm["price"])
        except (TypeError, ValueError):
            price = None
    if price is None:
        meta = tile.select_one('[itemprop="price"]')
        if meta:
            price = parse_price_text(meta.get("content")) or parse_price_text(meta.get_text())
    if price is None:
        val = tile.select_one(".sales .value, .price .value, .sales")
        if val:
            price = parse_price_text(val.get("content")) or parse_price_text(val.get_text())

    # Availability: gtm dispoweb is authoritative on the grid (1 sellable / 0 not).
    available = None
    if gtm and "dispoweb" in gtm and gtm["dispoweb"] is not None:
        try:
            available = 1 if int(gtm["dispoweb"]) == 1 else 0
        except (TypeError, ValueError):
            available = None

    ean = str(gtm.get("EAN")) if gtm and gtm.get("EAN") else ""

    return {
        "platform_pid": pid,
        "title": title,
        "url": url,
        "price": price,
        "available": available,
        "ean": ean,
    }


# --------------------------------------------------------------------------- #
# Product detail page (PDP) — mirrors fetch_prestashop's parser contract
# --------------------------------------------------------------------------- #
def parse_price(soup: BeautifulSoup):
    """Parse the current price from a Micromania PDP. Returns float or None."""
    # 1) schema.org price meta (most stable; SFCC themes expose it on the PDP).
    for sel in ('meta[itemprop="price"]', 'span[itemprop="price"]',
                '[itemprop="price"]'):
        m = soup.select_one(sel)
        if m:
            v = m.get("content")
            if v:
                try:
                    return float(v)
                except ValueError:
                    pass
            p = parse_price_text(m.get_text())
            if p is not None:
                return p
    # 2) visible sales price block.
    for sel in (".prices .sales .value", ".product-price .sales", ".sales .value",
                ".product-price", ".price .sales"):
        e = soup.select_one(sel)
        if e:
            p = parse_price_text(e.get("content")) or parse_price_text(e.get_text())
            if p is not None:
                return p
    return None


def parse_availability(soup: BeautifulSoup):
    """Return 1 (in stock), 0 (out), or None. Priority mirrors fetch_prestashop:
    add-to-cart button state -> page text -> schema.org meta -> gtm fallback."""
    # 1) add-to-cart button: disabled => out of stock.
    btn = soup.select_one(
        'button.add-to-cart, button.add-to-cart-global, button[data-button-action="add-to-cart"], '
        'button[name="add-to-cart"], a.add-to-cart'
    )
    btn_disabled = False
    if btn:
        classes = btn.get("class") or []
        btn_disabled = btn.has_attr("disabled") or "disabled" in classes
        if btn_disabled:
            return 0

    # 2) availability text. OUT keywords first (so "indisponible" isn't read as
    # "disponible"). SFCC/Micromania uses these on the PDP and the cart block.
    OUT_KW = ["rupture", "indisponible", "épuisé", "epuise", "non disponible",
              "out of stock", "sold out", "victime de son succès",
              "produit en rupture", "bientôt disponible"]
    IN_KW = ["en stock", "disponible en ligne", "ajouter au panier",
             "in stock", "disponible", "available"]
    for sel in ['.availability', '.product-availability', '.availability-msg',
                '[itemprop="availability"]', '.add-to-cart-messages',
                '.stock-message', '.delivery']:
        e = soup.select_one(sel)
        if not e:
            continue
        t = e.get_text(" ", strip=True).lower()
        if not t:
            continue
        if any(k in t for k in OUT_KW):
            return 0
        if any(k in t for k in IN_KW):
            return 1

    # 3) schema.org availability link/meta.
    link = soup.select_one('link[itemprop="availability"], meta[itemprop="availability"]')
    if link:
        h = (link.get("href") or link.get("content") or "").lower()
        if "outofstock" in h or "soldout" in h:
            return 0
        if "preorder" in h or "backorder" in h or "instock" in h:
            return 1

    # 4) data-gtm dispoweb on the PDP, if present.
    g = soup.find(attrs={"data-gtm": True})
    if g:
        prod = _gtm_product(g.get("data-gtm"))
        if prod and prod.get("dispoweb") is not None:
            try:
                return 1 if int(prod["dispoweb"]) == 1 else 0
            except (TypeError, ValueError):
                pass

    # 5) enabled add-to-cart button is a weak positive.
    if btn and not btn_disabled:
        return 1
    return None


def parse_stock_count(soup: BeautifulSoup):
    """Extract an explicit 'X in stock' count if the PDP exposes one, else None."""
    for sel in ['.availability', '.product-availability', '.availability-msg',
                '.stock-message', '.quantity']:
        e = soup.select_one(sel)
        if not e:
            continue
        t = e.get_text(" ", strip=True).lower()
        for pat in [r"(\d+)\s+(?:produit|article)s?\s+en\s+stock",
                    r"(?:reste que|il reste|reste)\s+(\d+)",
                    r"(\d+)\s+disponible",
                    r"(\d+)\s+in\s+stock"]:
            m = re.search(pat, t)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
    return None


def parse_detail_title(soup: BeautifulSoup) -> str | None:
    """Best-effort PDP title (for discovery), from h1 / schema.org name."""
    for sel in ['h1.product-name', 'h1[itemprop="name"]', '.product-name h1',
                'h1', '[itemprop="name"]']:
        e = soup.select_one(sel)
        if e:
            t = e.get_text(" ", strip=True)
            if t:
                return t
    return None


def parse_detail_description(soup: BeautifulSoup, limit: int = 600) -> str:
    """Best-effort PDP description text (for the sealed/kind gate)."""
    for sel in ['.product-description', '[itemprop="description"]',
                '.description-and-detail', '.long-description', '.pdp-description']:
        e = soup.select_one(sel)
        if e:
            t = e.get_text(" ", strip=True)
            if t:
                return re.sub(r"\s+", " ", t)[:limit]
    return ""
