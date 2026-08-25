"""Read-only classification for unlinked work-character staging rows."""

from __future__ import annotations

from typing import Any

from .global_master import normalize_identity


NON_CHARACTER_LABELS = {
    "conductor", "musical conductor", "stage director", "director", "lighting",
    "set designer", "sets", "costume", "costumes", "choreography",
    "chorus conductor", "chorus master", "orchestra", "choir", "ensemble",
    "dramaturg", "dramaturgy",
}
LOCALIZED_LABELS = {"un joven pastor"}
CANONICAL_REVIEW_LABELS = {"walter von der vogelweide", "heinrich der schreiber", "wolfram von eschenbach"}


def classify_unlinked_character(row: dict[str, Any], snapshot: Any, *, work_label_counts: dict[str, int] | None = None, verified_original_names: set[str] | None = None) -> dict[str, Any]:
    label = str(row.get("canonical_name") or "").strip()
    key = normalize_identity(label)
    if key in {normalize_identity(value) for value in NON_CHARACTER_LABELS}:
        classification = "NON_CHARACTER_CONTAMINATION"
        reason = "production/artistic role hard-blocked from global character identity"
        proposed = None
    elif key in {normalize_identity(value) for value in LOCALIZED_LABELS}:
        classification = "REVIEW_LOCALIZED_NAME"
        reason = "localized source label requires original-language canonical verification"
        proposed = None
    else:
        matches = []
        for character in snapshot.entities.get("character", []):
            if normalize_identity(character.get("canonical_name")) == key:
                matches.append(character)
        for alias in getattr(snapshot, "character_aliases", []):
            if normalize_identity(alias.get("alias")) == key:
                matches.extend(character for character in snapshot.entities.get("character", []) if character.get("id") == alias.get("character_id"))
        matches = list({character.get("id"): character for character in matches}.values())
        if len(matches) == 1:
            classification = "SAFE_LINK_EXISTING_CHARACTER"
            reason = "exact canonical or existing alias match"
            proposed = matches[0].get("id")
        elif len(matches) > 1:
            classification = "REVIEW_CHARACTER_IDENTITY"
            reason = "ambiguous global or cross-work identity; no blind merge"
            proposed = None
        elif key in {normalize_identity(value) for value in CANONICAL_REVIEW_LABELS}:
            classification = "REVIEW_CANONICAL_NAME"
            reason = "source label requires canonical spelling/capitalization verification"
            proposed = None
        elif key in {normalize_identity(value) for value in (verified_original_names or set())}:
            classification = "SAFE_NEW_GLOBAL_CHARACTER_VERIFIED"
            reason = "official original-language dramatic role verified for this Work"
            proposed = None
        elif (work_label_counts or {}).get(key, 0) > 1:
            classification = "REVIEW_CHARACTER_IDENTITY"
            reason = "same new label occurs across multiple works; no blind cross-work merge"
            proposed = None
        elif key:
            classification = "REVIEW_CHARACTER_IDENTITY"
            reason = "canonical original-language identity is not verified"
            proposed = None
        else:
            classification = "REVIEW_CHARACTER_IDENTITY"
            reason = "empty character identity"
            proposed = None
    return {**row, "proposed_character_id": proposed, "classification": classification, "reason": reason}

