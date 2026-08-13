from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any


@dataclass
class CanonicalEvent:
    source: str
    source_event_id: str
    source_url: str
    venue: str
    city: str
    country: str
    title: str
    date: str
    start_time: str | None = None
    end_time: str | None = None
    event_type: str = "concert"
    room: str | None = None
    review_status: str = "ready"
    programme: list[dict[str, Any]] = field(default_factory=list)
    credits: list[dict[str, Any]] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors = []
        if not self.source or not self.source_event_id:
            errors.append("missing source identity")
        if not self.source_url.startswith(("http://", "https://")):
            errors.append("missing source URL")
        try:
            datetime.fromisoformat(self.date)
        except ValueError:
            errors.append("invalid datetime/date")
        if not self.venue or not self.city or not self.title:
            errors.append("missing canonical event field")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
