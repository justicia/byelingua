"""Shared publication policy for performance occurrences.

This module deliberately separates occurrence acquisition from the semantic
decision about whether a row belongs on the public performance calendar.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from typing import Any


VISITOR_PATTERNS = (
    r"\bguided\s+tour\b",
    r"\barchitecture\s+tour\b",
    r"\bbackstage\s+tour\b",
    r"\bbuilding\s+tour\b",
    r"\bbehind\s+the\s+scenes\s+tour\b",
    r"\bexhibition\s+tours?\b",
    r"\btea\s+and\s+tour\b",
    r"\bworkshop\s+tour\b",
    r"\bcostume\s+design\s+tour\b",
    r"\badventure\s+tour\b",
    r"\bon\s+stage\s+tour\b",
    r"\bdivine\s+divas\s+tour\b",
    r"\bmuseum\s+(?:tour|visit)\b",
    r"\bvisitor\s+(?:tour|experience)\b",
    r"\b(?:fuehrung|fuhrung)\b",
    r"\bkinder(?:fuehrung|fuhrung)\b",
    r"\bvisite\s+guidee\b",
    r"\bvisita\s+guidata\b",
    r"\bvisita\s+guiada\b",
)


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _signals(event: Any) -> tuple[str, str]:
    raw = event.raw if isinstance(getattr(event, "raw", None), dict) else {}
    title = _fold(getattr(event, "title", ""))
    metadata = _fold(" ".join(str(raw.get(key) or "") for key in (
        "source_event_type", "event_type", "classification", "category", "type",
    ))) + " " + _fold(" ".join(str(item) for item in (raw.get("official_tags") or [])))
    current_type = _fold(getattr(event, "event_type", ""))
    return title, " ".join(part for part in (current_type, metadata) if part)


def visitor_exclusion_reason(event: Any) -> str | None:
    """Return a high-precision exclusion reason for visitor-only activities."""
    title, metadata = _signals(event)
    if _fold(getattr(event, "event_type", "")) == "visitor activity":
        return "VISITOR_ACTIVITY"
    combined = f"{title} {metadata}".strip()
    for pattern in VISITOR_PATTERNS:
        if re.search(pattern, combined):
            return "VISITOR_ACTIVITY"
    return None


def classify_performance_type(event: Any) -> str:
    """Classify public performance types without treating all rows as performance."""
    title, metadata = _signals(event)
    combined = f"{metadata} {title}".strip()
    current = _fold(getattr(event, "event_type", ""))
    canonical_current = {
        "children family": "children_family",
        "visitor activity": "visitor_activity",
        "opera en concert": "opera_en_concert",
        "chamber music": "chamber_music",
        "concert recital": "concert_recital",
        "concert vocal": "concert_vocal",
    }.get(current, current)
    if canonical_current not in {"", "performance", "unclassified performance"}:
        return canonical_current
    if re.search(r"\b(opera|oper|operetta|operette)\b", combined):
        return "opera"
    if re.search(r"\b(ballet|ballett|dance|danse)\b", combined):
        return "ballet"
    if re.search(r"\brecitals?\b", combined):
        return "recital"
    if re.search(r"\bconcerto\b", combined):
        return "concerto"
    if re.search(r"\b(chamber music|chamber concert|kammermusik)\b", combined):
        return "chamber_music"
    if re.search(r"\b(concert|konzert|symphony|symphonic|orchestra|orchestral)\b", combined):
        return "concert"
    return canonical_current if canonical_current not in {"", "performance"} else "unclassified_performance"


def apply_publication_policy(events: list[Any]) -> tuple[list[Any], dict[str, Any]]:
    """Exclude visitor rows and attach a deterministic performance classification."""
    kept: list[Any] = []
    excluded: list[dict[str, Any]] = []
    for event in events:
        reason = visitor_exclusion_reason(event)
        if reason:
            excluded.append({
                "event_key": getattr(event, "event_key", None),
                "title": getattr(event, "title", None),
                "reason": reason,
                "source_url": getattr(event, "source_url", None),
            })
            continue
        event_type = classify_performance_type(event)
        raw = dict(event.raw) if isinstance(getattr(event, "raw", None), dict) else {}
        raw["publication_classification"] = event_type
        kept.append(replace(event, event_type=event_type, raw=raw))
    return kept, {
        "input_events": len(events),
        "kept_events": len(kept),
        "excluded_visitor_events": len(excluded),
        "excluded": excluded,
    }


def event_requires_cast(event: Any) -> bool:
    return str(getattr(event, "event_type", "")).casefold() in {"opera", "ballet"}
