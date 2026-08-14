from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlparse


# The single contract shared by the preflight reader, reconciliation, and writer.
PATCHABLE_EVENT_FIELDS = (
    "start_time",
    "end_time",
    "room",
    "event_type",
)


@dataclass(frozen=True)
class CanonicalEvent:
    source: str
    source_event_id: str
    source_url: str
    organization: str
    venue: str
    city: str
    country: str
    timezone: str
    title: str
    date: str
    start_time: str | None
    end_time: str | None
    room: str | None
    event_type: str
    classification: str | None = None
    programme: list[dict[str, Any]] = field(default_factory=list)
    credits: list[dict[str, Any]] = field(default_factory=list)
    data_quality: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def event_key(self) -> str:
        """A stable source identity; mutable titles and times are excluded."""
        identity = f"{self.source}\0{self.source_event_id}".encode()
        return f"{self.source}:{hashlib.sha256(identity).hexdigest()[:24]}"

    def validate(self) -> None:
        if not all((self.source, self.source_event_id, self.source_url, self.organization,
                    self.venue, self.city, self.country, self.timezone, self.title)):
            raise ValueError("canonical event is missing a required field")
        date.fromisoformat(self.date)
        source_url = urlparse(self.source_url)
        if source_url.scheme not in {"http", "https"} or not source_url.netloc:
            raise ValueError(f"invalid source URL: {self.source_url}")
        if self.start_time is not None and len(self.start_time) != 5:
            raise ValueError(f"invalid start time: {self.start_time}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"event_key": self.event_key, **asdict(self)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
