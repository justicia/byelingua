"""Batch adapters for deterministic official-PDF season acquisition.

The Barbican V3 runner remains the frozen reference implementation.  This
module adds only the small amount of layout-specific segmentation needed for
the next PDF batch and reuses the existing PDF transport, source-facts
contract, merge, and dry-run pipeline.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from jobs.hermes_acquire_worker import SOURCE_FACTS_SCHEMA_VERSION, validate_source_facts
from season_ingestion.hermes_acquisition import persist_source_facts
from season_ingestion.pdf_acquisition import (
    PdfAcquisitionError,
    _pdf_page_count,
    download_pdf,
    extract_pdf_pages,
    merge_pdf_chunk_facts,
)
from season_ingestion.pipeline import run_pipeline
from season_ingestion.product_contract import (
    BYELINGUA_PRODUCT_CONTRACT_VERSION,
    assert_product_contract_compatibility,
    declare_product_contract,
)


BATCH_SEASON = "2026-27"
BATCH_VENUES = (
    "deutsche_oper_berlin",
    "dutch_national_opera",
    "komische_oper_berlin",
    "theatre_champs_elysees",
    "southbank_centre",
)

# Canonical venue selection for the shared Hermes/PDF/human state machine.
# Komische is accepted already but remains selectable for targeted reruns;
# the default state-machine batch derives the unresolved subset below.
ACQUISITION_STATE_MACHINE_VENUES = (
    "deutsche_oper_berlin",
    "dutch_national_opera",
    "komische_oper_berlin",
    "theatre_champs_elysees",
    "southbank_centre",
    "tonhalle_zurich",
    "lauditori_barcelona",
)
UNRESOLVED_ACQUISITION_STATE_MACHINE_VENUES = tuple(
    venue for venue in ACQUISITION_STATE_MACHINE_VENUES
    if venue not in {"komische_oper_berlin", "tonhalle_zurich", "lauditori_barcelona"}
)

PDF_URLS = {
    "deutsche_oper_berlin": (
        "https://deutscheoperberlin.de/dox/download.php?filesize=107825&"
        "name=PK_Premieren%C3%BCbersicht.pdfmimetype%3Dpdf&url=https%3A%2F%2F"
        "dox-file.culturebase.org%2F1%2F7%2F6%2Fd%2F8%2F176d8a4ae84172a43c5bdfa3e9f49f6f.pdf"
    ),
    "dutch_national_opera": "https://digitaalpubliceren.com/operaballet/21244/2/",
    "komische_oper_berlin": "https://kob-6a25.kxcdn.com/download/12761/spielzeitheft_26-27_komische_oper_berlin.pdf",
    "theatre_champs_elysees": "https://www.calameo.com/read/003045515feb4b86d348d",
    "southbank_centre": "https://bynder.southbankcentre.co.uk/asset/43cc3530-cfaa-40d2-ab91-7d032820272e/Forward-planner-Classical-Music-Autumn-Winter-2026-27.pdf",
}

_DE_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}
_DE_WEEKDAYS = "MO|DI|MI|DO|FR|SA|SO"
_MONTH_HEADER_RE = re.compile(r"^(?P<month>[A-Za-zÄÖÜäöü]+)\s+(?P<year>20(?:26|27))$", re.I)
_DAY_RE = re.compile(rf"^(?P<weekday>{_DE_WEEKDAYS})(?:\s+(?P<day>\d{{1,2}})\.)?\s*(?P<rest>.*)$", re.I)
_TIME_RE = re.compile(r"^(?P<time>\d{1,2}:\d{2})\s+(?P<rest>.+)$")


def _normalize_calendar_header(text: str) -> str:
    # The source PDF uses a visually similar capital O in 2O26/2O27.
    return re.sub(r"(?<=2)O(?=2[67]\b)", "0", text.strip(), flags=re.I)


def _line_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _pdf_page_lines(page: dict[str, Any]) -> list[str]:
    return [_line_text(line) for line in str(page.get("text") or "").splitlines() if _line_text(line)]


def _clean_komische_listing_title(raw: str) -> tuple[str, str | None]:
    value = _line_text(raw)
    room = None
    if "@" in value:
        value, room = value.split("@", 1)
        room = re.sub(r"\s+[A-Z]$", "", _line_text(room)) or None
    value = re.sub(r"\s+\d+(?:\s*/\s*\d+)?\s*€\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+S\.\s*\d+\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+[A-EPS]\s*$", "", value)
    value = re.sub(r"\s+(?:WIEDERAUFNAHME|PREMIERE|URAUFFÜHRUNG)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+[A-EPS]\s*$", "", value)
    value = re.sub(r"\s+UHR\s*$", "", value, flags=re.I)
    return value.strip(" -–—"), room


def _is_non_programme_title(title: str) -> bool:
    normalized = title.casefold()
    return normalized.startswith(("führung", "guided tour", "einführung", "spielzeitfest"))


def segment_komische_calendar(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Segment explicit date/time rows from the Komische season calendar."""
    blocks: list[dict[str, Any]] = []
    month = None
    year = None
    current_date: date | None = None
    pending_weekday: str | None = None
    pending_prefix = ""

    for page in pages:
        # Pages 171-181 are the printed season calendar in this PDF.  Keeping
        # the boundary explicit prevents brochure prose from becoming events.
        if not 171 <= int(page["page"]) <= 181:
            continue
        lines = _pdf_page_lines(page)
        index = 0
        while index < len(lines):
            line = lines[index]
            header = _MONTH_HEADER_RE.match(_normalize_calendar_header(line))
            if header and header.group("month").casefold() in _DE_MONTHS:
                month = _DE_MONTHS[header.group("month").casefold()]
                year = int(header.group("year"))
                current_date = None
                pending_prefix = ""
                index += 1
                continue

            day_match = _DAY_RE.match(line)
            if day_match and day_match.group("day"):
                day = int(day_match.group("day"))
                if month is None or year is None:
                    index += 1
                    continue
                try:
                    current_date = date(year, month, day)
                except ValueError:
                    current_date = None
                pending_weekday = None
                pending_prefix = ""
                rest = _line_text(day_match.group("rest"))
                if rest:
                    time_match = _TIME_RE.match(rest)
                    if time_match and current_date is not None:
                        blocks.append(_calendar_block(page, current_date, time_match.group("time"), time_match.group("rest"), len(blocks) + 1, line))
                index += 1
                continue

            # One calendar row is split as "MI" / "16." / "19:30 Lear".
            weekday_only = _DAY_RE.match(line)
            if weekday_only and not weekday_only.group("day") and not weekday_only.group("rest"):
                pending_weekday = weekday_only.group("weekday").upper()
                index += 1
                continue
            if pending_weekday and re.fullmatch(r"\d{1,2}\.", line):
                if month is not None and year is not None:
                    try:
                        current_date = date(year, month, int(line[:-1]))
                    except ValueError:
                        current_date = None
                pending_weekday = None
                pending_prefix = ""
                index += 1
                continue

            time_match = _TIME_RE.match(line)
            if time_match and current_date is not None:
                raw_title = f"{pending_prefix} {time_match.group('rest')}".strip()
                pending_prefix = ""
                blocks.append(_calendar_block(page, current_date, time_match.group("time"), raw_title, len(blocks) + 1, line))
                index += 1
                continue

            if current_date is not None and line.startswith("@") and blocks and blocks[-1].get("date") == current_date.isoformat() and not blocks[-1].get("room"):
                room = re.sub(r"\s+[A-Z]$", "", _line_text(line[1:]))
                blocks[-1]["room"] = room or None
                blocks[-1]["raw_text"] = f"{blocks[-1].get('raw_text', '')}\n{line}".strip()
                index += 1
                continue

            if current_date is not None and line and not line.startswith(("SPIELPLAN", "IM ANSCHLUSS", "@")):
                # Keep source line continuations, but never turn them into an
                # event until a following explicit time line is present.
                if not re.search(r"(?:FEIERTAG|SILVESTER|NEUJAHR|OSTER|PFINGST)", line, re.I):
                    pending_prefix = f"{pending_prefix} {line}".strip()
            index += 1
    return blocks


