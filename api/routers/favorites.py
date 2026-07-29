"""Watchlist / favorites — protected CRUD scoped to the current user."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.catalog import Catalog, Product
from api.models.favorite import Favorite
from api.routers.auth import CurrentUser, get_current_user
from api.schemas import FavoriteCreate, FavoriteOut, ProductListing
from api.services.listings import query_listings, status_of

router = APIRouter()


@router.get("/listings", response_model=list[ProductListing])
def favorite_listings(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The current user's favorited products, as full listings (for the Favoris page)."""
    product_ids = [
        f.product_id
        for f in db.query(Favorite)
        .filter(Favorite.user_id == user.user_id, Favorite.product_id.isnot(None))
        .all()
    ]
    if not product_ids:
        return []
    _, rows = query_listings(db, product_ids=product_ids, limit=500)
    return [ProductListing(**row, status=status_of(row.get("available"))) for row in rows]


@router.get("", response_model=list[FavoriteOut])
def list_favorites(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favs = db.query(Favorite).filter(Favorite.user_id == user.user_id).all()
    return [FavoriteOut.model_validate(f, from_attributes=True) for f in favs]


@router.post("", response_model=FavoriteOut, status_code=201)
def add_favorite(
    body: FavoriteCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if bool(body.product_id) == bool(body.catalog_id):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of product_id or catalog_id",
        )
    if body.product_id and not db.get(Product, body.product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    if body.catalog_id and not db.get(Catalog, body.catalog_id):
        raise HTTPException(status_code=404, detail="Catalog item not found")

    existing = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == user.user_id,
            Favorite.product_id == body.product_id,
            Favorite.catalog_id == body.catalog_id,
        )
        .first()
    )
    if existing:
        return FavoriteOut.model_validate(existing, from_attributes=True)

    fav = Favorite(
        user_id=user.user_id,
        product_id=body.product_id,
        catalog_id=body.catalog_id,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return FavoriteOut.model_validate(fav, from_attributes=True)


@router.delete("/{favorite_id}", status_code=204)
def delete_favorite(
    favorite_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fav = (
        db.query(Favorite)
        .filter(Favorite.id == favorite_id, Favorite.user_id == user.user_id)
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
