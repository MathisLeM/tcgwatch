"""Alert detection + delivery.

Run after a scrape: for every product, compare its latest snapshot to the
previous one, derive `restock` / `price_drop` events, find the active
`AlertConfig` rules that match, and send a notification (email / Discord) for
each — de-duplicated via `AlertEvent` so the same change is never sent twice.

Backend-agnostic: reads through SQLAlchemy (`api.database.SessionLocal`), so it
works against the local SQLite DB and the production Postgres alike. The
window-function query is identical to the dashboard/API one (works on
SQLite 3.25+ and Postgres).

Usage:
    from scraper.alerting import run_alerting
    run_alerting()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models import AlertConfig, AlertEvent, Favorite
from api.services.notify import send_notification

logger = logging.getLogger("scraper.alerting")

# Price moves smaller than this (in €) are noise, not a "price drop".
PRICE_DROP_EPSILON = 0.5


@dataclass
class _Change:
    """A detected stock/price change on one product (latest vs previous snapshot)."""
    product_id: int
    title: str
    shop: str
    url: str
    game: str
    language: str
    set_code: str
    kind: Optional[str]
    catalog_id: Optional[int]
    observed_at: str          # timestamp of the triggering (latest) snapshot
    price_now: Optional[float]
    price_prev: Optional[float]
    avail_now: Optional[int]
    avail_prev: Optional[int]

    @property
    def is_restock(self) -> bool:
        # out/unknown -> in stock. (NULL prev counts as "was not in stock".)
        return self.avail_now == 1 and (self.avail_prev == 0 or self.avail_prev is None) \
            and self.avail_prev != 1

    @property
    def is_price_drop(self) -> bool:
        return (
            self.price_now is not None
            and self.price_prev is not None
            and (self.price_prev - self.price_now) > PRICE_DROP_EPSILON
        )


# Latest + previous snapshot per product, with the product metadata we need to
# match alert rules and to build a readable message. Same window pattern as
# api/services/listings.py.
_CHANGES_SQL = """
    WITH ranked AS (
        SELECT s.product_id, s.observed_at, s.price_eur, s.available,
               p.title, p.shop, p.url, p.game, p.language, p.set_code,
               p.kind, p.catalog_id,
               ROW_NUMBER() OVER (PARTITION BY s.product_id
                                  ORDER BY s.observed_at DESC) AS rn
        FROM snapshots s JOIN products p ON p.id = s.product_id
    )
    SELECT a.product_id, a.title, a.shop, a.url, a.game, a.language,
           a.set_code, a.kind, a.catalog_id, a.observed_at,
           a.price_eur AS price_now, b.price_eur AS price_prev,
           a.available AS avail_now, b.available AS avail_prev
    FROM ranked a
    LEFT JOIN ranked b ON b.product_id = a.product_id AND b.rn = 2
    WHERE a.rn = 1
"""


def detect_changes(db: Session) -> list[_Change]:
    """Return the products whose latest snapshot is a restock or a price drop."""
    rows = db.execute(text(_CHANGES_SQL)).mappings().all()
    changes: list[_Change] = []
    for r in rows:
        c = _Change(
            product_id=r["product_id"],
            title=r["title"],
            shop=r["shop"],
            url=r["url"],
            game=r["game"],
            language=r["language"],
            set_code=r["set_code"],
            kind=r["kind"],
            catalog_id=r["catalog_id"],
            observed_at=str(r["observed_at"]),
            price_now=r["price_now"],
            price_prev=r["price_prev"],
            avail_now=r["avail_now"],
            avail_prev=r["avail_prev"],
        )
        if c.is_restock or c.is_price_drop:
            changes.append(c)
    return changes


def _config_matches_product(cfg: AlertConfig, change: _Change, db: Session) -> bool:
    """Does this alert rule's scope cover the changed product?"""
    scope = cfg.scope_type
    if scope == "product":
        return cfg.product_id == change.product_id
    if scope == "catalog":
        return cfg.catalog_id is not None and cfg.catalog_id == change.catalog_id
    if scope == "set":
        if cfg.set_code != change.set_code:
            return False
        if cfg.game and cfg.game != change.game:
            return False
        if cfg.language and cfg.language != change.language:
            return False
        return True
    if scope == "favorites":
        # The product is a favorite of the rule's owner — directly (product_id)
        # or via its catalog (catalog_id).
        q = db.query(Favorite.id).filter(Favorite.user_id == cfg.user_id)
        if change.catalog_id is not None:
            q = q.filter(
                (Favorite.product_id == change.product_id)
                | (Favorite.catalog_id == change.catalog_id)
            )
        else:
            q = q.filter(Favorite.product_id == change.product_id)
        return db.query(q.exists()).scalar()
    return False


