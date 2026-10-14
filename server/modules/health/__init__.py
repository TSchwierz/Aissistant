"""Health Scale Hub — mounted into the unified Personal AIssistent process.

Phone API paths preserved at ``/api/...`` (no prefix change).
Dashboard at ``/``; static assets at ``/static``.
"""

from server.modules.health.router import mount_health, startup_health

__all__ = ["mount_health", "startup_health"]
