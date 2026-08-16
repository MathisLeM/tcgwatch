"""Pydantic schemas (request/response contracts).

Keep these in sync with the frontend's lib/api.ts types (Vigilyx convention).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# ── Auth ────────────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id: int
    email: str            # login identifier — a free-form pseudo OR an email
    is_admin: bool


class SignupRequest(BaseModel):
    # Free-form identifier (pseudo or email); no email-format constraint so a
    # simple pseudo works. Stored in User.email and matched verbatim at login.
    email: str
    password: str


# ── Products / listings ─────────────────────────────────────────────────────
class ProductListing(BaseModel):
    product_id: int
    platform: str
    shop: str
    game: str
    language: str
    set_code: str
    set_codes: Optional[str] = None
    series: Optional[str] = None
    kind: Optional[str] = None
    title: str
    url: str
    price_now: Optional[float] = None
    available: Optional[int] = None          # 0/1/None
    status: str                              # "In Stock" | "Out" | "Unknown"
    stock_remaining: Optional[int] = None
    observed_at: Optional[str] = None
    price_prev: Optional[float] = None
    avail_prev: Optional[int] = None
    image: Optional[str] = None              # root-relative, e.g. "images/Pokemon/..."


class ProductPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProductListing]


class PricePoint(BaseModel):
    """One day of a product's price history (last observation of that day)."""
    d: str                                   # ISO date, YYYY-MM-DD
    p: float                                 # EUR


# ── Sets reference ──────────────────────────────────────────────────────────
class SetRef(BaseModel):
    game: str
    language: str
    set_code: str
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    series: Optional[str] = None
    release_date: Optional[str] = None
    logo_url: Optional[str] = None
    symbol_url: Optional[str] = None
    card_count: Optional[int] = None


# ── Retailers (big chains) ────────────────────────────────────────────────────
class RetailerOut(BaseModel):
    id: str
    name: str
    platform: Optional[str] = None
    status: str                      # live | soon | blocked
    has_store_stock: bool = False
    note: Optional[str] = None
    item_count: Optional[int] = None


class StoreStock(BaseModel):
    store_id: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    click_and_collect: bool = False
    pickup_in_store: bool = False
    ats_value: Optional[int] = None
    available: Optional[bool] = None


class StoreStockResponse(BaseModel):
    product_id: int
    pid: str
    postal: str
    stores: list[StoreStock]


# ── Favorites ───────────────────────────────────────────────────────────────
class FavoriteCreate(BaseModel):
    product_id: Optional[int] = None
    catalog_id: Optional[int] = None


class FavoriteOut(BaseModel):
    id: int
    product_id: Optional[int] = None
    catalog_id: Optional[int] = None
    created_at: datetime


# ── Alerts ──────────────────────────────────────────────────────────────────
class AlertConfigCreate(BaseModel):
    scope_type: str                          # product|catalog|set|favorites
    product_id: Optional[int] = None
    catalog_id: Optional[int] = None
    set_code: Optional[str] = None
    game: Optional[str] = None
    language: Optional[str] = None
    channel: str                             # email|discord
    destination: str                         # email address or Discord webhook URL
    alert_type: str = "any"                  # restock|price_drop|any
    price_threshold: Optional[float] = None


class AlertConfigOut(BaseModel):
    id: int
    scope_type: str
    product_id: Optional[int] = None
    catalog_id: Optional[int] = None
    set_code: Optional[str] = None
    game: Optional[str] = None
    language: Optional[str] = None
    channel: str
    destination: str
    alert_type: str
    price_threshold: Optional[float] = None
    active: bool
    created_at: datetime


# ── Waitlist ────────────────────────────────────────────────────────────────
class WaitlistCreate(BaseModel):
    email: EmailStr
    source: Optional[str] = "landing"


class WaitlistJoined(BaseModel):
    """Réponse publique — volontairement identique que l'e-mail soit nouveau ou
    déjà présent, pour ne pas transformer l'endpoint en oracle d'inscription."""
    ok: bool = True
    message: str


class WaitlistOut(BaseModel):
    """Réservé à l'export admin."""
    id: int
    email: str
    source: Optional[str] = None
    created_at: datetime
