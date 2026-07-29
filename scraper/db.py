"""SQLite schema and connection helper for the multi-TCG tracker.

Entity model (the user's "sites / collections products / site products / pictures"):
- sites        : the shops we track (one row per host).
- sets         : reference catalogue of *card sets* per game+language (from TCGdex).
- catalog      : canonical tracked SKU = (game, language, set_code, kind). "Collection product".
- products     : a *shop's listing* of a catalog item ("site product"). Stable identity.
- snapshots    : one row per scrape run per product. Price/stock history.

`language` is a first-class dimension (Pokemon is tracked in FR/EN/JA/KO/ZH);
OPTCG / Naruto rows are all 'fr'.
"""
import os
import sqlite3
from .config import DB_PATH, DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    host            TEXT PRIMARY KEY,        -- 'dracaugames.com'
    platform        TEXT NOT NULL,           -- 'shopify' | 'prestashop' | ...
    games           TEXT,                    -- csv of games carried, e.g. 'optcg,pokemon'
    active          INTEGER NOT NULL DEFAULT 1,
    first_seen_at   TEXT
);

CREATE TABLE IF NOT EXISTS sets (
    game            TEXT NOT NULL,           -- 'pokemon' | 'optcg'
    language        TEXT NOT NULL,           -- 'fr' | 'en' | 'ja' | 'ko' | 'zh'
    set_code        TEXT NOT NULL,           -- TCGdex set id, e.g. 'sv01', 'swsh09'
    name            TEXT,                    -- localised set name
    abbreviation    TEXT,                    -- official 3-letter code, e.g. 'OBF','CRI','PRE'
    series          TEXT,                    -- 'sv' | 'swsh' | ...
    release_date    TEXT,                    -- ISO date
    logo_url        TEXT,
    symbol_url      TEXT,
    card_count      INTEGER,
    PRIMARY KEY (game, language, set_code)
);

CREATE TABLE IF NOT EXISTS catalog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game            TEXT NOT NULL,
    language        TEXT NOT NULL,
    set_code        TEXT NOT NULL,
    kind            TEXT NOT NULL,           -- 'display' | 'etb' | 'booster' | 'case' | ...
    display_name    TEXT,
    image_path      TEXT,
    UNIQUE(game, language, set_code, kind)
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,           -- 'shopify' | 'prestashop' | 'woocommerce' | ...
    shop            TEXT NOT NULL,           -- host (e.g. 'dracaugames.com')
    platform_pid    TEXT NOT NULL,           -- product ID on that platform
    game            TEXT NOT NULL,           -- 'optcg' | 'naruto_mythos' | 'pokemon'
    language        TEXT NOT NULL DEFAULT 'fr',
    set_code        TEXT NOT NULL,           -- primary set 'OP09' | 'sv01' | etc.
    set_codes       TEXT,                    -- all sets for multi-set lots, ';'-joined
    series          TEXT,                    -- block/series id (e.g. 'sv','swsh','me')
    kind            TEXT,                    -- classified product kind (nullable)
    catalog_id      INTEGER REFERENCES catalog(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,           -- ISO date of first observation
    UNIQUE(platform, shop, platform_pid)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    observed_at     TEXT NOT NULL,           -- ISO timestamp
    price_eur       REAL,                    -- cheapest variant price
    available       INTEGER,                 -- 0/1/NULL (unknown)
    raw_variant_count INTEGER,
    stock_remaining INTEGER                  -- exact count when shop exposes it
);

CREATE INDEX IF NOT EXISTS idx_snapshots_product_time
    ON snapshots(product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_products_game_lang_set
    ON products(game, language, set_code);
CREATE INDEX IF NOT EXISTS idx_sets_game_lang
    ON sets(game, language);
"""


def game_filter_sql(games):
    """Return (sql_fragment, params) to append to a products query, e.g.
    " AND game IN (?,?)". `games` is None/empty (no filter) or a list of game ids."""
    if not games:
        return "", []
    return " AND game IN (%s)" % ",".join("?" * len(games)), list(games)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
# By default the scraper writes to the local SQLite file (DB_PATH). When
# DATABASE_URL points at a non-sqlite backend (Postgres in prod), we route every
# write/read through SQLAlchemy's engine via a thin compatibility wrapper so the
# 8 platform fetchers keep working unchanged (they speak the sqlite3 API:
# `?` placeholders, `sqlite3.Row` access, executemany/executescript, and the
# `with connect() as conn:` commit-on-exit idiom).

def _database_url() -> str | None:
    """Return the active DATABASE_URL, or None to fall back to local SQLite.

    Reads the process env first, then the API settings (which also load `.env`),
    so the scraper and the API always agree on which backend is in use.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        from api.config import settings
        # The settings default is the local SQLite file; treat that as "no PG".
        if settings.DATABASE_URL and not settings.DATABASE_URL.startswith("sqlite"):
            return settings.DATABASE_URL
    except Exception:
        pass
    return None


def _use_postgres() -> bool:
    url = _database_url()
    return bool(url) and not url.startswith("sqlite")


class _PgRow(dict):
    """Mimics sqlite3.Row: supports both row["col"] and row[index] access."""

    def __init__(self, mapping, order):
        super().__init__(mapping)
        self._order = order  # column names in SELECT order

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._order[key])
        return super().__getitem__(key)


