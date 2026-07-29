"""One-off migration: import the live OPTCG_Scrapper DB into the new schema.

Copies `products` (tagging language='fr') and `snapshots` (preserving ids so the
FK links stay intact), then seeds the `sites` table from the imported shops.

Run:  python -m scraper.migrate_from_optcg
      python -m scraper.migrate_from_optcg --src "C:\\path\\to\\tcg_stock.sqlite" --force
"""
import argparse
import sqlite3
from pathlib import Path
from .db import connect, init_db

DEFAULT_SRC = Path(r"C:\Users\mathi\OPTCG_Scrapper\data\tcg_stock.sqlite")


def migrate(src: Path, force: bool):
    if not src.exists():
        raise SystemExit(f"Source DB not found: {src}")
    init_db()
    with connect() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if existing and not force:
            raise SystemExit(f"Target already has {existing} products. Re-run with --force to replace.")
        if existing and force:
            conn.execute("DELETE FROM snapshots")
            conn.execute("DELETE FROM products")
            conn.commit()

        old = sqlite3.connect(src)
        old.row_factory = sqlite3.Row

        prods = old.execute("""
            SELECT id, platform, shop, platform_pid, game, set_code,
                   title, url, first_seen_at FROM products
        """).fetchall()
        conn.executemany("""
            INSERT INTO products (id, platform, shop, platform_pid, game, language,
                                  set_code, title, url, first_seen_at)
            VALUES (?, ?, ?, ?, ?, 'fr', ?, ?, ?, ?)
        """, [(p["id"], p["platform"], p["shop"], p["platform_pid"], p["game"],
               p["set_code"], p["title"], p["url"], p["first_seen_at"]) for p in prods])

        snaps = old.execute("""
            SELECT product_id, observed_at, price_eur, available,
                   raw_variant_count, stock_remaining FROM snapshots
        """).fetchall()
        conn.executemany("""
            INSERT INTO snapshots (product_id, observed_at, price_eur, available,
                                   raw_variant_count, stock_remaining)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(s["product_id"], s["observed_at"], s["price_eur"], s["available"],
               s["raw_variant_count"], s["stock_remaining"]) for s in snaps])

        # Seed sites from imported products.
        sites = conn.execute("""
            SELECT shop AS host, platform,
                   GROUP_CONCAT(DISTINCT game) AS games,
                   MIN(first_seen_at) AS first_seen_at
            FROM products GROUP BY shop, platform
        """).fetchall()
        conn.executemany("""
            INSERT INTO sites (host, platform, games, active, first_seen_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(host) DO UPDATE SET platform=excluded.platform,
                games=excluded.games
        """, [(s["host"], s["platform"], s["games"], s["first_seen_at"]) for s in sites])

        old.close()
        conn.commit()

        n_p = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        n_s = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        n_site = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        by_game = conn.execute("SELECT game, COUNT(*) FROM products GROUP BY game").fetchall()
    print(f"Imported from {src}")
    print(f"  products : {n_p}")
    print(f"  snapshots: {n_s}")
    print(f"  sites    : {n_site}")
    for g, c in by_game:
        print(f"    {g:<14} {c}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    migrate(Path(args.src), args.force)
