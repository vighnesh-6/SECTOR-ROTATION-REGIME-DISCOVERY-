"""
deployment/events/deduplication.py
==================================
Deterministic fingerprinting, fuzzy token matching, and deduplication logic
for macroeconomic events. Ensures existing 135 records are 100% protected.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .models import MacroEvent


def tokenize(text: str) -> Set[str]:
    """Extract meaningful lowercase alphanumeric tokens."""
    tokens = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower())
    # Exclude trivial stopwords
    stopwords = {"the", "and", "for", "with", "from", "that", "this", "over", "into", "amid"}
    return set(tokens) - stopwords


class EventDeduplicator:
    """
    Tracks seen event fingerprints and prevents duplicate insertions.
    """

    def __init__(self, existing_events: Optional[List[MacroEvent]] = None):
        self.seen_fingerprints: Set[str] = set()
        self.existing_by_date: Dict[str, List[MacroEvent]] = {}

        if existing_events:
            for ev in existing_events:
                self.register(ev)

    def register(self, event: MacroEvent) -> None:
        """Register an existing event into lookup sets."""
        fp = event.fingerprint()
        self.seen_fingerprints.add(fp)
        if event.date not in self.existing_by_date:
            self.existing_by_date[event.date] = []
        self.existing_by_date[event.date].append(event)

    def is_duplicate(self, candidate: MacroEvent) -> Tuple[bool, Optional[str]]:
        """
        Check if candidate is a duplicate of any registered event.
        Returns (True, reason) if duplicate, (False, None) otherwise.
        """
        # 1. Exact canonical fingerprint check
        fp = candidate.fingerprint()
        if fp in self.seen_fingerprints:
            return True, f"Exact fingerprint match: {fp}"

        # 2. Check same-date events for fuzzy title match
        same_date_events = self.existing_by_date.get(candidate.date, [])
        cand_tokens = tokenize(candidate.title)
        if not cand_tokens:
            cand_tokens = set(re.findall(r"\w+", candidate.title.lower()))

        for existing in same_date_events:
            # Check exact title match
            if candidate.title.strip().lower() == existing.title.strip().lower():
                return True, f"Exact title match on {candidate.date}: '{existing.title}'"

            if candidate.source_id.startswith("EVT:") and candidate.source_id == existing.source_id:
                return True, "Same official release reference"

            # Different numeric values can represent distinct same-day releases.
            if set(re.findall(r"\d+", candidate.title)) != set(re.findall(r"\d+", existing.title)):
                continue

            # Check token overlap if category is identical or compatible
            if candidate.category.lower() == existing.category.lower():
                exist_tokens = tokenize(existing.title)
                if not exist_tokens:
                    exist_tokens = set(re.findall(r"\w+", existing.title.lower()))

                intersection = cand_tokens & exist_tokens
                union = cand_tokens | exist_tokens
                jaccard = len(intersection) / len(union) if union else 0.0

                if jaccard >= 0.50:  # 50% token overlap on same date and category
                    return True, f"High semantic similarity ({jaccard:.2f}) on {candidate.date} with: '{existing.title}'"

        return False, None

    def filter_unique(
        self, candidates: List[MacroEvent]
    ) -> Tuple[List[MacroEvent], List[Tuple[MacroEvent, str]]]:
        """
        Filters a list of candidate events, registering approved unique events.
        Returns:
            (unique_events, rejected_duplicates_with_reason)
        """
        unique_events: List[MacroEvent] = []
        rejected: List[Tuple[MacroEvent, str]] = []

        for cand in candidates:
            dup, reason = self.is_duplicate(cand)
            if dup:
                rejected.append((cand, reason or "Duplicate"))
            else:
                self.register(cand)
                unique_events.append(cand)

        return unique_events, rejected

