"""Pytest fixtures — isolated temp SQLite DB seeded with a little data.

DATABASE_URL is set *before* importing the app so the engine binds to the temp DB.
"""
import os
import tempfile

import pytest

# Must run before any `api.*` import (settings/engine are built at import time).
_TMP_DB = os.path.join(tempfile.gettempdir(), "tcgwatch_test.sqlite")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "test-secret-not-for-prod"
# Tests exercise the signup→login→me flow, so the public-signup gate is open here.
# The closed-signup behaviour (default in prod/alpha) is covered by its own test.
os.environ["ALLOW_PUBLIC_SIGNUP"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from api.database import Base, SessionLocal, engine  # noqa: E402
from api.limiter import limiter  # noqa: E402
from api.models.catalog import Product, Set, Site, Snapshot  # noqa: E402
from main import app  # noqa: E402

# Rate limiting is a production concern; disable it so functional tests (which
# issue many signup/login calls from the same "testclient" address) are
# deterministic and don't trip the 5/minute signup bucket.
limiter.enabled = False


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.add(Site(host="exampleshop.fr", platform="shopify", games="pokemon", active=1,
                    first_seen_at="2026-01-01"))
        db.add(Set(game="pokemon", language="fr", set_code="sv08.5", name="Étincelles Déferlantes",
                   abbreviation="PRE", series="sv"))
        p = Product(
            platform="shopify", shop="exampleshop.fr", platform_pid="111",
            game="pokemon", language="fr", set_code="sv08.5", series="sv", kind="etb",
            title="ETB Étincelles Déferlantes FR", url="https://exampleshop.fr/etb",
            first_seen_at="2026-01-01",
        )
        db.add(p)
        db.flush()
        # Previous snapshot: out of stock & pricier; latest: in stock & cheaper (a restock + price drop)
        db.add(Snapshot(product_id=p.id, observed_at="2026-06-01T10:00:00", price_eur=69.9,
                        available=0, stock_remaining=0))
        db.add(Snapshot(product_id=p.id, observed_at="2026-06-02T10:00:00", price_eur=59.9,
                        available=1, stock_remaining=4))
        # A big-chain (Micromania) product, for the retailers endpoints.
        db.add(Site(host="micromania.fr", platform="micromania", games="pokemon", active=1,
                    first_seen_at="2026-01-01"))
        mm = Product(
            platform="micromania", shop="micromania.fr", platform_pid="160611",
            game="pokemon", language="fr", set_code="sv08.5", series="sv", kind="coffret",
            title="Coffret Collection Illustration Premiers Partenaires Serie 2",
            url="https://www.micromania.fr/p/x-160611.html", first_seen_at="2026-01-01",
        )
        db.add(mm)
        db.flush()
        db.add(Snapshot(product_id=mm.id, observed_at="2026-06-02T10:00:00", price_eur=19.99,
                        available=1, stock_remaining=None))
        # An OPTCG product with NO stored kind (like prod) — exercises the
        # derive-kind-from-title path (api.services.kinds).
        db.add(Site(host="opshop.fr", platform="shopify", games="optcg", active=1,
                    first_seen_at="2026-01-01"))
        op = Product(
            platform="shopify", shop="opshop.fr", platform_pid="op10-1",
            game="optcg", language="fr", set_code="OP10", series=None, kind=None,
            title="Display One Piece Card Game OP10 : Sang Royal - Version Française",
            url="https://opshop.fr/op10-display", first_seen_at="2026-01-01",
        )
        db.add(op)
        db.flush()
        db.add(Snapshot(product_id=op.id, observed_at="2026-06-02T10:00:00", price_eur=89.9,
                        available=1, stock_remaining=2))
        # Cardmarket trend tracking: one sealed product with 2 price points (for the
        # /trends API), and one with none (for the ingestion idempotency test).
        from api.models.cardmarket import CmPrice, CmTracked
        db.add(CmTracked(id_product=768727, game="optcg", category="sealed",
                         set_code="OP09", kind="Booster Box",
                         name="Emperors in the New World Booster Box"))
        db.add(CmPrice(id_product=768727, observed_on="2026-05-01", trend=333.0, low=333.0, avg=357.0))
        db.add(CmPrice(id_product=768727, observed_on="2026-07-01", trend=431.0, low=340.0, avg=428.0))
        db.add(CmTracked(id_product=802153, game="optcg", category="sealed",
                         set_code="OP10", kind="Booster Box", name="Royal Blood Booster Box"))
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """A TestClient that has signed up (cookie jar holds the auth cookie).

    Uses a unique email per test so multiple auth tests don't collide.
    """
    import uuid
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/signup", json={"email": email, "password": "supersecret"})
    assert r.status_code == 200, r.text
    return client
