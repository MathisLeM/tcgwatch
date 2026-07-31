"""Ingest Cardmarket `price_guide_*.json` snapshots into the DB.

For every tracked product (`cm_tracked`), append/refresh its price row for the
snapshot's day (`cm_prices`). Idempotent on `(id_product, observed_on)`, so
re-ingesting a file just updates in place — never duplicates.

Runs against `DATABASE_URL` (local SQLite by default, or prod Supabase when set),
like the data migration and `manage_users`.

Run:  python -m scraper.cardmarket.ingest                    # every file in data/cardmarket/price_guide/
      python -m scraper.cardmarket.ingest price_guide_1307.json
      DATABASE_URL='postgresql://...' python -m scraper.cardmarket.ingest
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

from api.database import SessionLocal, init_db
from api.models.cardmarket import CmPrice, CmTracked

from . import FIELDS, PRICE_GUIDE_DIR


def _snapshot_date(data: dict, path: Path) -> str:
    """ISO day for a price guide: from createdAt, else the DDMM in the filename."""
    created = (data.get("createdAt") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", created):
        return created
    m = re.search(r"(\d{2})(\d{2})", path.stem)   # price_guide_DDMM
    if m:
        import datetime as dt
        return f"{dt.date.today().year}-{m.group(2)}-{m.group(1)}"
    raise SystemExit(f"Cannot determine snapshot date for {path.name}")


def _resolve_paths(arg: str | None) -> list[Path]:
    if arg:
        p = Path(arg)
        if not p.is_file():
            p = PRICE_GUIDE_DIR / arg
        if not p.is_file():
            sys.exit(f"File not found: {arg}")
        return [p]
    return [Path(f) for f in sorted(glob.glob(str(PRICE_GUIDE_DIR / "*.json")))]


def ingest(paths: list[Path]) -> dict:
    init_db()
    with SessionLocal() as db:
        tracked_ids = {t.id_product for t in db.query(CmTracked.id_product).all()}
        if not tracked_ids:
            sys.exit("No tracked products. Run `python -m scraper.cardmarket.track seed` first.")

        # (id_product, observed_on) -> CmPrice, for idempotent upsert.
        existing = {(p.id_product, p.observed_on): p
                    for p in db.query(CmPrice).all()}

        inserted = updated = snapshots = 0
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            date = _snapshot_date(data, path)
            snapshots += 1
            for e in data.get("priceGuides", []):
                idp = e.get("idProduct")
                if idp not in tracked_ids:
                    continue
                vals = {f: e.get(f) for f in FIELDS}
                row = existing.get((idp, date))
                if row is None:
                    row = CmPrice(id_product=idp, observed_on=date, **vals)
                    db.add(row)
                    existing[(idp, date)] = row
                    inserted += 1
                else:
                    if any(getattr(row, f) != vals[f] for f in FIELDS):
                        for f in FIELDS:
                            setattr(row, f, vals[f])
                        updated += 1
            print(f"  {path.name:<28} {date}")
        db.commit()

    print(f"\nSnapshots: {snapshots}  |  price rows inserted: {inserted}, updated: {updated}")
    return {"snapshots": snapshots, "inserted": inserted, "updated": updated}


def main():
    ap = argparse.ArgumentParser(description="Ingest Cardmarket price-guide snapshots.")
    ap.add_argument("file", nargs="?", help="A single price_guide file (default: all).")
    args = ap.parse_args()
    ingest(_resolve_paths(args.file))


if __name__ == "__main__":
    main()
