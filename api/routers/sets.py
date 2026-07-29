"""Reference set catalogue (names, abbreviations, series, images).

The frontend joins this with /products to build labels (block · abbr · name),
the same way the Streamlit dashboard's `pokemon_set_meta` did.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.catalog import Product, Set
from api.schemas import SetRef

router = APIRouter()


@router.get("", response_model=list[SetRef])
def list_sets(
    db: Session = Depends(get_db),
    game: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
):
    q = db.query(Set)
    if game:
        q = q.filter(Set.game == game)
    if language:
        q = q.filter(Set.language == language)
    return [SetRef.model_validate(s, from_attributes=True) for s in q.all()]


@router.get("/blocks")
def list_blocks(
    db: Session = Depends(get_db),
    language: Optional[str] = Query(
        None, description="Restrict to one language (fr/en/ja/ko/zh)."
    ),
):
    """Pokemon navigation tree: **block > set > article type**, each level with a
    live tracked-listing count and its image. Backs the frontend drill-down and
    stays in sync with the offline `pokemon_hierarchy` export.
    """
    from scraper.games.pokemon_hierarchy import build_hierarchy

    rows = (
        db.query(
            Product.language,
            func.coalesce(Product.set_code, "").label("set_code"),
            func.coalesce(Product.kind, "unknown").label("kind"),
            func.count(Product.id).label("n"),
        )
        .filter(Product.game == "pokemon")
        .group_by(Product.language, Product.set_code, Product.kind)
    )
    if language:
        rows = rows.filter(Product.language == language)

    counts = {(r.language, r.set_code, r.kind): r.n for r in rows.all()}
    langs = [language] if language else None
    return build_hierarchy(counts, languages=langs)
