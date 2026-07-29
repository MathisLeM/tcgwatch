"""POC: stealthy headless scraping of an Imperva/Incapsula-protected retailer.

Target: micromania.fr (GameStop FR) — Pokemon trading-card products.
Fallback target: smythstoys.com/fr/fr-fr/ (also Incapsula).

GOAL
----
This is a *feasibility* probe, NOT a production scraper and NOT part of the
pipeline. It answers one question: can a stealthy headless Chromium clear the
Incapsula JS challenge well enough to read real product data, and if so, how
fragile is it?

It is deliberately gentle:
  * one browser session, a handful of navigations, delays between them;
  * no aggressive looping, no parallelism, no cookie farming.

USAGE
-----
    python -m scraper.poc.micromania_playwright              # headless, no proxy
    python -m scraper.poc.micromania_playwright --headful    # visible browser
    PROXY_URL=http://user:pass@host:port python -m scraper.poc.micromania_playwright

Artifacts (screenshot + HTML dump per page) are written next to this file so
the run leaves auditable proof of what Incapsula actually returned.

Importing this module must have no side effects (it only defines functions),
so `python -c "import scraper.poc.micromania_playwright"` is safe.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import json
import datetime as dt
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# A current, real desktop-Chrome UA. Must match the Chromium major we ship as
# closely as possible; Incapsula cross-checks UA vs. sec-ch-ua vs. TLS/JS hints.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

# Pages to probe, in order. We start at the home (to acquire incap cookies via
# the challenge), then hit a Pokemon listing where products should render.
TARGETS = {
    "micromania": {
        "home": "https://www.micromania.fr/",
        # Micromania uses /c/<slug> category pages. /c/cartespokemon is the
        # Pokemon trading-card category (sealed boosters, decks, coffrets).
        "listing": "https://www.micromania.fr/c/cartespokemon",
    },
    "smythstoys": {
        "home": "https://www.smythstoys.com/fr/fr-fr/",
        "listing": "https://www.smythstoys.com/fr/fr-fr/search/?text=pokemon",
    },
}


# --------------------------------------------------------------------------- #
# Incapsula detection
# --------------------------------------------------------------------------- #
def looks_like_incapsula_challenge(html: str, status: int | None) -> bool:
    """Heuristic: is this the interstitial JS challenge rather than real content?

    Incapsula challenge pages are tiny, mention _Incapsula_Resource /
    incap_ses, and carry no real DOM. They sometimes come back as 200, often
    as 403/429.
    """
    if html is None:
        return True
    h = html.lower()
    # Strong markers that only appear on the interstitial itself. (We avoid
    # generic strings like "incap_ses" — those also show up in the cookie-setting
    # JS embedded on perfectly normal cleared pages, causing false positives.)
    challenge_markers = (
        "_incapsula_resource",
        "subject requested illegal",
        "incident id",
        "powered by imperva",
    )
    hit = any(m in h for m in challenge_markers)
    # The real challenge page is tiny; a cleared page is hundreds of KB. So a
    # marker hit on a large page is almost certainly the embedded resource
    # loader, not the block screen.
    tiny = len(html) < 5000
    blocked_status = status in (403, 429, 503)
    return (hit and tiny) or (tiny and blocked_status) or (hit and blocked_status)


def cookie_summary(cookies: list[dict]) -> str:
    names = sorted({c.get("name", "") for c in cookies})
    incap = [n for n in names if n.startswith(("incap_ses", "visid_incap", "nlbi"))]
    return f"{len(names)} cookies; incapsula={incap or 'NONE'}"


# --------------------------------------------------------------------------- #
# Product extraction
# --------------------------------------------------------------------------- #
def _to_price(text: str | None):
    if not text:
        return None
    m = re.search(r"(\d{1,4}(?:[  .]\d{3})*[,.]\d{2})", text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def extract_products(page, base_url: str, limit: int = 8) -> list[dict]:
    """Best-effort product extraction. Tries JSON-LD first, then resilient DOM.

    We never assume a selector matches — every step is guarded and we log how
    many candidates each strategy found so a future layout change is debuggable.
    """
    products: list[dict] = []

    # Strategy 1: schema.org JSON-LD Product/ItemList (most stable when present).
    try:
        for raw in page.eval_on_selector_all(
            'script[type="application/ld+json"]', "els => els.map(e => e.textContent)"
        ):
            try:
                data = json.loads(raw)
            except Exception:
                continue
            for node in _iter_ld_products(data):
                name = node.get("name")
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("price") if isinstance(offers, dict) else None
                url = node.get("url") or node.get("@id")
                if name:
                    products.append({
                        "title": str(name).strip(),
                        "price": _to_price(str(price)) if price is not None else None,
                        "url": _abs(url, base_url),
                        "available": _ld_avail(offers),
                        "source": "json-ld",
                    })
        if products:
            print(f"  [extract] JSON-LD yielded {len(products)} products")
    except Exception as e:
        print(f"  [extract] JSON-LD step failed: {e}")

    if products:
        return _dedupe(products)[:limit]

    # Strategy 2: DOM. Try several common product-tile selectors; stop at the
    # first that returns a meaningful number of nodes.
    tile_selectors = [
        "[data-testid*='product']",
        "li.product, div.product",
        ".product-tile, .product-card, .productTile, .product-item",
        "article[class*='product']",
        "a[href*='/p/'], a[href*='/produit'], a[href*='-p-']",
    ]
    for sel in tile_selectors:
        try:
            count = page.locator(sel).count()
        except Exception:
            count = 0
        if count >= 3:
            print(f"  [extract] DOM selector {sel!r} matched {count} nodes")
            products = _extract_tiles(page, sel, base_url, limit)
            if products:
                break
    if not products:
        print("  [extract] no product tiles matched any known selector")
    return _dedupe(products)[:limit]


def _extract_tiles(page, sel: str, base_url: str, limit: int) -> list[dict]:
    out: list[dict] = []
    nodes = page.locator(sel)
    n = min(nodes.count(), limit * 3)
    for i in range(n):
        node = nodes.nth(i)
        try:
            title = _first_text(node, [
                "[class*='title']", "[class*='name']", "h2", "h3", "a[title]", "a",
            ])
            price = _to_price(_first_text(node, [
                "[class*='price']", "[data-testid*='price']", ".price",
            ]))
            href = None
            try:
                link = node if sel.startswith("a") else node.locator("a").first
                href = link.get_attribute("href")
            except Exception:
                href = None
            if title:
                out.append({
                    "title": title.strip(),
                    "price": price,
                    "url": _abs(href, base_url),
                    "available": None,
                    "source": "dom",
                })
        except Exception as e:
            print(f"  [extract] tile #{i} failed: {e}")
        if len(out) >= limit:
            break
    return out


def _first_text(node, selectors: list[str]) -> str | None:
    for s in selectors:
        try:
            loc = node.locator(s).first
            if loc.count() > 0:
                t = loc.inner_text(timeout=1000)
                if t and t.strip():
                    return t
        except Exception:
            continue
    # last resort: the node's own text
    try:
        t = node.inner_text(timeout=1000)
        return t if t and t.strip() else None
    except Exception:
        return None


def _iter_ld_products(data):
    """Yield Product nodes from arbitrary JSON-LD shapes."""
    stack = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, dict):
            t = cur.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(str(x).lower() == "product" for x in types):
                yield cur
            for v in cur.values():
                if isinstance(v, (list, dict)):
                    stack.append(v)


def _ld_avail(offers):
    if not isinstance(offers, dict):
        return None
    a = str(offers.get("availability", "")).lower()
    if "outofstock" in a or "soldout" in a:
        return 0
    if "instock" in a or "preorder" in a:
        return 1
    return None


def _abs(href: str | None, base_url: str) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    from urllib.parse import urljoin
    return urljoin(base_url, href)


def _dedupe(products: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for p in products:
        key = (p.get("title"), p.get("url"))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def _save_artifacts(page, tag: str):
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    png = OUT_DIR / f"{tag}_{ts}.png"
    htm = OUT_DIR / f"{tag}_{ts}.html"
    try:
        page.screenshot(path=str(png), full_page=True)
    except Exception as e:
        print(f"  [artifact] screenshot failed: {e}")
        png = None
    try:
        htm.write_text(page.content(), encoding="utf-8")
    except Exception as e:
        print(f"  [artifact] html dump failed: {e}")
        htm = None
    return png, htm


def _stealth_init_script() -> str:
    """Manual evasions applied on top of (or instead of) playwright-stealth."""
    return """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.chrome = window.chrome || { runtime: {} };
    Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1,2,3,4,5].map(i => ({name: 'plugin'+i}))
    });
    const origQuery = navigator.permissions && navigator.permissions.query;
    if (origQuery) {
        navigator.permissions.query = (p) => (
            p && p.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : origQuery(p)
        );
    }
    """


def run(target_key: str, headful: bool, proxy_url: str | None):
    from playwright.sync_api import sync_playwright
    try:
        from playwright_stealth import Stealth
        have_stealth = True
    except Exception:
        Stealth = None
        have_stealth = False

    targets = TARGETS[target_key]
    print(f"=== Incapsula POC: {target_key} ===")
    print(f"  headless={not headful}  proxy={'yes' if proxy_url else 'no'}  "
          f"playwright-stealth={'yes' if have_stealth else 'no (manual evasions)'}")

    launch_args = {
        "headless": not headful,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    }
    if proxy_url:
        launch_args["proxy"] = {"server": proxy_url}

    context_args = {
        "user_agent": USER_AGENT,
        "locale": "fr-FR",
        "timezone_id": "Europe/Paris",
        "viewport": {"width": 1280, "height": 800},
        "geolocation": {"latitude": 48.8566, "longitude": 2.3522},
        "permissions": [],
        "extra_http_headers": {
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    }

    verdict = {"target": target_key, "headless": not headful, "proxy": bool(proxy_url)}

    # Stealth() wraps sync_playwright so its evasions auto-apply to every context.
    stealth_cm = Stealth().use_sync(sync_playwright()) if have_stealth else sync_playwright()
    with stealth_cm as p:
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(**context_args)
        context.add_init_script(_stealth_init_script())
        page = context.new_page()
        page.set_default_navigation_timeout(45000)

        try:
            # --- Home: acquire incap cookies via the challenge --------------- #
            print(f"\n[1] GET home: {targets['home']}")
            resp = _goto(page, targets["home"])
            status = resp.status if resp else None
            time.sleep(6)  # let the Incapsula JS challenge run + redirect
            _settle(page)
            html = page.content()
            challenged = looks_like_incapsula_challenge(html, status)
            cookies = context.cookies()
            print(f"  status={status}  bytes={len(html)}  "
                  f"challenge_page={challenged}")
            print(f"  {cookie_summary(cookies)}")
            png, htm = _save_artifacts(page, f"{target_key}_home")
            print(f"  artifacts: {png and png.name}, {htm and htm.name}")

            verdict["home"] = {
                "status": status, "bytes": len(html),
                "challenge_page": challenged,
                "incap_cookies": [c["name"] for c in cookies
                                  if c["name"].startswith(("incap", "visid", "nlbi"))],
            }

            time.sleep(3)  # be polite between navigations

            # --- Listing: where real products should render ------------------ #
            print(f"\n[2] GET listing: {targets['listing']}")
            resp = _goto(page, targets["listing"])
            status = resp.status if resp else None
            time.sleep(5)
            _settle(page)
            html = page.content()
            challenged = looks_like_incapsula_challenge(html, status)
            print(f"  status={status}  bytes={len(html)}  challenge_page={challenged}")
            png, htm = _save_artifacts(page, f"{target_key}_listing")
            print(f"  artifacts: {png and png.name}, {htm and htm.name}")

            products = [] if challenged else extract_products(page, targets["listing"])
            verdict["listing"] = {
                "status": status, "bytes": len(html),
                "challenge_page": challenged,
                "n_products": len(products),
            }
            verdict["products_sample"] = products[:5]

            print(f"\n[3] Extracted {len(products)} products")
            for pr in products[:5]:
                price = f"{pr['price']:.2f} EUR" if pr.get("price") is not None else "?"
                print(f"   - {pr['title'][:60]:<60} {price:>12}  "
                      f"{(pr.get('url') or '')[:70]}")
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            verdict["error"] = f"{type(e).__name__}: {e}"
            try:
                _save_artifacts(page, f"{target_key}_error")
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    _print_verdict(verdict)
    return verdict


def _goto(page, url):
    """Navigate with a tolerant wait condition (challenge pages stall 'load')."""
    try:
        return page.goto(url, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  [goto] domcontentloaded failed ({e}); retrying with 'commit'")
        try:
            return page.goto(url, wait_until="commit")
        except Exception as e2:
            print(f"  [goto] commit also failed: {e2}")
            return None


def _settle(page):
    """Give the page a chance to finish network activity post-challenge."""
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass


def _print_verdict(v: dict):
    print("\n" + "=" * 60)
    print("FEASIBILITY VERDICT")
    print("=" * 60)
    print(json.dumps(v, indent=2, ensure_ascii=False))
    home = v.get("home", {})
    lst = v.get("listing", {})
    passed = (not lst.get("challenge_page", True)) and lst.get("n_products", 0) > 0
    if passed:
        print(f"\n>>> PASSED: Incapsula cleared, {lst['n_products']} products read.")
    elif not home.get("challenge_page", True):
        print("\n>>> PARTIAL: home cleared but listing yielded no products "
              "(layout/selector issue or soft block).")
    else:
        print("\n>>> BLOCKED: still on the Incapsula challenge page.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Incapsula stealth scraping POC")
    ap.add_argument("--target", default="micromania",
                    choices=list(TARGETS.keys()))
    ap.add_argument("--headful", action="store_true",
                    help="run a visible browser (compare vs headless)")
    args = ap.parse_args(argv)
    proxy_url = os.environ.get("PROXY_URL") or None
    run(args.target, headful=args.headful, proxy_url=proxy_url)


if __name__ == "__main__":
    main()