def _calendar_block(page: dict[str, Any], event_date: date, start_time: str, raw_title: str, index: int, raw_line: str) -> dict[str, Any]:
    title, room = _clean_komische_listing_title(raw_title)
    return {
        "block_index": index,
        "kind": "single",
        "date": event_date.isoformat(),
        "times": [start_time],
        "room": room,
        "title": title,
        "add_programme": not _is_non_programme_title(title),
        "pdf_page": int(page["page"]),
        "pdf_pages": [int(page["page"])],
        "source_url": page["source_url"],
        "pdf_sha256": page.get("pdf_sha256"),
        "raw_text": raw_line,
    }


def segment_enrichment_pages(pages: list[dict[str, Any]], venue_id: str) -> list[dict[str, Any]]:
    """Return auditable non-occurrence blocks for enrichment-only PDFs."""
    blocks: list[dict[str, Any]] = []
    for page in pages:
        text = str(page.get("text") or "")
        if venue_id == "deutsche_oper_berlin" and ("Premieren" in text or "Premiere:" in text):
            blocks.append({
                "block_index": len(blocks) + 1,
                "kind": "enrichment",
                "pdf_page": int(page["page"]),
                "pdf_pages": [int(page["page"])],
                "source_url": page["source_url"],
                "pdf_sha256": page.get("pdf_sha256"),
                "raw_text": text,
                "review_reason": "premiere/production overview is enrichment, not an occurrence calendar",
            })
        elif venue_id == "southbank_centre" and page["page"] in {1, 2, 3, 4, 5}:
            blocks.append({
                "block_index": len(blocks) + 1,
                "kind": "enrichment",
                "pdf_page": int(page["page"]),
                "pdf_pages": [int(page["page"])],
                "source_url": page["source_url"],
                "pdf_sha256": page.get("pdf_sha256"),
                "raw_text": text,
                "review_reason": "forward-planner highlights are not a complete occurrence calendar",
            })
    return blocks


