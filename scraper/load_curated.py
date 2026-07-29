"""Load the 3 curated Excel files into the `products` table.

Idempotent: re-running upserts based on (platform, shop, platform_pid).
"""
import datetime as dt
import pandas as pd
from .db import connect
from .config import DATA_DIR

FILES = [
    ("shopify",     "discovered_shopify.xlsx",     "shopify_pid"),
    ("prestashop",  "discovered_prestashop.xlsx",  "product_pid"),
    ("woocommerce", "discovered_woocommerce.xlsx", "product_pid"),
    ("wix",         "discovered_wix.xlsx",         "product_pid"),
    ("powerboutique", "discovered_powerboutique.xlsx", "product_pid"),
    ("nextjs",       "discovered_nextjs.xlsx",       "product_pid"),
    ("emonsite",     "discovered_emonsite.xlsx",     "product_pid"),
    ("fantasysphere", "discovered_fantasysphere.xlsx", "product_pid"),
]


def load_file(conn, platform, fname, pid_col):
    path = DATA_DIR / fname
    if not path.exists():
        return 0, 0, 0, None
    df = pd.read_excel(path)
    today = dt.date.today().isoformat()
    inserted = updated = skipped = 0
    keys = set()  # (shop, platform_pid) for every valid row in the file
    for _, r in df.iterrows():
        pid = r.get(pid_col)
        if pd.isna(pid) or pid == "":
            skipped += 1
            continue
        set_code = (r.get("set") or "").strip() if isinstance(r.get("set"), str) else ""
        if not set_code:
            skipped += 1
            continue
        keys.add((str(r["shop"]), str(pid)))
        row = (
            platform, r["shop"], str(pid), r["game"], set_code,
            r["title"], r["url"], today,
        )
        cur = conn.execute("""
            INSERT INTO products (platform, shop, platform_pid, game, set_code,
                                  title, url, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, shop, platform_pid) DO UPDATE SET
                title    = excluded.title,
                url      = excluded.url,
                set_code = excluded.set_code,
                game     = excluded.game
        """, row)
        if cur.rowcount == 1: inserted += 1
        else: updated += 1
    return inserted, updated, skipped, keys


def prune_platform(conn, platform, keys):
    """Delete stale DB products of `platform` — but ONLY for shops that appear in
    the curated file. Shops the file doesn't mention are left untouched.

    The curated `discovered_<platform>.xlsx` is populated incrementally, one shop
    at a time (via `add_site`), so it is NOT a complete snapshot of the platform.
    Pruning every product absent from it wiped all previously-added shops on each
    `add_site` run. Scoping the prune to the file's own shops means re-discovering
    one shop only reconciles that shop's rows and never touches the others.
    Cascades to snapshots via ON DELETE CASCADE."""
    if not keys:
        return 0
    shops_in_file = {shop for shop, _pid in keys}
    existing = conn.execute(
        "SELECT id, shop, platform_pid FROM products WHERE platform = ?", (platform,)
    ).fetchall()
    stale = [r["id"] for r in existing
             if r["shop"] in shops_in_file
             and (str(r["shop"]), str(r["platform_pid"])) not in keys]
    for pid in stale:
        conn.execute("DELETE FROM products WHERE id = ?", (pid,))
    return len(stale)


def main():
    with connect() as conn:
        for platform, fname, pid_col in FILES:
            ins, upd, skp, keys = load_file(conn, platform, fname, pid_col)
            pruned = prune_platform(conn, platform, keys)
            print(f"  {platform:<14} inserted/updated={ins+upd}  skipped={skp}  pruned={pruned}")
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"\nTotal products in DB: {n}")
        by_plat = conn.execute("""
            SELECT platform, COUNT(*) FROM products GROUP BY platform ORDER BY platform
        """).fetchall()
        for p, c in by_plat:
            print(f"  {p:<12} {c}")


if __name__ == "__main__":
    main()
