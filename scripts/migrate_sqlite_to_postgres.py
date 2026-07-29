"""One-shot data migration: local SQLite -> target DB (Supabase Postgres).

Usage (run AFTER `alembic upgrade head` has created the schema on the target):

    # target comes from DATABASE_URL (.env) — must be the Postgres URL
    python -m scripts.migrate_sqlite_to_postgres
    python -m scripts.migrate_sqlite_to_postgres --source data/tcg_stock.sqlite
    python -m scripts.migrate_sqlite_to_postgres --dry-run

Copies the scraper's reference + operational tables. User/favorite/alert tables
start empty in production, so they are not copied.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

from sqlalchemy import create_engine, insert, text

from api.config import settings
from api.database import Base
import api.models  # noqa: F401  (populate metadata)

# Parent-before-child order so foreign keys resolve.
TABLE_ORDER = ["sites", "sets", "catalog", "products", "snapshots"]
# Tables whose integer PK is a Postgres sequence we must re-sync after explicit-id inserts.
SEQUENCE_TABLES = ["catalog", "products", "snapshots"]
BATCH = 1000


def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/tcg_stock.sqlite", help="source SQLite path")
    ap.add_argument("--dry-run", action="store_true", help="count rows only, write nothing")
    ap.add_argument("--force", action="store_true", help="allow a SQLite target")
    args = ap.parse_args()

    target_url = settings.DATABASE_URL
    is_pg = target_url.startswith("postgresql")
    if not is_pg and not args.force:
        print(f"Target DATABASE_URL is not Postgres ({target_url[:30]}…).\n"
              f"Set DATABASE_URL to your Supabase URL, or pass --force to target SQLite.",
              file=sys.stderr)
        return 2

    src = sqlite3.connect(args.source)
    metadata_tables = Base.metadata.tables
    engine = create_engine(target_url)

    total = 0
    with engine.begin() as conn:
        for table in TABLE_ORDER:
            rows = _rows(src, table)
            print(f"{table:>10}: {len(rows)} rows", end="")
            if args.dry_run or not rows:
                print(" (skipped)" if args.dry_run else "")
                continue
            tbl = metadata_tables[table]
            # Keep only columns that exist on the target table.
            cols = set(tbl.columns.keys())
            payload = [{k: v for k, v in r.items() if k in cols} for r in rows]
            for i in range(0, len(payload), BATCH):
                conn.execute(insert(tbl), payload[i:i + BATCH])
            total += len(payload)
            print(" -> inserted")

        # Re-sync Postgres sequences so future autoincrement ids don't collide.
        if is_pg and not args.dry_run:
            for table in SEQUENCE_TABLES:
                conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                ))
            print("Postgres sequences re-synced.")

    src.close()
    print(f"\nDone. {total} rows migrated to {target_url[:30]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
