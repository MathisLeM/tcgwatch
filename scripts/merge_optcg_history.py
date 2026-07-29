"""Merge the snapshot history from the legacy OPTCG_Scrapper DB into the current
TCG_Scrapper DB, non-destructively, to get the complete MAJ history.

Unlike `scraper.migrate_from_optcg` (which DELETEs + replaces), this MERGES:
  - products are matched on the stable key (platform, shop, platform_pid);
  - products absent from the target are re-created (language='fr', new ids);
  - snapshots are inserted only when (product_id, observed_at) isn't already
    present, so the merge is idempotent (safe to re-run).

A timestamped backup of the target DB is written before any change.

Run:
    python scripts/merge_optcg_history.py            # apply
    python scripts/merge_optcg_history.py --dry-run  # report only
    python scripts/merge_optcg_history.py --src "C:\\path\\to\\old.sqlite"
"""
import argparse
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "tcg_stock.sqlite"
DEFAULT_SRC = Path(r"C:\Users\mathi\OPTCG_Scrapper\data\tcg_stock.sqlite")
BACKUP_DIR = ROOT / "data" / "backups"


def merge(src: Path, dry_run: bool):
    if not src.exists():
        raise SystemExit(f"Source DB not found: {src}")
    if not TARGET.exists():
        raise SystemExit(f"Target DB not found: {TARGET}")

    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup = BACKUP_DIR / f"tcg_stock_{stamp}.sqlite"
        shutil.copy2(TARGET, backup)
        print(f"Backup -> {backup}")

    tgt = sqlite3.connect(TARGET)
    tgt.row_factory = sqlite3.Row
    old = sqlite3.connect(src)
    old.row_factory = sqlite3.Row

    # target product key -> id
    key_to_id = {(r["platform"], r["shop"], r["platform_pid"]): r["id"]
                 for r in tgt.execute("SELECT id, platform, shop, platform_pid FROM products")}
    # existing snapshot identity (product_id, observed_at)
    have_snap = set()
    for r in tgt.execute("SELECT product_id, observed_at FROM snapshots"):
        have_snap.add((r["product_id"], r["observed_at"]))

    old_products = old.execute(
        "SELECT id, platform, shop, platform_pid, game, set_code, title, url, first_seen_at "
        "FROM products").fetchall()

    # map old product id -> target id (creating missing products)
    o2n = {}
    created = 0
    cur = tgt.cursor()
    for p in old_products:
        k = (p["platform"], p["shop"], p["platform_pid"])
        if k in key_to_id:
            o2n[p["id"]] = key_to_id[k]
            continue
        created += 1
        if dry_run:
            o2n[p["id"]] = None  # placeholder; snapshots counted as "to import"
            continue
        cur.execute(
            "INSERT INTO products (platform, shop, platform_pid, game, language, "
            "set_code, title, url, first_seen_at) VALUES (?,?,?,?, 'fr', ?,?,?,?)",
            (p["platform"], p["shop"], p["platform_pid"], p["game"],
             p["set_code"] or "", p["title"] or "", p["url"] or "", p["first_seen_at"]))
        new_id = cur.lastrowid
        key_to_id[k] = new_id
        o2n[p["id"]] = new_id

    # insert missing snapshots
    rows = old.execute(
        "SELECT product_id, observed_at, price_eur, available, raw_variant_count, "
        "stock_remaining FROM snapshots").fetchall()
    to_insert = []
    skipped = unmapped = 0
    for s in rows:
        nid = o2n.get(s["product_id"])
        if nid is None:
            if dry_run:
                unmapped += 1   # belongs to a product that *would* be created
            continue
        if (nid, s["observed_at"]) in have_snap:
            skipped += 1
            continue
        to_insert.append((nid, s["observed_at"], s["price_eur"], s["available"],
                          s["raw_variant_count"], s["stock_remaining"]))
        have_snap.add((nid, s["observed_at"]))

    if not dry_run:
        cur.executemany(
            "INSERT INTO snapshots (product_id, observed_at, price_eur, available, "
            "raw_variant_count, stock_remaining) VALUES (?,?,?,?,?,?)", to_insert)
        tgt.commit()

    n_imported = len(to_insert) + (unmapped if dry_run else 0)
    print(f"{'DRY-RUN: would ' if dry_run else ''}create {created} products, "
          f"import {n_imported} snapshots "
          f"(already present, skipped: {skipped}).")
    if not dry_run:
        tp = tgt.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        ts = tgt.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        rng = tgt.execute("SELECT MIN(observed_at), MAX(observed_at) FROM snapshots").fetchone()
        print(f"Target now: {tp} products, {ts} snapshots, range {rng[0]} -> {rng[1]}")
    tgt.close()
    old.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    merge(Path(args.src), args.dry_run)
