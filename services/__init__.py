"""
Service package for bot helper services.

Currently used for statistics and the monitoring web UI.
"""
# pyright: reportUnsupportedDunderAll=false

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "stats_collector",
    "stats_events",
    "stats_service",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        return import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
