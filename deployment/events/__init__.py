"""
deployment/events/__init__.py
============================
Macroeconomic Event Data Acquisition, Normalization, Deduplication, and Persistence Package.
Supports authoritative historical backfills and daily incremental collections.
"""

from .models import MacroEvent
from .normalization import normalize_event
from .deduplication import EventDeduplicator
from .storage import EventStorage

__all__ = [
    "MacroEvent",
    "normalize_event",
    "EventDeduplicator",
    "EventStorage",
]

