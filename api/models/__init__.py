"""SQLAlchemy models.

Importing this package registers every model on `Base.metadata` so that
`create_all` (dev) and Alembic autogenerate (prod) see the full schema.
"""
from api.models.catalog import Catalog, Product, Set, Site, Snapshot  # noqa: F401
from api.models.user import User  # noqa: F401
from api.models.favorite import Favorite  # noqa: F401
from api.models.alert import AlertConfig, AlertEvent  # noqa: F401
from api.models.cardmarket import CmPrice, CmTracked  # noqa: F401

__all__ = [
    "Site",
    "Set",
    "Catalog",
    "Product",
    "Snapshot",
    "User",
    "Favorite",
    "AlertConfig",
    "AlertEvent",
    "CmTracked",
    "CmPrice",
]
