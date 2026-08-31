from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(__file__).with_name("venue_registry.json")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "season-ingestion-registry-v1":
        raise ValueError("unsupported venue registry schema")
    if not isinstance(payload.get("venues"), dict) or not payload["venues"]:
        raise ValueError("venue registry must contain venues")
    for venue_id, config in payload["venues"].items():
        if not isinstance(config, dict) or not config.get("adapter") or not config.get("official_source"):
            raise ValueError(f"venue registry entry is incomplete: {venue_id}")
        contract = config.get("source_contract")
        if not isinstance(contract, dict) or contract.get("schema_version") != "official-source-contract-v2" or contract.get("writes") is not False:
            raise ValueError(f"venue registry source contract is missing or write-enabled: {venue_id}")
    return payload


def load_adapter(venue: str, registry: dict[str, Any] | None = None) -> Any:
    config = (registry or load_registry())["venues"].get(venue)
    if not config:
        raise ValueError(f"venue is not registered: {venue}")
    module_name, symbol = config["adapter"].split(":", 1)
    return getattr(importlib.import_module(module_name), symbol)(config)
