"""Pousse les données scrapées en local vers la base de prod (Supabase Postgres).

**Rejouable autant de fois qu'on veut** — contrairement à
`scripts.migrate_sqlite_to_postgres` qui fait des INSERT bruts et explose au
second passage. Ici tout passe par un UPSERT (`ON CONFLICT`) :

- `sites`, `sets`, `catalog`, `products`, `cm_tracked` : upsert intégral
  (les lignes existantes sont mises à jour, les nouvelles insérées).
- `snapshots`, `cm_prices` : séries temporelles append-only. Par défaut seules
  les lignes dont l'id dépasse le max déjà présent en cible sont envoyées
  (rapide) ; `--full` renvoie tout en upsert.

Les tables applicatives (`users`, `favorites`, `alert_configs`, `alert_events`)
vivent **uniquement** en prod et ne sont jamais touchées.

Usage typique (après un scrape local) :

    # DATABASE_URL pointe sur Supabase (.env ou variable d'environnement)
    python -m scripts.sync_to_prod --dry-run     # voir ce qui partirait
    python -m scripts.sync_to_prod               # pousser

    # ou en passant l'URL directement (pratique en one-shot) :
    python -m scripts.sync_to_prod --target "postgresql://postgres:...@db.xxx.supabase.co:5432/postgres"

Options utiles :
    --full              renvoie l'intégralité des séries temporelles
    --only products,snapshots    ne synchronise que ces tables
    --migrate           joue `alembic upgrade head` sur la cible avant de pousser
    --source <path>     autre base SQLite source
"""
from __future__ import annotations

import argparse
import io
import os
import sqlite3
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine

from api.config import settings

BATCH = 1000


@dataclass(frozen=True)
class TableSync:
    """Comment une table est synchronisée."""
    name: str
    key: tuple[str, ...]           # colonnes du ON CONFLICT
    append_only: bool = False      # série temporelle : fast-path sur max(id)
    id_col: str = "id"


# Ordre parent → enfant pour que les clés étrangères se résolvent.
TABLES: list[TableSync] = [
    TableSync("sites", ("host",)),
    TableSync("sets", ("game", "language", "set_code")),
    TableSync("catalog", ("id",)),
    TableSync("products", ("id",)),
    TableSync("snapshots", ("id",), append_only=True),
    TableSync("cm_tracked", ("id_product",)),
    TableSync("cm_prices", ("id",), append_only=True),
]

# Tables dont la PK entière est alimentée par une séquence Postgres : après des
# INSERT à id explicite il faut la recaler, sinon les futurs inserts collisionnent.
SEQUENCE_TABLES = ["catalog", "products", "snapshots", "cm_prices"]


def _upsert_stmt(engine: Engine, table, rows: list[dict], spec: TableSync):
    """INSERT ... ON CONFLICT DO UPDATE, dialecte-agnostique (Postgres ou SQLite)."""
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert

    stmt = insert(table).values(rows)
    updatable = [c for c in table.columns.keys() if c not in spec.key]
    if not updatable:
        return stmt.on_conflict_do_nothing(index_elements=list(spec.key))
    return stmt.on_conflict_do_update(
        index_elements=list(spec.key),
        set_={c: getattr(stmt.excluded, c) for c in updatable},
    )


