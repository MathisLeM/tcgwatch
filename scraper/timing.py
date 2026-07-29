"""Tiny timing helpers shared by the scrapers."""
import sys
import time
import functools


def _script_name(fn):
    """Real dotted module name, even when run via `python -m scraper.x`."""
    mod = fn.__module__
    if mod == "__main__":
        spec = getattr(sys.modules.get("__main__"), "__spec__", None)
        if spec and spec.name:
            return spec.name
    return mod


def timed_main(fn):
    """Decorator for a script's main(): prints the wall-clock time it took.

    Works even if main() raises — the elapsed time is always reported."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            print(f"\n[time] {_script_name(fn)} ran in {time.perf_counter() - t0:.1f}s")
    return wrapper


def format_timings(timings):
    """timings: list of (label, n_products, seconds). Returns a summary table str."""
    lines = ["", "=" * 48, f"{'SCRAPER TIMINGS':^48}", "=" * 48,
             f"{'Platform':<16}{'Products':>9}{'Time':>11}{'Per item':>12}"]
    total_t = sum(t for _, _, t in timings)
    total_n = sum(n for _, n, _ in timings)
    for label, n, t in timings:
        per = f"{t / n:.2f}s" if n else "-"
        lines.append(f"{label:<16}{n:>9}{t:>10.1f}s{per:>12}")
    lines.append("-" * 48)
    lines.append(f"{'TOTAL':<16}{total_n:>9}{total_t:>10.1f}s")
    lines.append("=" * 48)
    return "\n".join(lines)
