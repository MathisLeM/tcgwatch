"""ORM models mirroring the scraper's existing schema (see scraper/db.py).

Column names/types are kept identical to the live SQLite tables so the API can
read the current DB unchanged, and so `create_all`/Alembic produce a compatible
schema on Postgres. Text date columns stay String (the scraper stores ISO text).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class Site(Base):
    __tablename__ = "sites"

    host: Mapped[str] = mapped_column(primary_key=True)        # 'dracaugames.com'
    platform: Mapped[str] = mapped_column(nullable=False)      # 'shopify' | ...
    games: Mapped[Optional[str]] = mapped_column()             # csv: 'optcg,pokemon'
    active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[Optional[str]] = mapped_column()


class Set(Base):
    """Reference set catalogue per (game, language, set_code) — from TCGdex."""
    __tablename__ = "sets"

    game: Mapped[str] = mapped_column(primary_key=True)
    language: Mapped[str] = mapped_column(primary_key=True)
    set_code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column()
    abbreviation: Mapped[Optional[str]] = mapped_column()      # 'OBF','CRI','PRE'
    series: Mapped[Optional[str]] = mapped_column()            # 'sv','swsh','me'
    release_date: Mapped[Optional[str]] = mapped_column()
    logo_url: Mapped[Optional[str]] = mapped_column()
    symbol_url: Mapped[Optional[str]] = mapped_column()
    card_count: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (Index("idx_sets_game_lang", "game", "language"),)


class Catalog(Base):
    """Canonical tracked SKU = (game, language, set_code, kind)."""
    __tablename__ = "catalog"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game: Mapped[str] = mapped_column(nullable=False)
    language: Mapped[str] = mapped_column(nullable=False)
    set_code: Mapped[str] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(nullable=False)          # 'display'|'etb'|...
    display_name: Mapped[Optional[str]] = mapped_column()
    image_path: Mapped[Optional[str]] = mapped_column()

    __table_args__ = (
        UniqueConstraint("game", "language", "set_code", "kind", name="uq_catalog_sku"),
    )


class Product(Base):
    """A shop's listing of a catalog item (stable identity per platform)."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(nullable=False)
    shop: Mapped[str] = mapped_column(nullable=False)
    platform_pid: Mapped[str] = mapped_column(nullable=False)
    game: Mapped[str] = mapped_column(nullable=False)
    language: Mapped[str] = mapped_column(default="fr", nullable=False)
    set_code: Mapped[str] = mapped_column(nullable=False)
    set_codes: Mapped[Optional[str]] = mapped_column()        # ';'-joined multi-set lots
    series: Mapped[Optional[str]] = mapped_column()
    kind: Mapped[Optional[str]] = mapped_column()
    catalog_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("catalog.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(nullable=False)
    url: Mapped[str] = mapped_column(nullable=False)
    first_seen_at: Mapped[str] = mapped_column(nullable=False)

    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("platform", "shop", "platform_pid", name="uq_product_identity"),
        Index("idx_products_game_lang_set", "game", "language", "set_code"),
    )


class Snapshot(Base):
    """One price/stock observation per scrape run per product."""
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    observed_at: Mapped[str] = mapped_column(nullable=False)   # ISO timestamp text
    price_eur: Mapped[Optional[float]] = mapped_column()
    available: Mapped[Optional[int]] = mapped_column(Integer)  # 0/1/NULL (unknown)
    raw_variant_count: Mapped[Optional[int]] = mapped_column(Integer)
    stock_remaining: Mapped[Optional[int]] = mapped_column(Integer)

    product: Mapped["Product"] = relationship(back_populates="snapshots")

    __table_args__ = (Index("idx_snapshots_product_time", "product_id", "observed_at"),)
