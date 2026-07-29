"""Registry of user-added shops.

The original SHOPIFY_SHOPS / PRESTASHOP_SHOPS / WOOCOMMERCE_SHOPS lists in the
discover_*.py files are the *built-in* shops we curated during initial setup.
This module reads `data/extra_shops.json` and merges it with those built-in
lists at module load time, so adding a new shop never requires editing Python.
"""
import json
from .config import DATA_DIR

EXTRA_FILE = DATA_DIR / "extra_shops.json"

DEFAULT = {"shopify": [], "prestashop": [], "woocommerce": [], "wix": [],
           "powerboutique": [], "nextjs": [], "emonsite": [], "fantasysphere": [],
           "direct_urls": {}}


def load_extras() -> dict:
    if not EXTRA_FILE.exists():
        return DEFAULT.copy()
    try:
        return {**DEFAULT, **json.loads(EXTRA_FILE.read_text(encoding="utf-8"))}
    except Exception:
        return DEFAULT.copy()


def save_extras(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXTRA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_shop(platform: str, host: str, direct_urls: list | None = None) -> bool:
    """Register a new shop. Returns True if added, False if already present.
    `direct_urls` is a list of {'game':..., 'url':..., 'scope':...} dicts (PS only)."""
    if platform not in ("shopify", "prestashop", "woocommerce", "wix", "powerboutique",
                        "nextjs", "emonsite", "fantasysphere"):
        raise ValueError(f"Unknown platform: {platform}")
    data = load_extras()
    if host in data[platform]:
        return False
    data[platform].append(host)
    if direct_urls:
        data["direct_urls"][host] = direct_urls
    save_extras(data)
    return True


def all_shops(platform: str, builtin: list) -> list:
    """Built-in shops + user-added shops, deduplicated, original order preserved."""
    extras = load_extras().get(platform, [])
    seen, out = set(), []
    for h in builtin + extras:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def all_direct_urls(builtin: dict) -> dict:
    """Built-in DIRECT_URLS + user-added ones (for PrestaShop).
    Always returns host -> list of (game, url, scope) tuples."""
    out = {}
    for host, urls in builtin.items():
        out[host] = [(u["game"], u["url"], u["scope"]) if isinstance(u, dict) else u
                     for u in urls]
    for host, urls in load_extras().get("direct_urls", {}).items():
        out[host] = [(u["game"], u["url"], u["scope"]) if isinstance(u, dict) else u
                     for u in urls]
    return out
