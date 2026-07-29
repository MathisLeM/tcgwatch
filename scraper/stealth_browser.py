"""Reusable stealthy headless-Chromium helper (extracted from the Micromania POC).

Some retailers (Micromania / GameStop FR, Smyths, ...) sit behind Imperva /
Incapsula, which serves a JS interstitial challenge to plain HTTP clients. A
stealthy headless Chromium clears that challenge well enough to read real
product data. This module wraps the browser-launch + evasion logic the POC
validated into a single context manager so the discoverer and the fetcher share
exactly the same fingerprint.

Usage
-----
    from .stealth_browser import stealth_page, looks_like_challenge

    with stealth_page() as (page, ctx):
        resp = goto(page, "https://www.micromania.fr/c/cartespokemon")
        html = page.content()
        if looks_like_challenge(html, resp.status if resp else None):
            ...  # abort politely

`PROXY_URL` (env) is honoured as an optional residential-proxy fallback; by
default we run direct (no proxy), which is what the POC cleared.

Importing this module has no side effects (Playwright is imported lazily inside
the context manager), so `import scraper.stealth_browser` is cheap and safe.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

# A current, real desktop-Chrome UA. Must track the Chromium major we ship as
# closely as possible; Incapsula cross-checks UA vs. sec-ch-ua vs. TLS/JS hints.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

# Default per-navigation timeout (ms). Challenge pages stall the 'load' event,
# so callers should prefer `goto()` below which falls back to softer waits.
NAV_TIMEOUT_MS = 45000


# --------------------------------------------------------------------------- #
# Challenge detection (shared so both modules abort on the same signal)
# --------------------------------------------------------------------------- #
def looks_like_challenge(html: str | None, status: int | None) -> bool:
    """Heuristic: is this the Incapsula interstitial rather than real content?

    The real challenge page is tiny (< ~5KB), carries Imperva markers, and/or
    comes back as 403/429/503. A cleared page is hundreds of KB and may *also*
    contain an embedded incap cookie-setter, so a marker hit on a large page is
    NOT treated as a block (avoids false positives).
    """
    if html is None:
        return True
    h = html.lower()
    markers = (
        "_incapsula_resource",
        "subject requested illegal",
        "incident id",
        "powered by imperva",
    )
    hit = any(m in h for m in markers)
    tiny = len(html) < 5000
    blocked_status = status in (403, 429, 503)
    return (hit and tiny) or (tiny and blocked_status) or (hit and blocked_status)


# --------------------------------------------------------------------------- #
# Navigation helpers
# --------------------------------------------------------------------------- #
def goto(page, url: str):
    """Navigate with a tolerant wait condition (challenge pages stall 'load')."""
    try:
        return page.goto(url, wait_until="domcontentloaded")
    except Exception:
        try:
            return page.goto(url, wait_until="commit")
        except Exception:
            return None


def settle(page, timeout: int = 12000) -> None:
    """Give the page a chance to finish network activity post-challenge."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass


def _stealth_init_script() -> str:
    """Manual evasions applied on top of playwright-stealth (belt and braces)."""
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


@contextmanager
def stealth_page(headful: bool = False, proxy_url: str | None = None):
    """Context manager yielding (page, context) on a stealthy Chromium.

    The browser/context/page are torn down on exit no matter what. One session
    should be reused for a whole crawl (this is the polite, heavy resource).

    Parameters
    ----------
    headful : run a visible browser (debugging only).
    proxy_url : explicit proxy; defaults to env `PROXY_URL` or none (direct).
    """
    # Lazy imports so importing this module costs nothing.
    from playwright.sync_api import sync_playwright
    try:
        from playwright_stealth import Stealth
        have_stealth = True
    except Exception:
        Stealth = None
        have_stealth = False

    proxy_url = proxy_url or os.environ.get("PROXY_URL") or None

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
        "extra_http_headers": {"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
    }

    # Stealth() wraps sync_playwright so its evasions auto-apply to every context.
    stealth_cm = Stealth().use_sync(sync_playwright()) if have_stealth else sync_playwright()
    with stealth_cm as p:
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(**context_args)
        context.add_init_script(_stealth_init_script())
        page = context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        try:
            yield page, context
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