def _source_fact_request(config: dict[str, Any], venue_id: str, season: str, pdf_url: str) -> dict[str, Any]:
    return {
        "venue_id": venue_id,
        "season": season,
        "official_source_url": pdf_url,
        "listing_source_url": config.get("listing_source") or config.get("official_source"),
        "source_id": config.get("source_id", venue_id),
        "organization": config.get("organization"),
        "venue": config.get("venue"),
        "city": config.get("city"),
        "country": config.get("country"),
        "timezone": config.get("timezone"),
        "source_contract": {
            **(config.get("source_contract") or {}),
            "deterministic_pdf_acquisition": True,
            "batch_framework": "pdf-acquisition-batch-v1",
            "registry_official_source": config.get("official_source"),
            "registry_listing_source": config.get("listing_source"),
            "writes": False,
        },
    }


def _facts_from_blocks(request: dict[str, Any], blocks: list[dict[str, Any]], pdf_source: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("kind") != "single" or not block.get("title") or "\ufffd" in str(block["title"]):
            continue
        page = int(block["pdf_page"])
        source_url = str(pdf_source["source_url"])
        title = str(block["title"])
        provenance = {
            "source_url": source_url,
            "pdf_page": page,
            "pdf_pages": block.get("pdf_pages", [page]),
            "pdf_sha256": pdf_source["sha256"],
            "source_field": "official.pdf.event",
        }
        # A calendar row proves an occurrence and its production title.  It is
        # not repertoire evidence: the title must first resolve to an existing
        # Production/Work (or pass authority review for a new one).
        programme = []
        start_time = (block.get("times") or [None])[0]
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:48] or "event"
        events.append({
            "source_event_id": f"pdf-{request['venue_id']}-{block['block_index']}-{block['date']}-{start_time or 'unknown'}-{slug}",
            "source_url": source_url,
            "title": title,
            "date": block["date"],
            "start_time": start_time,
            "end_time": None,
            "room": block.get("room"),
            "event_type": "performance",
            "classification": "performance",
            "programme": programme,
            "credits": [],
            "provenance": provenance,
            "raw_block_text": block.get("raw_text", ""),
            "data_quality": {
                "schedule": {"year_status": "YEAR_EXPLICIT", "source_field": "official.pdf.event"},
                "programme": {"status": "NO_PROGRAMME_EVIDENCE", "reason": "calendar production title is not programme evidence"},
            },
        })
    facts = {
        "schema_version": SOURCE_FACTS_SCHEMA_VERSION,
        "venue_id": request["venue_id"],
        "season": request["season"],
        "source_id": request["source_id"],
        "source_type": "html",
        "official_source_url": request["official_source_url"],
        "source_contract": {
            **copy.deepcopy(request.get("source_contract") or {}),
            "pdf_source_mode": "FULL_SOURCE",
            "pdf_sources": [copy.deepcopy(pdf_source)],
        },
        "events": events,
    }
    declare_product_contract(facts, declared_version=BYELINGUA_PRODUCT_CONTRACT_VERSION)
    from jobs.hermes_acquire_worker import _normalize_programme_order

    _normalize_programme_order(facts)
    validate_source_facts(facts)
    return facts


