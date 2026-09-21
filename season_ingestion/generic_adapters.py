"""Shared source-capability classification and adapter routing helpers.

This module deliberately contains no venue names. Venue configuration and
Hermes discovery describe the source; these helpers select reusable adapter
families and report independent acquisition/enrichment/canonical states.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_FAMILIES = (
    "STRUCTURED_API",
    "STRUCTURED_HTML",
    "PAGINATED_CALENDAR",
    "PRODUCTION_PLUS_OCCURRENCES",
    "JS_RENDERED_DISCOVERY",
    "PDF_FULL",
    "PDF_ENRICHMENT",
    "HYBRID",
)

ACQUISITION_STATUSES = (
    "SOURCE_READY",
    "SOURCE_PARTIAL",
    "ADAPTER_REQUIRED",
    "SOURCE_BLOCKED",
    "HUMAN_PDF_REQUIRED",
)

ENRICHMENT_STATUSES = ("COMPLETE", "PARTIAL", "NOT_AVAILABLE")
CANONICAL_STATUSES = ("SAFE", "REVIEW_REQUIRED")

# Backward-compatible structure aliases used by older registry entries.
GENERIC_ADAPTERS = {
    "JSON_LD": "generic_jsonld",
    "EMBEDDED_JSON": "generic_embedded_json",
    "PUBLIC_JSON_API": "generic_json_api",
    "ICS": "generic_ics",
    "STRUCTURED_HTML_LISTING": "generic_calendar_html",
    "MONTH_CALENDAR_HTML": "generic_calendar_html",
    "DETAIL_LINKED_LISTING": "generic_calendar_html",
    "EUROPE_OFFICIAL_EVENT": "europe_venue",
    "STRUCTURED_API": "structured_api_adapter",
    "STRUCTURED_HTML": "html_event_card_adapter",
    "PAGINATED_CALENDAR": "paginated_calendar_adapter",
    "PRODUCTION_PLUS_OCCURRENCES": "production_occurrence_adapter",
    "JS_RENDERED_DISCOVERY": "discovery_then_deterministic",
    "PDF_FULL": "pdf_adapter",
    "PDF_ENRICHMENT": "pdf_adapter",
    "HYBRID": "multi_source_merge",
}

_ENGLISH_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_RE = "|".join(_ENGLISH_MONTHS)
_MONTH_GROUP_RE = re.compile(
    rf"(?P<month>{_MONTH_RE})\s+(?P<days>\d{{1,2}}(?:\s*(?:,|and|&)\s*(?!20\d{{2}}\b)\d{{1,2}})*)(?:\s*,?\s*(?P<year>20\d{{2}}))?",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(?P<year>20\d{2})-(?P<month>\d{2})-(?P<day>\d{2})\b")
_NUMERIC_DATE_RE = re.compile(r"\b(?P<day>\d{1,2})[./](?P<month>\d{1,2})[./](?P<year>20\d{2})\b")


@dataclass(frozen=True)
class CapabilityProfile:
    """Serializable description of the source strategy selected for a run."""

    venue_id: str
    season: str
    discovery: dict[str, Any]
    occurrence_source: dict[str, Any]
    detail_source: dict[str, Any]
    pdf_source: dict[str, Any]
    capabilities: dict[str, Any]
    strategy: dict[str, Any]
    fallback: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        occurrence_family = self.occurrence_source["family"]
        enrichment_families = list(self.strategy.get("enrichment_source_families", []))
        return {
            "venue": self.venue_id,
            "venue_id": self.venue_id,
            "season": self.season,
            "discovery": self.discovery,
            "occurrence_source": self.occurrence_source,
            "detail_source": self.detail_source,
            "pdf_source": self.pdf_source,
            "capabilities": self.capabilities,
            # Keep the legacy field for existing consumers.  New reports must
            # use the explicit layer fields below because a venue can combine
            # HTML/API occurrences with PDF enrichment.
            "source_family": occurrence_family,
            "occurrence_source_family": occurrence_family,
            "enrichment_source_families": enrichment_families,
            "overall_source_family": "HYBRID" if enrichment_families and any(
                family != occurrence_family for family in enrichment_families
            ) else occurrence_family,
            "strategy": self.strategy,
            "fallback": self.fallback,
        }


def select_generic_adapter(structure_type: str) -> str | None:
    """Map a source structure or capability family to a reusable adapter."""
    return GENERIC_ADAPTERS.get(str(structure_type or "").upper())


def _normalise_family(value: Any) -> str | None:
    candidate = str(value or "").strip().upper().replace("-", "_")
    return candidate if candidate in SOURCE_FAMILIES else None


def classify_source_family(
    *,
    config: dict[str, Any] | None = None,
    discovery: dict[str, Any] | None = None,
    observations: dict[str, Any] | None = None,
) -> str:
    """Classify source capability from factual source observations."""
    config = config or {}
    discovery = discovery or {}
    observations = observations or {}
    configured = _normalise_family(
        config.get("occurrence_source_family")
        or config.get("source_family")
        or config.get("capability_family")
    )
    pdf_type = str(observations.get("pdf_type") or config.get("pdf_type") or "").upper()
    if pdf_type in {"FULL_SOURCE", "PDF_FULL", "PDF_FULL_SOURCE"}:
        return "PDF_FULL"
    if pdf_type in {"ENRICHMENT_SOURCE", "PDF_ENRICHMENT", "PDF_ENRICHMENT_SOURCE"}:
        return "PDF_ENRICHMENT"

    mode = str(discovery.get("discovered_mode") or observations.get("discovered_mode") or "").upper()
    endpoint = str(discovery.get("discovered_endpoint") or observations.get("endpoint") or "").casefold()
    paginated = bool(
        discovery.get("pagination")
        or observations.get("paginated")
        or any(token in endpoint for token in ("page=", "p=", "offset=", "month=", "calendar"))
        or configured == "PAGINATED_CALENDAR"
    )
    production_and_occurrences = bool(
        observations.get("production_plus_occurrences")
        or configured == "PRODUCTION_PLUS_OCCURRENCES"
    )
    if mode in {"API", "JSON", "STRUCTURED_API"}:
        discovered_family = "PAGINATED_CALENDAR" if paginated else "STRUCTURED_API"
    elif mode in {"HTML", "STRUCTURED_HTML"}:
        discovered_family = "PAGINATED_CALENDAR" if paginated else "STRUCTURED_HTML"
    elif mode in {"JS", "BROWSER", "JS_RENDERED", "JS_RENDERED_DISCOVERY"}:
        discovered_family = "JS_RENDERED_DISCOVERY"
    elif production_and_occurrences:
        discovered_family = "PRODUCTION_PLUS_OCCURRENCES"
    else:
        discovered_family = configured or "STRUCTURED_HTML"

    pdf_configured = bool(config.get("official_pdf_sources") or config.get("pdf_source"))
    has_occurrence_source = bool(
        config.get("official_source")
        or config.get("listing_source")
        or discovery.get("discovered_endpoint")
        or observations.get("events")
    )
    enrichment_source = bool(config.get("detail_path_prefixes") or config.get("detail_source") or observations.get("detail_source"))
    if configured:
        return configured
    if pdf_configured and has_occurrence_source and (observations.get("hybrid") or enrichment_source):
        return "HYBRID"
    return discovered_family


def build_capability_profile(
    *,
    venue_id: str,
    season: str,
    config: dict[str, Any] | None = None,
    discovery: dict[str, Any] | None = None,
    observations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the per-run source capability artifact payload."""
    config = config or {}
    discovery = discovery or {}
    observations = observations or {}
    family = classify_source_family(config=config, discovery=discovery, observations=observations)
    official = config.get("official_source") or config.get("official_source_url")
    listing = config.get("listing_source") or config.get("listing_source_url") or official
    endpoint = discovery.get("discovered_endpoint") or observations.get("endpoint") or listing
    mode = discovery.get("discovered_mode") or observations.get("discovered_mode") or ("API" if family == "STRUCTURED_API" else "HTML")
    pdf_urls = config.get("official_pdf_sources") or config.get("pdf_source") or []
    if isinstance(pdf_urls, str):
        pdf_urls = [pdf_urls]
    detail = config.get("detail_source") or config.get("detail_path_prefixes") or []
    configured_capabilities = [
        family,
        *(_normalise_family(value) for value in config.get("capabilities", []) if _normalise_family(value)),
    ]
    configured_enrichment = config.get("enrichment_source_families")
    if isinstance(configured_enrichment, str):
        configured_enrichment = [configured_enrichment]
    enrichment_families = [
        value for value in (
            _normalise_family(item)
            for item in (configured_enrichment or [])
        ) if value
    ]
    if not enrichment_families:
        enrichment_families = sorted({
            value for value in configured_capabilities
            if value in {"PDF_FULL", "PDF_ENRICHMENT"} and value != family
        })
    detail_family = _normalise_family(
        (config.get("detail_source") or {}).get("source_family")
        if isinstance(config.get("detail_source"), dict)
        else config.get("detail_source_family")
    ) or ("STRUCTURED_HTML" if detail else None)
    pagination_mode = (
        discovery.get("pagination_mode")
        or discovery.get("pagination")
        or config.get("pagination_mode")
        or ("bounded" if family == "PAGINATED_CALENDAR" else "none")
    )
    detail_pattern = (
        discovery.get("detail_url_pattern")
        or config.get("detail_url_pattern")
        or config.get("detail_link_pattern")
    )
    capabilities = {
        "families": sorted(set(filter(None, configured_capabilities))),
        "explicit_dates": bool(config.get("explicit_dates", True)),
        "explicit_times": bool(config.get("explicit_times", True)),
        "programme": bool(config.get("programme", config.get("capability_programme", True))),
        "credits": bool(config.get("credits", config.get("capability_credits", bool(detail)))),
        "room": bool(config.get("room", config.get("capability_room", False))),
        "detail_links": bool(config.get("detail_links", bool(detail))),
    }
    profile = CapabilityProfile(
        venue_id=venue_id,
        season=season,
        discovery={
            "status": discovery.get("source_discovery", observations.get("source_discovery", "NOT_ATTEMPTED")),
            "mode": mode,
            "endpoint": endpoint,
            "discovered_by": discovery.get("discovered_by") or ("hermes" if discovery else "configuration"),
            "hermes_role": "SOURCE_DISCOVERY_ONLY" if discovery or observations.get("hermes_mode") == "source_discovery" else "OPTIONAL_RESIDUAL_AMBIGUITY",
        },
        occurrence_source={
            "family": family,
            "source_family": family,
            "url": endpoint,
            "mode": mode,
            "requires_browser": bool(config.get("requires_browser") or discovery.get("requires_browser")),
            "pagination_mode": pagination_mode,
            "detail_pattern": detail_pattern,
            "explicit_date_required": True,
            "events_observed": int(observations.get("events", 0) or 0),
        },
        detail_source={
            "url": detail,
            "enabled": bool(detail),
            "source_family": detail_family,
            "detail_pattern": detail_pattern,
            "bounded": True,
            "programme_and_credits_optional": True,
        },
        pdf_source={
            "available": bool(pdf_urls),
            "url": pdf_urls[0] if pdf_urls else None,
            "urls": list(pdf_urls),
            "type": observations.get("pdf_type") or config.get("pdf_type") or "UNCLASSIFIED",
            "fallback_only": True,
        },
        capabilities=capabilities,
        strategy={
            "primary": config.get("strategy", "deterministic occurrence extraction"),
            "adapter": select_generic_adapter(family),
            "occurrence_adapter": select_generic_adapter(family),
            "enrichment_adapters": [select_generic_adapter(value) for value in enrichment_families if select_generic_adapter(value)],
            "enrichment_source_families": enrichment_families,
            "merge": "per-fact provenance-preserving official-source merge",
            "semantic_hermes": "residual ambiguous blocks only",
        },
        fallback={
            "order": ["automatic_official_pdf", "human_official_pdf"],
            "auto_pdf": True,
            "human_pdf": True,
            "human_pdf_requires": "no useful deterministic occurrence source, known official PDF, automatic download failure",
            "configured": bool(pdf_urls),
        },
    )
    return profile.to_dict()


