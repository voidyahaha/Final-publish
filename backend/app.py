"""Compatibility entry point for `uvicorn app:app`.

The implementation lives in the package so the API, services and lifecycle
are kept in one place. Use `uvicorn app.main:app` in production.
"""

from app.main import app

__all__ = ["app"]
