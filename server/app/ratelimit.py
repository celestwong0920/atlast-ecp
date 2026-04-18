"""Shared SlowAPI limiter instance.

Kept in its own module so route handlers can `from ..ratelimit import limiter`
without causing a circular import through ``app.main``. The limiter is wired
into the FastAPI app in ``main.py`` (state + exception handler + middleware).

In development / test environments the limiter is disabled so multi-agent
stress tests and local iteration don't trip the 5/hour register limit.
Production keeps it enforced. Operators can also toggle explicitly via
RATELIMIT_ENABLED=true|false.
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

_DEV_ENVS = {"development", "dev", "test", "testing", "local"}
_env = os.getenv("ENVIRONMENT", "production").strip().lower()
_explicit = os.getenv("RATELIMIT_ENABLED", "").strip().lower()

if _explicit in ("true", "1", "yes"):
    _enabled = True
elif _explicit in ("false", "0", "no"):
    _enabled = False
else:
    _enabled = _env not in _DEV_ENVS  # default: enabled everywhere except dev/test

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=_enabled,
)
