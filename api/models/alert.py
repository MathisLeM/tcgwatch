"""Alerting configuration and sent-event log.

AlertConfig = a user's rule ("notify me about X via channel Y when Z happens").
AlertEvent  = a record of a fired/sent notification, used for de-duplication so
              the same restock/price-drop is never sent twice.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Allowed enum-ish values (kept as plain strings for SQLite/Postgres portability)
CHANNELS = ("email", "discord")
ALERT_TYPES = ("restock", "price_drop", "any")
SCOPE_TYPES = ("product", "catalog", "set", "favorites")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # What to watch -----------------------------------------------------------
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)  # SCOPE_TYPES
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    catalog_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("catalog.id", ondelete="CASCADE")
    )
    set_code: Mapped[Optional[str]] = mapped_column(String(32))
    game: Mapped[Optional[str]] = mapped_column(String(32))
    language: Mapped[Optional[str]] = mapped_column(String(8))

    # How / when --------------------------------------------------------------
    channel: Mapped[str] = mapped_column(String(16), nullable=False)     # CHANNELS
    destination: Mapped[str] = mapped_column(String(512), nullable=False)  # email or webhook
    alert_type: Mapped[str] = mapped_column(String(16), default="any", nullable=False)
    price_threshold: Mapped[Optional[float]] = mapped_column(Float)      # only alert below this €
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="alert_configs")
    events: Mapped[list["AlertEvent"]] = relationship(
        back_populates="config", cascade="all, delete-orphan"
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_config_id: Mapped[int] = mapped_column(
        ForeignKey("alert_configs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)  # restock|price_drop
    # The snapshot timestamp that triggered this — part of the dedup key.
    trigger_observed_at: Mapped[str] = mapped_column(String(40), nullable=False)
    price_eur: Mapped[Optional[float]] = mapped_column(Float)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    config: Mapped["AlertConfig"] = relationship(back_populates="events")

    __table_args__ = (
        # Fast dedup lookup: "did we already send THIS event for THIS config?"
        Index(
            "idx_alert_event_dedup",
            "alert_config_id",
            "product_id",
            "event_type",
            "trigger_observed_at",
        ),
    )
