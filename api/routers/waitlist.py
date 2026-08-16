"""Liste d'attente publique (formulaire de la landing).

`POST /waitlist` est le **seul endpoint ouvert sans authentification** avec
`/auth/login`, d'où deux précautions :
  - rate limit slowapi (une IP ne peut pas remplir la table),
  - réponse identique que l'e-mail soit nouveau ou déjà connu, pour ne pas
    permettre de tester si une adresse est inscrite.

`GET /waitlist` (export) et `GET /waitlist/stats` sont réservés aux admins
(`users.is_admin`) — c'est de la donnée personnelle.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.database import get_db
from api.limiter import limiter
from api.models.waitlist import WaitlistSignup
from api.routers.auth import CurrentUser, get_current_user
from api.schemas import WaitlistCreate, WaitlistJoined, WaitlistOut

router = APIRouter()
logger = logging.getLogger(__name__)

_JOINED = "Merci ! On vous prévient dès l'ouverture."


def _require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé aux admins")
    return current_user


@router.post("", response_model=WaitlistJoined, status_code=201)
@limiter.limit("5/minute")
def join_waitlist(
    request: Request,
    body: WaitlistCreate,
    db: Session = Depends(get_db),
):
    """Inscrit un e-mail. Idempotent : une adresse déjà présente renvoie le même
    message de succès sans créer de doublon."""
    email = body.email.strip().lower()
    source = (body.source or "landing").strip()[:50]

    signup = WaitlistSignup(email=email, source=source)
    db.add(signup)
    try:
        db.commit()
    except IntegrityError:
        # Déjà inscrit — course possible entre deux requêtes, on retombe dessus ici.
        db.rollback()
        return WaitlistJoined(message=_JOINED)

    logger.info("waitlist: nouvelle inscription (source=%s)", source)
    return WaitlistJoined(message=_JOINED)


@router.get("", response_model=list[WaitlistOut])
def list_waitlist(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(_require_admin),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """Export admin, du plus récent au plus ancien."""
    rows = (
        db.query(WaitlistSignup)
        .order_by(WaitlistSignup.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        WaitlistOut(id=r.id, email=r.email, source=r.source, created_at=r.created_at)
        for r in rows
    ]


@router.get("/stats")
def waitlist_stats(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(_require_admin),
):
    """Compteur global + répartition par source."""
    total = db.query(func.count(WaitlistSignup.id)).scalar() or 0
    by_source = dict(
        db.query(WaitlistSignup.source, func.count(WaitlistSignup.id))
        .group_by(WaitlistSignup.source)
        .all()
    )
    return {"total": total, "by_source": by_source}
