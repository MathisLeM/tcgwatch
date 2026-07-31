"""Cardmarket market-price tracking (OPTCG to start).

Ingests Cardmarket `price_guide_*.json` snapshots into the `cm_prices` /
`cm_tracked` DB tables (see api/models/cardmarket.py), for a curated set of
sealed products and singles. This is *market value* pricing (Cardmarket, EUR),
separate from the shop-scraped `products`/`snapshots` availability data.
"""
from ..config import DATA_DIR

CM_DIR = DATA_DIR / "cardmarket"
PRICE_GUIDE_DIR = CM_DIR / "price_guide"
TRACKED_PRODUCTS = CM_DIR / "tracked_products.json"
TRACKED_SINGLES = CM_DIR / "tracked_singles.json"

# Cardmarket price-guide fields we keep.
FIELDS = ("avg", "low", "trend", "avg7", "avg30")