class _PgCursor:
    """sqlite3.Cursor-ish view over a SQLAlchemy CursorResult."""

    def __init__(self, result):
        self._result = result
        self._keys = list(result.keys()) if result.returns_rows else []
        self.lastrowid = None
        try:
            self.rowcount = result.rowcount
        except Exception:
            self.rowcount = -1

    def _wrap(self, row):
        return _PgRow(row._mapping, self._keys)

    def fetchone(self):
        row = self._result.fetchone()
        return self._wrap(row) if row is not None else None

    def fetchall(self):
        return [self._wrap(r) for r in self._result.fetchall()]

    def __iter__(self):
        for r in self._result:
            yield self._wrap(r)


def _translate_sql(sql: str) -> str:
    """Translate the sqlite-only bits of a statement to portable Postgres SQL.

    The fetchers only need `?` -> `%s` (psycopg positional placeholders); they
    already use the portable `INSERT ... ON CONFLICT (...) DO UPDATE/NOTHING`
    upsert syntax, which both SQLite (3.24+) and Postgres (9.5+) understand.
    SQLite-only DDL (AUTOINCREMENT/PRAGMA) lives in SCHEMA, which is never run on
    Postgres (Alembic owns that schema).
    """
    return sql.replace("?", "%s")


class _PgConnection:
    """Wraps a SQLAlchemy connection to look like a sqlite3.Connection.

    Supports the exact subset the fetchers use. Commits on clean `with` exit,
    rolls back on exception — matching sqlite3's connection context manager.
    """

    def __init__(self, sa_conn):
        self._conn = sa_conn
        self._begun = False

    # -- helpers --------------------------------------------------------------
    def _begin(self):
        if not self._begun:
            self._tx = self._conn.begin()
            self._begun = True

    def _exec(self, sql, params=None):
        self._begin()
        translated = _translate_sql(sql)
        # exec_driver_sql passes params straight to the DBAPI (%s style).
        if params is None:
            return self._conn.exec_driver_sql(translated)
        return self._conn.exec_driver_sql(translated, tuple(params))

    # -- sqlite3.Connection-compatible surface --------------------------------
    def execute(self, sql, params=None):
        return _PgCursor(self._exec(sql, params))

    def executemany(self, sql, seq_of_params):
        self._begin()
        seq = [tuple(p) for p in seq_of_params]
        if not seq:
            return _PgCursor(self._conn.exec_driver_sql("SELECT 1"))
        result = self._conn.exec_driver_sql(_translate_sql(sql), seq)
        return _PgCursor(result)

    def executescript(self, script):
        # Only used by init_db()/SCHEMA, which we don't run on Postgres.
        raise NotImplementedError(
            "executescript is SQLite-only; Postgres schema is managed by Alembic."
        )

    def commit(self):
        if self._begun:
            self._tx.commit()
            self._begun = False

    def rollback(self):
        if self._begun:
            self._tx.rollback()
            self._begun = False

    def close(self):
        try:
            if self._begun:
                self._tx.commit()
                self._begun = False
        finally:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self._conn.close()
        return False


def _pg_connect():
    """Open a raw SQLAlchemy connection via the API engine (shared config)."""
    from api.database import engine
    return _PgConnection(engine.connect())


def connect():
    """Return a DB connection. SQLite by default; Postgres when DATABASE_URL set.

    The returned object exposes the sqlite3.Connection methods the fetchers use,
    so callers don't need to know which backend is active.
    """
    if _use_postgres():
        return _pg_connect()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    # On Postgres the schema is owned by Alembic (see api/database.py); nothing
    # to create here. SQLite keeps the original create-and-migrate behaviour.
    if _use_postgres():
        from api.database import init_db as api_init_db
        api_init_db()
        return
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Add columns introduced after the first DBs were created.
        pcols = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
        if "series" not in pcols:
            conn.execute("ALTER TABLE products ADD COLUMN series TEXT")
        if "set_codes" not in pcols:
            conn.execute("ALTER TABLE products ADD COLUMN set_codes TEXT")
        scols = {r["name"] for r in conn.execute("PRAGMA table_info(sets)")}
        if "abbreviation" not in scols:
            conn.execute("ALTER TABLE sets ADD COLUMN abbreviation TEXT")
        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
