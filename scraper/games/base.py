"""Shared helpers used by per-game modules."""
from urllib.parse import urlparse


def slug(url: str) -> str:
    """Last path segment of a URL, lowercased, words separated by spaces."""
    if not isinstance(url, str):
        return ""
    try:
        last = urlparse(url).path.rstrip("/").split("/")[-1]
        return last.lower().replace("-", " ").replace("_", " ").replace(".html", "")
    except Exception:
        return ""


def slug_last(url: str) -> str:
    """Last path segment, lowercased, hyphens kept, '.html' stripped."""
    if not isinstance(url, str):
        return ""
    try:
        return urlparse(url).path.rstrip("/").split("/")[-1].lower().replace(".html", "")
    except Exception:
        return ""


def blob(title: str, url: str = "") -> str:
    """Searchable text = title + url slug."""
    return f"{title or ''} {slug(url)}".strip()