def _source_tables(src: sqlite3.Connection) -> set[str]:
    return {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _read(src: sqlite3.Connection, table: str, where: str = "") -> list[dict]:
    src.row_factory = sqlite3.Row
    return [dict(r) for r in src.execute(f"SELECT * FROM {table} {where}")]


def _target_max_id(conn, table, id_col: str) -> int:
    return conn.execute(select(func.coalesce(func.max(table.c[id_col]), 0))).scalar_one()


def _force_utf8_stdout() -> None:
    """Console Windows en cp1252 : les flèches/accents des logs la font planter."""
    if sys.platform == "win32":
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name)
            if hasattr(stream, "buffer"):
                setattr(sys, name, io.TextIOWrapper(
                    stream.buffer, encoding="utf-8", errors="replace"))


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", default="data/tcg_stock.sqlite", help="base SQLite source")
    ap.add_argument("--target", default=None,
                    help="URL de la base cible (sinon DATABASE_URL / .env)")
    ap.add_argument("--dry-run", action="store_true", help="ne rien écrire, juste compter")
    ap.add_argument("--full", action="store_true",
                    help="renvoyer TOUTES les lignes des séries temporelles")
    ap.add_argument("--only", default=None,
                    help="liste de tables séparées par des virgules")
    ap.add_argument("--migrate", action="store_true",
                    help="jouer `alembic upgrade head` sur la cible avant de pousser")
    ap.add_argument("--force-sqlite", action="store_true",
                    help="autoriser une cible SQLite (tests)")
    args = ap.parse_args()

    # La cible : --target l'emporte sur DATABASE_URL. On la pousse aussi dans le
    # singleton settings pour qu'Alembic (migrations/env.py) vise la même base.
    target_url = args.target or settings.DATABASE_URL
    settings.DATABASE_URL = target_url
    os.environ["DATABASE_URL"] = target_url

    is_pg = target_url.startswith("postgresql")
    if not is_pg and not args.force_sqlite:
        print(f"La cible n'est pas Postgres ({target_url[:40]}…).\n"
              f"Renseigne DATABASE_URL (Supabase) ou passe --target. "
              f"--force-sqlite pour forcer.", file=sys.stderr)
        return 2

    if not os.path.exists(args.source):
        print(f"Base source introuvable : {args.source}", file=sys.stderr)
        return 2

    selected = {t.strip() for t in args.only.split(",")} if args.only else None
    specs = [s for s in TABLES if selected is None or s.name in selected]
    if selected and not specs:
        print(f"Aucune table connue dans --only={args.only}", file=sys.stderr)
        return 2

    if args.migrate and not args.dry_run:
        from alembic import command
        from alembic.config import Config
        print("→ alembic upgrade head sur la cible…")
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        command.upgrade(cfg, "head")

    # Import tardif : api.database construit son engine à partir de settings.
    from api.database import Base
    import api.models  # noqa: F401  (peuple Base.metadata)

    src = sqlite3.connect(args.source)
    available = _source_tables(src)
    engine = create_engine(target_url)

    print(f"source : {args.source}")
    print(f"cible  : {target_url.split('@')[-1] if '@' in target_url else target_url}")
    print(f"mode   : {'DRY-RUN' if args.dry_run else 'écriture'}"
          f"{' · full' if args.full else ''}\n")

    pushed_total = 0
    try:
        with engine.begin() as conn:  # tout ou rien : une transaction unique
            for spec in specs:
                table = Base.metadata.tables[spec.name]
                if spec.name not in available:
                    print(f"{spec.name:>11} : absente en local — ignorée")
                    continue

                where = ""
                if spec.append_only and not args.full:
                    high_water = _target_max_id(conn, table, spec.id_col)
                    if high_water:
                        where = f"WHERE {spec.id_col} > {high_water}"

                rows = _read(src, spec.name, where)
                suffix = " (incrémental)" if where else ""
                if not rows:
                    print(f"{spec.name:>11} : 0 nouvelle ligne{suffix}")
                    continue
                if args.dry_run:
                    print(f"{spec.name:>11} : {len(rows)} ligne(s) à pousser{suffix}")
                    pushed_total += len(rows)
                    continue

                # On ne garde que les colonnes qui existent réellement en cible.
                cols = set(table.columns.keys())
                payload = [{k: v for k, v in r.items() if k in cols} for r in rows]
                for i in range(0, len(payload), BATCH):
                    conn.execute(_upsert_stmt(engine, table, payload[i:i + BATCH], spec))
                pushed_total += len(payload)
                print(f"{spec.name:>11} : {len(payload)} ligne(s) poussée(s){suffix}")

            if is_pg and not args.dry_run:
                for name in SEQUENCE_TABLES:
                    if selected and name not in selected:
                        continue
                    conn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {name}), 1))"
                    ))
                print("\nséquences Postgres recalées.")

        # Contrôle final : les volumes source/cible doivent concorder.
        if not args.dry_run:
            print("\nvérification (source → cible) :")
            with engine.connect() as conn:
                for spec in specs:
                    if spec.name not in available:
                        continue
                    n_src = src.execute(f"SELECT COUNT(*) FROM {spec.name}").fetchone()[0]
                    n_dst = conn.execute(
                        select(func.count()).select_from(Base.metadata.tables[spec.name])
                    ).scalar_one()
                    # La cible peut légitimement en avoir plus (historique déjà
                    # poussé puis purgé en local) — on ne signale que le déficit.
                    flag = "OK" if n_dst >= n_src else "ÉCART"
                    print(f"{spec.name:>11} : {n_src} → {n_dst}   [{flag}]")
    finally:
        src.close()

    print(f"\nTerminé. {pushed_total} ligne(s) {'à pousser' if args.dry_run else 'poussées'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
