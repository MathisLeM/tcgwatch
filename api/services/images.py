"""Representative image for a tracked listing.

Reuses the same curated image sets the catalogue uses (`api/routers/catalog.py`),
so a product row in the dashboard and its set tile in the catalogue show the same
art. Returns a **root-relative** path (e.g. `images/Pokemon/...`) which the
frontend turns into an absolute URL via `imageUrl()`; the API serves these from
its `/images` static mount (Cloudflare R2 in prod).
"""
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=4096)
def listing_image(game: str, set_code: Optional[str], kind: Optional[str]) -> Optional[str]:
    """Image path for a (game, set, article-type), or None if nothing is curated.

    Pokemon has one image per set/series; OPTCG & Naruto curate per article-type
    (display vs booster art) and fall back to the set's representative image.
    Cached because `/products` resolves this per row and the lookups stat the
    images directory.
    """
    if not set_code:
        return None
    from scraper.games.pokemon_hierarchy import _rel

    if game == "pokemon":
        from scraper.games import pokemon
        return _rel(pokemon.series_image(set_code))

    from scraper.games import optcg
    return _rel(optcg.kind_image(set_code, kind or "") or optcg.set_image(set_code))
