"""cardmarket price tracking (cm_tracked, cm_prices)

Revision ID: b7c1d2e3f4a5
Revises: a4decaa46555
Create Date: 2026-07-29

Adds the Cardmarket market-value price-history tables (sealed + singles),
isolated from the shop-scraped products/snapshots tables.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, None] = "a4decaa46555"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cm_tracked",
        sa.Column("id_product", sa.Integer(), nullable=False),
        sa.Column("game", sa.String(), nullable=False, server_default="optcg"),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("set_code", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("card_code", sa.String(), nullable=True),
        sa.Column("card_set", sa.String(), nullable=True),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id_product"),
    )
    op.create_index("idx_cm_tracked_cat", "cm_tracked", ["game", "category"])

    op.create_table(
        "cm_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_product", sa.Integer(), nullable=False),
        sa.Column("observed_on", sa.String(), nullable=False),
        sa.Column("avg", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("trend", sa.Float(), nullable=True),
        sa.Column("avg7", sa.Float(), nullable=True),
        sa.Column("avg30", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["id_product"], ["cm_tracked.id_product"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_product", "observed_on", name="uq_cm_price_snapshot"),
    )
    op.create_index("idx_cm_prices_product_date", "cm_prices", ["id_product", "observed_on"])


def downgrade() -> None:
    op.drop_index("idx_cm_prices_product_date", table_name="cm_prices")
    op.drop_table("cm_prices")
    op.drop_index("idx_cm_tracked_cat", table_name="cm_tracked")
    op.drop_table("cm_tracked")
