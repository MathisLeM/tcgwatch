"""Multi-TCG navigation catalogue: **TCG > (block >) set > article type**.

Powers the post-login home (the 3-TCG chooser) and the drill-down beneath it.
One shape, two modes:
  - Pokemon    -> `mode="blocks"` : block > set > article-type (reuses the Pokemon
                  hierarchy builder, with images + localized names).
  - OPTCG /    -> `mode="sets"`   : a flat set list > article-type (no block layer),
    Naruto        set names/order/images from `scraper.games.optcg`.

Every level carries live availability: `product_count` (fiches enregistrées),
`available_count` (en stock à l'instant, d'après le dernier snapshot) and
`min_price` (prix mini en stock, si connu) — so the frontend can preview stock and
price ("2/20 · dès 24,90 €") without a second call.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, text
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.catalog import Product
from api.services.kinds import effective_kind

router = APIRouter()

# Display metadata per tracked game.
GAME_META = {
    "pokemon":       {"label": "Pokémon",       "mode": "blocks"},
    "optcg":         {"label": "One Piece",      "mode": "sets"},
    "naruto_mythos": {"label": "Naruto Mythos",  "mode": "sets"},
}
GAME_ORDER = ["pokemon", "optcg", "naruto_mythos"]


def _rel_image(abs_path: Optional[str]) -> Optional[str]:
    from scraper.games.pokemon_hierarchy import _rel
    return _rel(abs_path)


def _game_image(game: str) -> Optional[str]:
    """A representative image for the TCG chooser card."""
    if game == "pokemon":
        from scraper.games import pokemon
        return _rel_image(pokemon.block_image("me") or pokemon.block_image("sv"))
    from scraper.games import optcg
    reps = {"optcg": ["OP17", "OP16", "PRB02"], "naruto_mythos": ["NRT-KS-ED1"]}
    for code in reps.get(game, []):
        img = optcg.set_image(code)
        if img:
            return _rel_image(img)
    return None


def _min_opt(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _current_rows(db: Session, game: str):
    """Latest snapshot per product for a game: (language, set_code, kind, title,
    price, available). One row per product (its current price/stock)."""
    sql = text("""
        WITH ranked AS (
            SELECT p.language AS language, COALESCE(p.set_code, '') AS set_code,
                   p.kind AS kind, p.title AS title, p.game AS game,
                   s.price_eur AS price, s.available AS available,
                   ROW_NUMBER() OVER (PARTITION BY s.product_id
                                      ORDER BY s.observed_at DESC) AS rn
            FROM products p
            JOIN snapshots s ON s.product_id = p.id
            WHERE p.game = :game
        )
        SELECT language, set_code, kind, title, game, price, available
        FROM ranked WHERE rn = 1
    """)
    return db.execute(sql, {"game": game}).mappings().all()


def _aggregate(rows):
    """From current rows -> ({(lang,set,kind): count},
                             {(lang,set,kind): {available, min_price}})."""
    counts: dict[tuple, int] = {}
    stats: dict[tuple, dict] = {}
    for r in rows:
        kind = effective_kind(r["game"], r["kind"], r["title"]) or "unknown"
        key = (r["language"], r["set_code"], kind)
        counts[key] = counts.get(key, 0) + 1
        st = stats.setdefault(key, {"available": 0, "min_price": None})
        if r["available"] == 1:
            st["available"] += 1
            if r["price"] is not None:
                st["min_price"] = _min_opt(st["min_price"], float(r["price"]))
    return counts, stats


def _enrich_kinds(kinds: list, lang: str, set_code: str, stats: dict) -> tuple:
    """Add `available_count` + `min_price` to each kind node; return the set-level
    rollup (total available, min in-stock price)."""
    avail, min_price = 0, None
    for k in kinds:
        st = stats.get((lang, set_code, k["kind"]), {})
        a = st.get("available", 0)
        p = st.get("min_price")
        k["available_count"] = a
        k["min_price"] = p
        avail += a
        min_price = _min_opt(min_price, p)
    return avail, min_price


@router.get("/games")
def list_games(db: Session = Depends(get_db)):
    """The TCG chooser: one entry per tracked game with live counts + an image."""
    # Product counts + current availability (latest snapshot) per game.
    avail_rows = db.execute(text("""
        WITH ranked AS (
            SELECT p.game AS game, s.available AS available,
                   ROW_NUMBER() OVER (PARTITION BY s.product_id
                                      ORDER BY s.observed_at DESC) AS rn
            FROM products p JOIN snapshots s ON s.product_id = p.id
        )
        SELECT game, SUM(CASE WHEN available = 1 THEN 1 ELSE 0 END) AS avail
        FROM ranked WHERE rn = 1 GROUP BY game
    """)).all()
    avail_by_game = {g: int(a or 0) for g, a in avail_rows}

    prod_counts = dict(
        db.query(Product.game, func.count(Product.id)).group_by(Product.game).all()
    )
    set_counts = dict(
        db.query(Product.game, func.count(distinct(Product.set_code)))
        .filter(Product.set_code != "")
        .group_by(Product.game)
        .all()
    )
    out = []
    for game in GAME_ORDER:
        meta = GAME_META[game]
        out.append({
            "game": game,
            "label": meta["label"],
            "mode": meta["mode"],
            "product_count": int(prod_counts.get(game, 0)),
            "available_count": avail_by_game.get(game, 0),
            "set_count": int(set_counts.get(game, 0)),
            "image": _game_image(game),
        })
    return out


def _optcg_catalog(db: Session, game: str) -> dict:
    """Flat set > article-type tree for OPTCG / Naruto (French-only).

    Kind is derived from each title on-read, and availability/price come from the
    latest snapshot — so the tree is correct with no backfill / migration.
    """
    from scraper.games import optcg

    counts, stats = _aggregate(_current_rows(db, game))
    present = sorted({sc for (_, sc, _) in counts if sc}, key=optcg.set_order_index)

    sets = []
    for code in present:
        kinds = []
        for kind in optcg.KIND_ORDER:
            n = counts.get(("fr", code, kind), 0)
            if n:
                kinds.append({
                    "kind": kind,
                    "label": optcg.kind_label(kind, "fr"),
                    "label_en": optcg.kind_label(kind, "en"),
                    "product_count": n,
                    "image": _rel_image(optcg.kind_image(code, kind)),
                })
        avail, min_price = _enrich_kinds(kinds, "fr", code, stats)
        sets.append({
            "set_code": code,
            "language": "fr",
            "abbreviation": code,
            "name": optcg.set_name(code),
            "image": _rel_image(optcg.set_image(code)),
            "product_count": sum(k["product_count"] for k in kinds),
            "available_count": avail,
            "min_price": min_price,
            "kinds": kinds,
        })

    unassigned_kinds: dict[str, int] = {}
    for (_, sc, kind), n in counts.items():
        if not sc:
            unassigned_kinds[kind] = unassigned_kinds.get(kind, 0) + n
    unassigned = {
        "product_count": sum(unassigned_kinds.values()),
        "kinds": [{"kind": k, "label": optcg.kind_label(k, "fr"), "product_count": v}
                  for k, v in sorted(unassigned_kinds.items(), key=lambda kv: -kv[1])],
    }
    return {"game": game, "mode": "sets", "language": "fr",
            "set_count": len(sets), "sets": sets, "unassigned": unassigned}


def _pokemon_catalog(db: Session, language: Optional[str]) -> dict:
    from scraper.games.pokemon_hierarchy import build_hierarchy

    rows = _current_rows(db, "pokemon")
    if language:
        rows = [r for r in rows if r["language"] == language]
    counts, stats = _aggregate(rows)
    hierarchy = build_hierarchy(counts, languages=[language] if language else None)

    # Enrich every set + block with availability + min in-stock price.
    for block in hierarchy["blocks"]:
        b_avail, b_min = 0, None
        for s in block["sets"]:
            s_avail, s_min = _enrich_kinds(s["kinds"], s["language"], s["set_code"], stats)
            s["available_count"] = s_avail
            s["min_price"] = s_min
            b_avail += s_avail
            b_min = _min_opt(b_min, s_min)
        block["available_count"] = b_avail
        block["min_price"] = b_min

    return {"game": "pokemon", "mode": "blocks", **hierarchy}


@router.get("")
def get_catalog(
    game: str = Query(..., description="pokemon | optcg | naruto_mythos"),
    language: Optional[str] = Query(None, description="Pokemon only: fr/en/ja/ko/zh"),
    db: Session = Depends(get_db),
):
    """Navigation tree for one TCG (block>set>type for Pokemon, set>type otherwise)."""
    if game not in GAME_META:
        raise HTTPException(status_code=404, detail=f"Unknown game: {game}")
    if game == "pokemon":
        return _pokemon_catalog(db, language)
    return _optcg_catalog(db, game)