def write_capability_profile(output_dir: Path, profile: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "source_capability_profile.json"
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def expand_multi_date_occurrences(text: str, *, default_year: int | None = None) -> list[dict[str, str]]:
    """Expand explicit multi-date listing text without inferring dates."""
    raw = " ".join(str(text or "").replace("\u2013", "-").split())
    results: list[dict[str, str]] = []
    for match in _ISO_DATE_RE.finditer(raw):
        results.append({"date": match.group(0), "source_text": match.group(0)})
    for match in _NUMERIC_DATE_RE.finditer(raw):
        try:
            parsed = date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
        except ValueError:
            continue
        results.append({"date": parsed.isoformat(), "source_text": match.group(0)})
    years = [int(value) for value in re.findall(r"\b(20\d{2})\b", raw)]
    year_hint = years[-1] if years else default_year
    for match in _MONTH_GROUP_RE.finditer(raw):
        if re.match(r"\s*-\s*\d", raw[match.end():]):
            continue
        year = int(match.group("year")) if match.group("year") else year_hint
        if year is None:
            continue
        month = _ENGLISH_MONTHS[match.group("month").casefold()]
        for day_value in re.findall(r"\d{1,2}", match.group("days")):
            try:
                parsed = date(year, month, int(day_value))
            except ValueError:
                continue
            results.append({"date": parsed.isoformat(), "source_text": match.group(0)})
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in results:
        if item["date"] not in seen:
            unique.append(item)
            seen.add(item["date"])
    return unique


def classify_acquisition_status(
    *,
    events: int,
    source_capability: str | None = None,
    source_discovered: bool = False,
    deterministic_attempted: bool = False,
    useful_occurrence_source: bool = True,
    pdf_known: bool = False,
    pdf_download_failed: bool = False,
) -> str:
    """Classify occurrence acquisition independently from enrichment/review."""
    if events > 0:
        return "SOURCE_PARTIAL" if source_capability in {"SOURCE_PARTIAL", "SOURCE_BLOCKED"} else "SOURCE_READY"
    if source_discovered or deterministic_attempted:
        return "ADAPTER_REQUIRED" if useful_occurrence_source else "SOURCE_BLOCKED"
    if pdf_known and pdf_download_failed and not useful_occurrence_source:
        return "HUMAN_PDF_REQUIRED"
    return "SOURCE_BLOCKED"


def classify_enrichment_status(*, programme: int, credits: int) -> str:
    if programme > 0 and credits > 0:
        return "COMPLETE"
    if programme > 0 or credits > 0:
        return "PARTIAL"
    return "NOT_AVAILABLE"


def classify_canonical_status(*, global_master: str, review_items: int = 0, passed: bool = False) -> str:
    if global_master != "PASS" or review_items > 0 or not passed:
        return "REVIEW_REQUIRED"
    return "SAFE"


def merge_provenance_records(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    """Append source evidence without overwriting the first factual value."""
    target_provenance = target.setdefault("provenance", {})
    incoming_provenance = incoming.get("provenance") if isinstance(incoming.get("provenance"), dict) else {}
    record = {key: incoming_provenance.get(key) for key in ("source_url", "pdf_page", "pdf_sha256", "source_field") if incoming_provenance.get(key) is not None}
    if not record and incoming.get("source_url"):
        record = {"source_url": incoming["source_url"]}
    records = target_provenance.setdefault("source_records", [])
    if record and record not in records:
        records.append(record)
