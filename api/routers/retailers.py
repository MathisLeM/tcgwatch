"""Big-chain ("Grandes enseignes") endpoints.

3-level drill-down: list retailers -> a retailer's products (by TCG) -> per-store
stock for one product near a postal code (on demand, via the stealth browser).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api import retailers as reg
from api.database import get_db
from api.models.catalog import Product
from api.schemas import (
    ProductListing,
    ProductPage,
    RetailerOut,
    StoreStock,
    StoreStockResponse,
)
from api.services.listings import query_listings, status_of
from api.services.store_inventory import fetch_store_stock

router = APIRouter()


@router.get("", response_model=list[RetailerOut])
def list_retailers(db: Session = Depends(get_db)):
    """All retailers (live + soon + blocked). Live ones include an item count."""
    counts = dict(
        db.execute(text(
            "SELECT platform, COUNT(*) FROM products GROUP BY platform"
        )).all()
    )
    out = []
    for r in reg.RETAILERS:
        out.append(RetailerOut(
            **r.model_dump(),
            item_count=counts.get(r.platform) if r.platform else None,
        ))
    return out


def _live_retailer(rid: str) -> reg.Retailer:
    r = reg.get_by_id(rid)
    if not r:
        raise HTTPException(status_code=404, detail="Enseigne inconnue")
    if r.status != "live" or not r.platform:
        raise HTTPException(status_code=409, detail=f"Enseigne '{r.name}' non disponible ({r.status})")
    return r


@router.get("/{rid}/products", response_model=ProductPage)
def retailer_products(
    rid: str,
    db: Session = Depends(get_db),
    game: Optional[list[str]] = Query(None),
    set_code: Optional[list[str]] = Query(None),
    kind: Optional[list[str]] = Query(None),
    status: Optional[list[str]] = Query(None),
    search: Optional[str] = Query(None),
    order: str = Query("default"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    r = _live_retailer(rid)
    total, rows = query_listings(
        db, platforms=[r.platform], games=game, set_codes=set_code, kinds=kind,
        statuses=status, search=search, order=order, limit=limit, offset=offset,
    )
    items = [ProductListing(**row, status=status_of(row.get("available"))) for row in rows]
    return ProductPage(total=total, limit=limit, offset=offset, items=items)


@router.get("/{rid}/products/{product_id}/stores", response_model=StoreStockResponse)
def product_store_stock(
    rid: str,
    product_id: int,
    near: str = Query(..., min_length=2, description="Code postal ou ville"),
    radius: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    """Per-store availability for a product near `near` (live browser query)."""
    r = _live_retailer(rid)
    if not r.has_store_stock:
        raise HTTPException(status_code=409, detail=f"'{r.name}' n'expose pas de stock par magasin")
    product = db.get(Product, product_id)
    if not product or product.platform != r.platform:
        raise HTTPException(status_code=404, detail="Produit introuvable pour cette enseigne")
    try:
        stores = fetch_store_stock(product.url, product.platform_pid, near, radius=radius)
    except Exception as exc:  # noqa: BLE001 — browser/anti-bot failures shouldn't 500 hard
        raise HTTPException(status_code=502, detail=f"Stock magasin indisponible: {exc}")
    return StoreStockResponse(
        product_id=product_id,
        pid=product.platform_pid,
        postal=near,
        stores=[StoreStock(**s) for s in stores],
    )