def run_pdf_batch_venue(
    *,
    venue_id: str,
    config: dict[str, Any],
    season: str,
    output_dir: Path,
    download_timeout_seconds: int = 60,
    pdf_url: str | None = None,
    manual_pdf_path_value: str | None = None,
    include_facts: bool = False,
) -> dict[str, Any]:
    """Run one venue independently; acquisition failures become a report."""
    assert_product_contract_compatibility(BYELINGUA_PRODUCT_CONTRACT_VERSION)
    pdf_url = pdf_url or PDF_URLS.get(venue_id)
    if not pdf_url:
        return {
            "venue": venue_id,
            "pdf_download": "FAIL",
            "pdf_pages": 0,
            "text_pages": 0,
            "pdf_event_blocks": 0,
            "deterministic_parsed": 0,
            "review_blocks": 0,
            "events": 0,
            "programme": 0,
            "credits": 0,
            "source_type": "NONE",
            "global_master": "NOT_RUN",
            "production_writes": 0,
            "status": "BLOCKED",
            "blocker": "no official PDF URL was supplied",
        }
    base = {
        "venue": venue_id,
        "pdf_download": "FAIL",
        "pdf_pages": 0,
        "text_pages": 0,
        "pdf_event_blocks": 0,
        "deterministic_parsed": 0,
        "review_blocks": 0,
        "events": 0,
        "programme": 0,
        "credits": 0,
        "source_type": "NONE",
        "global_master": "NOT_RUN",
        "production_writes": 0,
        "status": "BLOCKED",
        "blocker": None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    request = _source_fact_request(config, venue_id, season, pdf_url)
    try:
        if manual_pdf_path_value:
            manual_path = Path(manual_pdf_path_value)
            payload = manual_path.read_bytes()
            if not payload.startswith(b"%PDF-"):
                raise PdfAcquisitionError("manual PDF is missing the %PDF- header")
            artifact = {
                "source_url": pdf_url,
                "path": str(manual_path),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_size": len(payload),
                "page_count": _pdf_page_count(manual_path),
                "acquisition_level": "HUMAN_PDF",
            }
        else:
            artifact = download_pdf(pdf_url, output_dir / "pdf-cache", timeout_seconds=download_timeout_seconds)
    except Exception as exc:
        base["blocker"] = str(exc)
        _write_json(output_dir / "summary.json", base)
        return base

    pages = extract_pdf_pages(artifact)
    _write_json(output_dir / "pdf-metadata.json", artifact)
    _write_json(output_dir / "pdf-pages.json", pages)
    base.update({
        "pdf_download": "PASS",
        "pdf_bytes": artifact["byte_size"],
        "pdf_pages": artifact["page_count"],
        "text_pages": sum(page["status"] == "TEXT_OK" for page in pages),
        "text_empty_pages": sum(page["status"] == "TEXT_EMPTY" for page in pages),
    })

    if venue_id == "komische_oper_berlin":
        blocks = segment_komische_calendar(pages)
        source_type = "FULL_SOURCE"
        blocker = None if blocks else "calendar pages contained no explicit date/time rows"
    else:
        blocks = segment_enrichment_pages(pages, venue_id)
        source_type = "ENRICHMENT_SOURCE"
        blocker = "official PDF is enrichment-only; explicit occurrence coverage remains separate"
    _write_json(output_dir / "pdf-event-blocks.json", blocks)
    base["pdf_event_blocks"] = len(blocks) if venue_id == "komische_oper_berlin" else 0

    facts = None
    if venue_id == "komische_oper_berlin" and blocks:
        partial = _facts_from_blocks(request, blocks, artifact)
        facts = merge_pdf_chunk_facts(
            [partial],
            request=request,
            pdf_source=artifact,
            source_mode=source_type,
        )
        base["facts"] = facts
        facts_path = persist_source_facts(facts, root=output_dir / "source-facts")
        pipeline_summary = run_pipeline(
            venue=venue_id,
            season=season,
            mode="dry-run",
            scope="full-season",
            output_dir=output_dir / "canonical-staging",
            hermes_source_facts_path=facts_path,
        )
        base["events"] = pipeline_summary.get("counts", {}).get("events", 0)
        base["programme"] = pipeline_summary.get("detail_enrichment", {}).get("programme_items", 0)
        base["credits"] = pipeline_summary.get("detail_enrichment", {}).get("credits_total", 0)
        base["global_master"] = pipeline_summary.get("global_master_preflight", "FAIL")
        base["production_writes"] = pipeline_summary.get("counts", {}).get("writes", 0)
        base["deterministic_parsed"] = len(facts["events"])
        base["review_blocks"] = max(0, len(blocks) - base["deterministic_parsed"])
        base["status"] = "SOURCE_READY" if pipeline_summary.get("passed") and base["production_writes"] == 0 else "REVIEW_ONLY"
        base["blocker"] = None if base["status"] == "SOURCE_READY" else "canonical dry-run gates did not all pass"
    else:
        base["pdf_event_blocks"] = 0
        base["review_blocks"] = len(blocks)
        base["blocker"] = blocker
        base["status"] = "REVIEW_ONLY"
    base["source_type"] = source_type
    facts_for_return = base.get("facts")
    base.pop("facts", None)
    _write_json(output_dir / "summary.json", base)
    if include_facts and facts_for_return is not None:
        base["facts"] = facts_for_return
    return base


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
