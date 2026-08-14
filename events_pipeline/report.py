from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


@dataclass
class IngestionReport:
    run_id: str
    source: str
    adapter_version: str
    started_at: str
    finished_at: str | None = None
    status: str = "RUNNING"
    records_fetched: int = 0
    records_valid: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    records_quarantined: int = 0
    records_failed: int = 0
    error_summary: list[str] | None = None

    @classmethod
    def start(cls, source: str, adapter_version: str):
        now = datetime.now(timezone.utc).isoformat()
        return cls(now.replace(":", "").replace("+", "_"), source, adapter_version, now, error_summary=[])

    def finish(self, status: str):
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.status = status

    def write(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{self.run_id}-{self.source}.json"
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
