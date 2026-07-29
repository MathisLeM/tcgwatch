"""Public read endpoints for tracked products and filter facets.

Replaces the direct SQLite reads the Streamlit dashboard used to do.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db
from api.schemas import ProductListing, ProductPage
from api.services.kinds import DERIVED_KIND_GAMES, effective_kind
from api.services.listings import query_listings, status_of

router = APIRouter()


@router.get("", response_model=ProductPage)
def list_products(
    db: Session = Depends(get_db),
    game: Optional[list[str]] = Query(None),
    language: Optional[list[str]] = Query(None),
    set_code: Optional[list[str]] = Query(None),
    series: Optional[list[str]] = Query(None),
    kind: Optional[list[str]] = Query(None),
    shop: Optional[list[str]] = Query(None),
    status: Optional[list[str]] = Query(None, description="In Stock | Out | Unknown"),
    max_price: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None),
    order: str = Query("default"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    # OPTCG/Naruto store no `kind`; it's derived from the title on-read. When a
    # kind filter is requested for these games, the SQL WHERE can't use the (NULL)
    # column, so we fetch the matching rows, derive+filter+paginate in Python.
    # Safe because these games are small (a few hundred rows) and French-only.
    derived_only = bool(game) and all(g in DERIVED_KIND_GAMES for g in game)
    if kind and derived_only:
        _, all_rows = query_listings(
            db, games=game, languages=language, set_codes=set_code, series=series,
            kinds=None, shops=shop, statuses=status, max_price=max_price,
            search=search, order=order, limit=100_000, offset=0,
        )
        wanted = set(kind)
        matched = [r for r in all_rows
                   if effective_kind(r["game"], r.get("kind"), r["title"]) in wanted]
        total = len(matched)
        rows = matched[offset:offset + limit]
    else:
        total, rows = query_listings(
            db, games=game, languages=language, set_codes=set_code, series=series,
            kinds=kind, shops=shop, statuses=status, max_price=max_price,
            search=search, order=order, limit=limit, offset=offset,
        )

    items = []
    for row in rows:
        row["kind"] = effective_kind(row["game"], row.get("kind"), row["title"])
        items.append(ProductListing(**row, status=status_of(row.get("available"))))
    return ProductPage(total=total, limit=limit, offset=offset, items=items)


@router.get("/facets")
def facets(
    db: Session = Depends(get_db),
    game: Optional[list[str]] = Query(None),
):
    """Distinct values usable to populate dashboard filter dropdowns."""
    params: dict = {}
    game_filter = ""
    if game:
        keys = []
        for i, g in enumerate(game):
            params[f"g{i}"] = g
            keys.append(f":g{i}")
        game_filter = f" AND game IN ({', '.join(keys)})"

    def distinct(col: str) -> list[str]:
        rows = db.execute(
            text(f"SELECT DISTINCT {col} FROM products "
                 f"WHERE {col} IS NOT NULL AND {col} != ''{game_filter}"),
            params,
        ).scalars().all()
        return sorted(v for v in rows if v)

    # OPTCG/Naruto have no stored kind — derive the kind facet from titles so the
    # dashboard's type dropdown is populated for them too.
    if game and all(g in DERIVED_KIND_GAMES for g in game):
        rows = db.execute(
            text(f"SELECT game, kind, title FROM products WHERE 1=1{game_filter}"), params
        ).all()
        kinds = sorted({k for k in (effective_kind(g, st, t) for g, st, t in rows) if k})
    else:
        kinds = distinct("kind")

    return {
        "games": distinct("game"),
        "languages": distinct("language"),
        "series": distinct("series"),
        "kinds": kinds,
        "shops": distinct("shop"),
        "set_codes": distinct("set_code"),
    }
