"""Watchlist / favorites.

A favorite targets EITHER a specific shop listing (`product_id`) OR a canonical
SKU (`catalog_id`). Exactly one is set. Uniqueness is enforced per user+target.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    catalog_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("catalog.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_fav_user_product"),
        UniqueConstraint("user_id", "catalog_id", name="uq_fav_user_catalog"),
    )
