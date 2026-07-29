"""Alert configuration CRUD + a manual test-send endpoint.

The detection + sending loop lives in the scraper worker (see scraper/alerting.py);
this router only manages the user's rules and lets them send a test notification.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.alert import ALERT_TYPES, CHANNELS, SCOPE_TYPES, AlertConfig
from api.routers.auth import CurrentUser, get_current_user
from api.schemas import AlertConfigCreate, AlertConfigOut
from api.services.notify import send_notification

router = APIRouter()


def _validate(body: AlertConfigCreate) -> None:
    if body.channel not in CHANNELS:
        raise HTTPException(status_code=400, detail=f"channel must be one of {CHANNELS}")
    if body.alert_type not in ALERT_TYPES:
        raise HTTPException(status_code=400, detail=f"alert_type must be one of {ALERT_TYPES}")
    if body.scope_type not in SCOPE_TYPES:
        raise HTTPException(status_code=400, detail=f"scope_type must be one of {SCOPE_TYPES}")
    if not body.destination:
        raise HTTPException(status_code=400, detail="destination is required")


@router.get("", response_model=list[AlertConfigOut])
def list_alerts(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(AlertConfig).filter(AlertConfig.user_id == user.user_id).all()
    return [AlertConfigOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", response_model=AlertConfigOut, status_code=201)
def create_alert(
    body: AlertConfigCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate(body)
    cfg = AlertConfig(user_id=user.user_id, **body.model_dump())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return AlertConfigOut.model_validate(cfg, from_attributes=True)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = (
        db.query(AlertConfig)
        .filter(AlertConfig.id == alert_id, AlertConfig.user_id == user.user_id)
        .first()
    )
    if not cfg:
        raise HTTPException(status_code=404, detail="Alert config not found")
    db.delete(cfg)
    db.commit()


@router.post("/{alert_id}/test")
def test_alert(
    alert_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = (
        db.query(AlertConfig)
        .filter(AlertConfig.id == alert_id, AlertConfig.user_id == user.user_id)
        .first()
    )
    if not cfg:
        raise HTTPException(status_code=404, detail="Alert config not found")
    ok, detail = send_notification(
        channel=cfg.channel,
        destination=cfg.destination,
        subject="TCGWatch — alerte de test",
        message="✅ Ceci est une alerte de test TCGWatch. Votre configuration fonctionne !",
    )
    return {"success": ok, "detail": detail}
