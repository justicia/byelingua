from __future__ import annotations

import re
from datetime import date
from typing import Any, Mapping


SEASON_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso_date(value: object, field: str) -> date:
    if not isinstance(value, str) or not ISO_DATE_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be an ISO date in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value}") from exc


def resolve_season_bounds(
    season: str, venue_config: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    """Resolve a YYYY-YY season, optionally applying a venue configuration override."""
    match = SEASON_PATTERN.fullmatch(season) if isinstance(season, str) else None
    if not match:
        raise ValueError(f"invalid season: {season}")
    start_year = int(match.group(1))
    end_year = start_year + 1
    if int(match.group(2)) != end_year % 100:
        raise ValueError(f"invalid season: {season}")

    start = date(start_year, 9, 1)
    end = date(end_year, 8, 31)
    configured_bounds = (venue_config or {}).get("season_bounds", {})
    if not isinstance(configured_bounds, Mapping):
        raise ValueError("season_bounds must be an object")
    bounds = configured_bounds.get(season)
    if bounds is not None:
        if not isinstance(bounds, Mapping):
            raise ValueError(f"season_bounds[{season}] must be an object")
        start = _iso_date(bounds.get("season_start"), "season_start")
        end = _iso_date(bounds.get("season_end"), "season_end")
        if start.year != start_year or end.year != end_year:
            raise ValueError(
                f"season bounds for {season} must start in {start_year} and end in {end_year}"
            )
    if start > end:
        raise ValueError(f"season_start must not be after season_end for {season}")
    return start.isoformat(), end.isoformat()
