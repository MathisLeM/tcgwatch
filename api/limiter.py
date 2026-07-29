"""Shared slowapi rate-limiter (mirrors Vigilyx app/limiter.py).

Import `limiter`, decorate routes with `@limiter.limit(...)`, and attach it to
the FastAPI app via `app.state.limiter` in main.py.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
