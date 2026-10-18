"""Test-only helper for the few tests that import the host `main` module.

`core.database`/`core.security` refuse to import without `MONGODB_URL`/
`JWT_SECRET` (no insecure defaults), and importing `main` installs a
process-wide Mongo repository override
(`repositories.provider.set_repository_factory_override`). Without this
helper that override leaked into every later test in the session, so
unrelated scientific tests silently queried whatever database
`MONGODB_URL` pointed at.

`isolated_main_module` supplies an unreachable placeholder database and a
random throwaway secret when none is configured, and always restores the
default provider afterwards.
"""

from __future__ import annotations

import contextlib
import os
import secrets

from ..repositories import provider

_UNREACHABLE_TEST_MONGODB_URL = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200&connectTimeoutMS=200"


@contextlib.contextmanager
def isolated_main_module(monkeypatch):
    if not os.environ.get("MONGODB_URL", "").strip():
        monkeypatch.setenv("MONGODB_URL", _UNREACHABLE_TEST_MONGODB_URL)
    if not os.environ.get("JWT_SECRET", "").strip():
        monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    try:
        import main as main_module

        yield main_module
    finally:
        provider.set_repository_factory_override(None)
