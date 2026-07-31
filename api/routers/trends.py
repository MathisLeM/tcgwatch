"""Cardmarket market-price trends (sealed products + singles).

Read-only endpoints over `cm_tracked` / `cm_prices`:
  - GET /trends?game=optcg&category=sealed|single -> tracked items with the latest
    price, the change since the first snapshot, and a sparkline series.
  - GET /trends/{id_product} -> full price history for one item (for a chart).

This is Cardmarket *market value* (EUR), separate from the shop-scraped
availability in /products.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.cardmarket import CmPrice, CmTracked

router = APIRouter()


def _pct(first: Optional[float], last: Optional[float]) -> Optional[float]:
    if first in (None, 0) or last is None:
        return None
    return round((last - first) / first * 100, 1)


@router.get("")
def list_trends(
    db: Session = Depends(get_db),
    game: str = Query("optcg"),
    category: Optional[str] = Query(None, description="sealed | single"),
):
    q = db.query(CmTracked).filter(CmTracked.game == game)
    if category:
        q = q.filter(CmTracked.category == category)
    tracked = q.all()
    if not tracked:
        return []

    ids = [t.id_product for t in tracked]
    # All price points for these products, chronological.
    rows = (
        db.query(CmPrice)
        .filter(CmPrice.id_product.in_(ids))
        .order_by(CmPrice.id_product, CmPrice.observed_on)
        .all()
    )
    series: dict[int, list[CmPrice]] = {}
    for r in rows:
        series.setdefault(r.id_product, []).append(r)

    out = []
    for t in tracked:
        pts = series.get(t.id_product, [])
        latest = pts[-1] if pts else None
        first = pts[0] if pts else None
        out.append({
            "id_product": t.id_product,
            "category": t.category,
            "name": t.name,
            "set_code": t.set_code,
            "kind": t.kind,
            "card_code": t.card_code,
            "card_set": t.card_set,
            "image": t.image_path,
            "latest": None if latest is None else {
                "observed_on": latest.observed_on, "trend": latest.trend,
                "low": latest.low, "avg": latest.avg,
            },
            "first_on": first.observed_on if first else None,
            "first_trend": first.trend if first else None,
            "delta_pct": _pct(first.trend if first else None,
                              latest.trend if latest else None),
            "points": [{"d": p.observed_on, "t": p.trend} for p in pts if p.trend is not None],
        })

    # Sealed by set + kind (box before case); singles by card code.
    def sort_key(item):
        return (item["category"], item["set_code"] or "", item["kind"] or "",
                item["card_code"] or "")
    out.sort(key=sort_key)
    return out


@router.get("/{id_product}")
def trend_detail(id_product: int, db: Session = Depends(get_db)):
    t = db.get(CmTracked, id_product)
    if t is None:
        raise HTTPException(status_code=404, detail="Not tracked")
    pts = (
        db.query(CmPrice)
        .filter(CmPrice.id_product == id_product)
        .order_by(CmPrice.observed_on)
        .all()
    )
    return {
        "id_product": t.id_product,
        "category": t.category,
        "name": t.name,
        "set_code": t.set_code,
        "kind": t.kind,
        "card_code": t.card_code,
        "card_set": t.card_set,
        "image": t.image_path,
        "points": [{
            "d": p.observed_on, "avg": p.avg, "low": p.low,
            "trend": p.trend, "avg7": p.avg7, "avg30": p.avg30,
        } for p in pts],
    }