def _config_wants_event(cfg: AlertConfig, event_type: str, price_now: Optional[float]) -> bool:
    """Honour the rule's alert_type filter and (for price drops) its threshold."""
    if cfg.alert_type not in ("any", event_type):
        return False
    if event_type == "price_drop" and cfg.price_threshold is not None:
        if price_now is None or price_now > cfg.price_threshold:
            return False
    return True


def _already_sent(db: Session, cfg: AlertConfig, change: _Change, event_type: str) -> bool:
    """Anti-doublon: have we already recorded this exact event for this rule?"""
    return db.query(
        db.query(AlertEvent.id)
        .filter(
            AlertEvent.alert_config_id == cfg.id,
            AlertEvent.product_id == change.product_id,
            AlertEvent.event_type == event_type,
            AlertEvent.trigger_observed_at == change.observed_at,
        )
        .exists()
    ).scalar()


_EVENT_LABEL_FR = {"restock": "De retour en stock", "price_drop": "Baisse de prix"}


def _build_message(change: _Change, event_type: str) -> tuple[str, str]:
    """French (subject, body) for a notification."""
    label = _EVENT_LABEL_FR[event_type]
    set_part = f"[{change.set_code}]" if change.set_code else ""
    subject = f"TCGWatch — {label} : {change.title[:80]}"

    lines = [
        f"{label}",
        "",
        f"Produit : {change.title}",
    ]
    if set_part:
        lines.append(f"Set     : {change.set_code}")
    lines.append(f"Boutique: {change.shop}")

    if event_type == "price_drop" and change.price_prev is not None and change.price_now is not None:
        lines.append(
            f"Prix    : {change.price_prev:.2f} € → {change.price_now:.2f} € "
            f"({change.price_now - change.price_prev:+.2f} €)"
        )
    elif change.price_now is not None:
        lines.append(f"Prix    : {change.price_now:.2f} €")

    lines.append("")
    lines.append(f"Lien    : {change.url}")
    return subject, "\n".join(lines)


def _process_event(db: Session, cfg: AlertConfig, change: _Change, event_type: str) -> bool:
    """Send (if not already sent) one event for one rule. Returns True if sent now."""
    if not _config_wants_event(cfg, event_type, change.price_now):
        return False
    if _already_sent(db, cfg, change, event_type):
        return False

    subject, body = _build_message(change, event_type)
    try:
        ok, detail = send_notification(
            channel=cfg.channel,
            destination=cfg.destination,
            subject=subject,
            message=body,
        )
    except Exception as exc:  # noqa: BLE001 — never let one send kill the batch
        ok, detail = False, f"exception: {exc}"
        logger.exception(
            "Notification raised for config=%s product=%s", cfg.id, change.product_id
        )

    db.add(
        AlertEvent(
            alert_config_id=cfg.id,
            product_id=change.product_id,
            event_type=event_type,
            trigger_observed_at=change.observed_at,
            price_eur=change.price_now,
            channel=cfg.channel,
            sent_ok=bool(ok),
            error=None if ok else (detail or "")[:512],
        )
    )
    db.commit()
    logger.info(
        "Alert %s for product=%s -> config=%s (%s/%s): ok=%s %s",
        event_type, change.product_id, cfg.id, cfg.channel, cfg.scope_type, ok, detail,
    )
    return ok


def run_alerting() -> dict:
    """Detect changes, dispatch matching alerts, return a small summary dict."""
    db = SessionLocal()
    summary = {"changes": 0, "restocks": 0, "price_drops": 0, "sent": 0, "skipped": 0}
    try:
        changes = detect_changes(db)
        summary["changes"] = len(changes)
        summary["restocks"] = sum(1 for c in changes if c.is_restock)
        summary["price_drops"] = sum(1 for c in changes if c.is_price_drop)
        if not changes:
            logger.info("No restock/price-drop changes detected.")
            return summary

        # Load active rules once; match each in memory (rule counts are small).
        configs = db.query(AlertConfig).filter(AlertConfig.active.is_(True)).all()
        logger.info(
            "Detected %d change(s); evaluating against %d active alert rule(s).",
            len(changes), len(configs),
        )

        for change in changes:
            event_types = []
            if change.is_restock:
                event_types.append("restock")
            if change.is_price_drop:
                event_types.append("price_drop")

            for cfg in configs:
                if not _config_matches_product(cfg, change, db):
                    continue
                for event_type in event_types:
                    if _process_event(db, cfg, change, event_type):
                        summary["sent"] += 1
                    else:
                        summary["skipped"] += 1
        return summary
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    result = run_alerting()
    print("Alerting summary:", result)
