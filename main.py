"""TCGWatch API entrypoint (FastAPI).  Run: uvicorn main:app --reload

Mirrors the Vigilyx app: lifespan init_db, CORS via ALLOWED_ORIGINS, slowapi
rate limiting, health check, and a production secret-validation guard.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import _WEAK_SECRET, settings
from api.database import init_db
from api.limiter import limiter
from api.routers import (
    alerts, auth, catalog, favorites, products, retailers, sets, trends,
)
from scraper.config import IMAGES_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "0.1.0"


def _validate_production_settings() -> None:
    """Crash at startup if critical secrets are still placeholders."""
    errors = []
    if settings.SECRET_KEY == _WEAK_SECRET:
        errors.append("SECRET_KEY is still the default placeholder — set a strong random value")
    if errors:
        raise RuntimeError("\n  - ".join(["Production startup failed:"] + errors))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production:
        _validate_production_settings()
        logger.info("Production mode — strict security checks passed")
    else:
        logger.info("Development mode (ENVIRONMENT=%s)", settings.ENVIRONMENT)
    init_db()
    yield


_docs = None if settings.is_production else "/docs"

app = FastAPI(
    title="TCGWatch API",
    description="Suivi de stock de produits scellés TCG (Pokémon, One Piece…) multi-boutiques.",
    version=VERSION,
    lifespan=lifespan,
    docs_url=_docs,
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(sets.router, prefix="/sets", tags=["Sets"])
app.include_router(catalog.router, prefix="/catalog", tags=["Catalog"])
app.include_router(trends.router, prefix="/trends", tags=["Trends"])
app.include_router(retailers.router, prefix="/retailers", tags=["Retailers"])
app.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])

# Reference images (block / set logos) served for the frontend catalogue. Paths
# returned by /sets/blocks are root-relative ("images/Pokemon/...") so the URL is
# simply `${API}/images/Pokemon/...`. In prod these live on Cloudflare R2 instead.
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": VERSION}
