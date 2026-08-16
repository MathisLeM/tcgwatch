"""Liste d'attente publique (landing page).

Table volontairement minimale : un e-mail, d'où il vient, et quand. Pas de
mot de passe, pas de lien avec `users` — quelqu'un de la waitlist n'a pas de
compte, c'est justement l'intérêt. Le double opt-in n'est pas implémenté :
si on part sur un envoi de campagne, il faudra ajouter un `confirmed_at` et
un token de confirmation (ou déléguer à un ESP).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Stocké normalisé (strip + lowercase) — l'unicité rend l'inscription idempotente.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), default="landing")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
