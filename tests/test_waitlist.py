"""Liste d'attente publique (POST /waitlist) + export admin."""
import pytest

from api.models.user import User
from api.models.waitlist import WaitlistSignup
from api.database import SessionLocal
from api.routers.auth import hash_password


@pytest.fixture(autouse=True)
def _clean_waitlist():
    """La table est partagée par toute la session de test — on repart de zéro."""
    db = SessionLocal()
    try:
        db.query(WaitlistSignup).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def admin_client(client):
    """Client authentifié en admin (l'export est réservé aux admins)."""
    db = SessionLocal()
    try:
        email = "admin-waitlist@example.com"
        existing = db.query(User).filter(User.email == email).first()
        if not existing:
            db.add(User(email=email, hashed_password=hash_password("motdepasse1"),
                        is_admin=True))
            db.commit()
    finally:
        db.close()
    client.post("/auth/login", data={"username": email, "password": "motdepasse1"})
    yield client
    client.post("/auth/logout")


# ── Inscription ─────────────────────────────────────────────────────────────
def test_join_waitlist(client):
    r = client.post("/waitlist", json={"email": "Nouveau@Exemple.FR"})
    assert r.status_code == 201
    assert r.json()["ok"] is True

    db = SessionLocal()
    try:
        rows = db.query(WaitlistSignup).all()
        assert len(rows) == 1
        assert rows[0].email == "nouveau@exemple.fr"   # normalisé
        assert rows[0].source == "landing"
    finally:
        db.close()


def test_join_is_idempotent(client):
    first = client.post("/waitlist", json={"email": "double@exemple.fr"})
    second = client.post("/waitlist", json={"email": "  DOUBLE@exemple.fr  "})
    assert first.status_code == 201 and second.status_code == 201
    # Même message : l'endpoint ne dit pas si l'adresse était déjà connue.
    assert first.json()["message"] == second.json()["message"]

    db = SessionLocal()
    try:
        assert db.query(WaitlistSignup).count() == 1
    finally:
        db.close()


def test_join_rejects_invalid_email(client):
    assert client.post("/waitlist", json={"email": "pas-un-email"}).status_code == 422


def test_source_is_recorded_and_truncated(client):
    client.post("/waitlist", json={"email": "src@exemple.fr", "source": "x" * 80})
    db = SessionLocal()
    try:
        assert len(db.query(WaitlistSignup).one().source) == 50
    finally:
        db.close()


# ── Export admin ────────────────────────────────────────────────────────────
def test_export_requires_auth(client):
    assert client.get("/waitlist").status_code == 401
    assert client.get("/waitlist/stats").status_code == 401


def test_export_requires_admin(client):
    client.post("/auth/signup", json={"email": "simple@exemple.fr", "password": "motdepasse1"})
    assert client.get("/waitlist").status_code == 403
    client.post("/auth/logout")


def test_admin_export_and_stats(admin_client):
    admin_client.post("/waitlist", json={"email": "a@exemple.fr"})
    admin_client.post("/waitlist", json={"email": "b@exemple.fr", "source": "twitter"})

    rows = admin_client.get("/waitlist").json()
    assert {r["email"] for r in rows} == {"a@exemple.fr", "b@exemple.fr"}

    stats = admin_client.get("/waitlist/stats").json()
    assert stats["total"] == 2
    assert stats["by_source"] == {"landing": 1, "twitter": 1}
