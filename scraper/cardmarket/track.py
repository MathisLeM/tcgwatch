"""Manage the Cardmarket products/cards we track the price of.

  python -m scraper.cardmarket.track seed                      # load the bundled tracked lists
  python -m scraper.cardmarket.track add-single <cardmarket-url>
  python -m scraper.cardmarket.track add-sealed <idProduct> <code> <kind> <name...>
  python -m scraper.cardmarket.track list

Writes to `cm_tracked` via DATABASE_URL. After adding, run
`python -m scraper.cardmarket.ingest` to (back)fill the price history.
"""
import argparse
import json
import os
import sys

from api.database import SessionLocal, init_db
from api.models.cardmarket import CmTracked

from ..config import ROOT
from . import TRACKED_PRODUCTS, TRACKED_SINGLES

_KIND_TO_IMG = {"Booster Box": "display", "Sleeved Pack Case": "case"}


def _rel(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return os.path.relpath(path, ROOT).replace("\\", "/")
    except ValueError:
        return path.replace("\\", "/")


def _sealed_image(code: str, kind: str) -> str | None:
    from scraper.games import optcg
    mapped = _KIND_TO_IMG.get(kind)
    return _rel(optcg.kind_image(code, mapped)) if mapped else None


def _upsert(db, **fields) -> bool:
    """Upsert a cm_tracked row by id_product. Returns True if newly created."""
    row = db.get(CmTracked, fields["id_product"])
    if row is None:
        db.add(CmTracked(**fields))
        return True
    for k, v in fields.items():
        setattr(row, k, v)
    return False


def cmd_seed(_args):
    init_db()
    sealed = json.loads(TRACKED_PRODUCTS.read_text(encoding="utf-8")) if TRACKED_PRODUCTS.exists() else []
    singles = json.loads(TRACKED_SINGLES.read_text(encoding="utf-8")) if TRACKED_SINGLES.exists() else []
    created = 0
    with SessionLocal() as db:
        for p in sealed:
            created += _upsert(
                db, id_product=p["idProduct"], game="optcg", category="sealed",
                name=p["name"], set_code=p["code"], kind=p["kind"],
                image_path=_sealed_image(p["code"], p["kind"]),
            )
        for s in singles:
            created += _upsert(
                db, id_product=s["idProduct"], game="optcg", category="single",
                name=s["name"], card_code=s.get("code"), card_set=s.get("set"),
            )
        db.commit()
    print(f"Seeded {len(sealed)} sealed + {len(singles)} singles "
          f"({created} new). Run `python -m scraper.cardmarket.ingest` to fill history.")


def cmd_add_single(args):
    from .resolver import SingleResolver
    res = SingleResolver().resolve(args.url)
    if not res.ok:
        sys.exit(f"Could not resolve a single from: {args.url}\n"
                 f"(code={res.code}, expansion={res.expansion_slug})")
    b = res.best
    init_db()
    with SessionLocal() as db:
        new = _upsert(db, id_product=b.idProduct, game="optcg", category="single",
                      name=b.name, card_code=res.code, card_set=b.set_name)
        db.commit()
    print(f"{'Added' if new else 'Updated'} single: {b.name}  (idProduct={b.idProduct}, {b.set_name})")
    # Keep the bundled list in sync so a future `seed` re-adds it.
    _append_json(TRACKED_SINGLES, {"idProduct": b.idProduct, "code": res.code,
                                   "name": b.name, "set": b.set_name, "url": args.url})
    print("Run `python -m scraper.cardmarket.ingest` to backfill its price history.")


def cmd_add_sealed(args):
    init_db()
    name = " ".join(args.name)
    with SessionLocal() as db:
        new = _upsert(db, id_product=args.id_product, game="optcg", category="sealed",
                      name=name, set_code=args.code, kind=args.kind,
                      image_path=_sealed_image(args.code, args.kind))
        db.commit()
    print(f"{'Added' if new else 'Updated'} sealed: {name} ({args.code} {args.kind})")
    print("Run `python -m scraper.cardmarket.ingest` to backfill its price history.")


def cmd_list(_args):
    with SessionLocal() as db:
        rows = db.query(CmTracked).order_by(CmTracked.category, CmTracked.set_code,
                                            CmTracked.card_code).all()
    if not rows:
        print("No tracked products. Run `seed` first.")
        return
    for cat in ("sealed", "single"):
        items = [r for r in rows if r.category == cat]
        if not items:
            continue
        print(f"\n=== {cat} ({len(items)}) ===")
        for r in items:
            code = r.set_code or r.card_code or "?"
            extra = r.kind or r.card_set or ""
            print(f"  {r.id_product:>8}  {code:<10} {extra:<26} {r.name}")


def _append_json(path, entry: dict):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not any(e.get("idProduct") == entry["idProduct"] for e in data):
        data.append(entry)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Manage tracked Cardmarket products/cards.")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Load the bundled tracked lists into cm_tracked").set_defaults(func=cmd_seed)

    p = sub.add_parser("add-single", help="Add a single card by Cardmarket URL")
    p.add_argument("url")
    p.set_defaults(func=cmd_add_single)

    p = sub.add_parser("add-sealed", help="Add a sealed product by idProduct")
    p.add_argument("id_product", type=int)
    p.add_argument("code")
    p.add_argument("kind")
    p.add_argument("name", nargs="+")
    p.set_defaults(func=cmd_add_sealed)

    sub.add_parser("list", help="List tracked products").set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
