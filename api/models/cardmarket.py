"""Cardmarket price-history models (market-value trends).

Separate from the shop-scraped `products`/`snapshots` tables: this is Cardmarket
reference/market pricing (EUR), keyed by Cardmarket `id_product`, ingested from
`price_guide_*.json` snapshots. Sealed products (booster boxes, cases) and singles
(individual cards) both live here, distinguished by `category`.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class CmTracked(Base):
    """A Cardmarket product we track the price of (sealed SKU or single card)."""
    __tablename__ = "cm_tracked"

    id_product: Mapped[int] = mapped_column(primary_key=True)   # Cardmarket idProduct
    game: Mapped[str] = mapped_column(default="optcg", nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)       # 'sealed' | 'single'
    name: Mapped[str] = mapped_column(nullable=False)
    set_code: Mapped[Optional[str]] = mapped_column()           # 'OP09' (sealed)
    kind: Mapped[Optional[str]] = mapped_column()               # 'Booster Box' | 'Sleeved Pack Case'
    card_code: Mapped[Optional[str]] = mapped_column()          # 'OP01-060' (single)
    card_set: Mapped[Optional[str]] = mapped_column()           # expansion name (single)
    image_path: Mapped[Optional[str]] = mapped_column()         # root-relative image, if any

    prices: Mapped[list["CmPrice"]] = relationship(
        back_populates="tracked", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (Index("idx_cm_tracked_cat", "game", "category"),)


class CmPrice(Base):
    """One Cardmarket price-guide snapshot for a tracked product."""
    __tablename__ = "cm_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_product: Mapped[int] = mapped_column(
        ForeignKey("cm_tracked.id_product", ondelete="CASCADE"), nullable=False
    )
    observed_on: Mapped[str] = mapped_column(nullable=False)    # ISO date (snapshot day)
    avg: Mapped[Optional[float]] = mapped_column(Float)
    low: Mapped[Optional[float]] = mapped_column(Float)
    trend: Mapped[Optional[float]] = mapped_column(Float)
    avg7: Mapped[Optional[float]] = mapped_column(Float)
    avg30: Mapped[Optional[float]] = mapped_column(Float)

    tracked: Mapped["CmTracked"] = relationship(back_populates="prices")

    __table_args__ = (
        UniqueConstraint("id_product", "observed_on", name="uq_cm_price_snapshot"),
        Index("idx_cm_prices_product_date", "id_product", "observed_on"),
    )
