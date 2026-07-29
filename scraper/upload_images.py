"""Upload every local image under images/ to Cloudflare R2.

Walks `images/` recursively and uploads each file via
`api.services.r2.upload_file`. The R2 object key mirrors the file's path
*relative to* images/ (POSIX separators), optionally under a `--prefix`, so the
bucket layout stays readable and stable (e.g. `Pokemon/Image_Serie/foo.png`).

Idempotent: an object that already exists in R2 is skipped unless `--force`.

When R2 is not configured (no R2_* env / boto3 missing), the helper runs in
dry-run mode automatically: nothing is uploaded, every file is logged as "would
upload", and the summary still reflects what *would* happen. `--dry-run` forces
that behaviour even when R2 is configured.

Run:  python -m scraper.upload_images [--force] [--dry-run] [--prefix PREFIX]
"""
import argparse
import mimetypes

from .config import IMAGES_DIR
from .timing import timed_main
from api.services import r2

# Only treat real image files as uploadable; skip stray .DS_Store / .txt / etc.
_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}


def _iter_images(root):
    """Yield (local_path, relative_posix_path) for every image file under root."""
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in _IMG_EXT:
            continue
        yield f, f.relative_to(root).as_posix()


def _make_key(rel_posix: str, prefix: str) -> str:
    """Build a clean R2 object key from the relative path and an optional prefix."""
    prefix = (prefix or "").strip().strip("/")
    return f"{prefix}/{rel_posix}" if prefix else rel_posix


def upload_all(*, force: bool = False, dry_run: bool = False, prefix: str = "") -> dict:
    """Upload all images. Returns counts {uploaded, skipped, failed, total}."""
    if not IMAGES_DIR.exists():
        print(f"images dir not found: {IMAGES_DIR}")
        return {"uploaded": 0, "skipped": 0, "failed": 0, "total": 0}

    # `r2.upload_file` already dry-runs (returns False + logs) when R2 is
    # unconfigured/boto3 missing; --dry-run lets us force that even if configured.
    configured = r2.settings.r2_enabled
    effective_dry = dry_run or not configured
    mode = "DRY-RUN" if effective_dry else "LIVE"
    print(f"=== Image upload ({mode}) root={IMAGES_DIR} prefix={prefix or '(none)'} ===")
    if effective_dry and not dry_run and not configured:
        print("R2 not configured (or boto3 missing) -> dry-run; nothing will be uploaded.")

    uploaded = skipped = failed = total = 0
    for local_path, rel in _iter_images(IMAGES_DIR):
        total += 1
        key = _make_key(rel, prefix)

        # Idempotency: skip objects already present (only meaningful when live).
        if not force and not effective_dry and r2.object_exists(key):
            skipped += 1
            print(f"  skip (exists)  {key}")
            continue

        if effective_dry:
            ctype = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
            print(f"  would upload   {key}  ({ctype})")
            uploaded += 1  # counted as "would upload" in dry-run
            continue

        ok = r2.upload_file(local_path, key)
        if ok:
            uploaded += 1
            print(f"  uploaded       {key}")
        else:
            failed += 1
            print(f"  FAILED         {key}")

    label = "would upload" if effective_dry else "uploaded"
    print("\n--- summary ---")
    print(f"  {label}: {uploaded}")
    print(f"  skipped (already in R2): {skipped}")
    if failed:
        print(f"  failed: {failed}")
    print(f"  total image files: {total}")
    return {"uploaded": uploaded, "skipped": skipped, "failed": failed, "total": total}


@timed_main
def main():
    ap = argparse.ArgumentParser(description="Upload images/ to Cloudflare R2.")
    ap.add_argument("--force", action="store_true",
                    help="Re-upload even if the object already exists in R2.")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be uploaded without uploading.")
    ap.add_argument("--prefix", default="",
                    help="Optional key prefix (e.g. 'v2'); default = none.")
    args = ap.parse_args()
    upload_all(force=args.force, dry_run=args.dry_run, prefix=args.prefix)


if __name__ == "__main__":
    main()
