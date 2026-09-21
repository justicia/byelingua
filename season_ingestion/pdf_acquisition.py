"""Deterministic official-PDF acquisition for season source facts.

This module deliberately keeps PDF transport separate from browser discovery:
the known official PDF is fetched with ``requests``, extracted page by page,
sent to Hermes in bounded page chunks, and merged back into the existing
``hermes-source-facts-v1`` contract.  It does not know about Supabase and does
not perform canonical writes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from jobs.hermes_acquire_worker import (
    SOURCE_FACTS_SCHEMA,
    SOURCE_FACTS_SCHEMA_VERSION,
    WorkerError,
    _parse_and_validate,
    _run_hermes,
    validate_source_facts,
)


PDF_MAGIC = b"%PDF-"
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 60
DEFAULT_CHUNK_TIMEOUT_SECONDS = 240
DEFAULT_MAX_CHUNK_PAGES = 8
DEFAULT_MAX_CHUNK_CHARS = 20_000
PDF_SOURCE_MODE = "FULL_SOURCE"

_WEEKDAYS = "Mon|Tue|Wed|Thu|Fri|Sat|Sun"
_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_LINE_RE = re.compile(
    rf"^(?P<weekday>{_WEEKDAYS})\s+(?P<day>\d{{1,2}})\s+(?P<month>{_MONTHS})\s+(?P<year>\d{{4}})(?:\s*,?\s*(?P<rest>.*))?$",
    re.IGNORECASE,
)
_DATE_RANGE_RE = re.compile(
    rf"(?:\b\d{{1,2}}\s*(?:{_MONTHS})?\s*(?:-|\u2013|\u2014)\s*\d{{1,2}}\s*(?:{_MONTHS})?\s+\d{{4}}\b|\b\d{{1,2}}\s+{_MONTHS}\s+\d{{4}}\s*(?:-|\u2013|\u2014)\s*(?:{_WEEKDAYS}\s+)?\d{{1,2}}\s+{_MONTHS}\s+\d{{4}}\b)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"(?<!\d)(?P<hour>\d{1,2})(?:[.:](?P<minute>\d{2}))?\s*(?P<ampm>am|pm)\b", re.IGNORECASE)
_MONTH_HEADER_RE = re.compile(rf"^(?:{_MONTHS})\s+\d{{4}}$", re.IGNORECASE)
_ROLE_RE = re.compile(
    r"\b(conductor|director|artistic director|chief conductor|presenter|piano|violin|viola|cello|flute|trumpet|trombone|organ|harpsichord|soprano|mezzo-soprano|contralto|countertenor|tenor|baritone|bass|percussion|electronics|guitar|lute|sitar|tabla|sarod|vocal|vocals|voice|composer|chorusmaster|artistic director)\b",
    re.IGNORECASE,
)
_ENSEMBLE_RE = re.compile(r"\b(orchestra|ensemble|choir|chorus|quartet|trio|singers|musicians|group|foundation)\b", re.IGNORECASE)


class PdfAcquisitionError(RuntimeError):
    """A deterministic PDF acquisition or merge failure."""


def _safe_cache_name(source_url: str) -> str:
    path_name = Path(unquote(urlparse(source_url).path)).name or "source.pdf"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(path_name).stem).strip("-") or "source"
    url_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    return f"{stem}-{url_hash}.pdf"


def download_pdf(
    source_url: str,
    cache_dir: Path,
    *,
    timeout_seconds: int = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
    session: Any = requests,
) -> dict[str, Any]:
    """Fetch one known official PDF, validate it, cache it, and fingerprint it."""
    if not isinstance(source_url, str) or not source_url.startswith(("http://", "https://")):
        raise PdfAcquisitionError("PDF source_url must be an absolute HTTP(S) URL")
    if timeout_seconds <= 0:
        raise PdfAcquisitionError("PDF download timeout must be positive")

    try:
        response = session.get(
            source_url,
            timeout=timeout_seconds,
            headers={"User-Agent": "Byelingua deterministic PDF acquisition/2.0"},
        )
        response.raise_for_status()
        payload = bytes(response.content)
    except requests.RequestException as exc:
        raise PdfAcquisitionError(f"official PDF download failed: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise PdfAcquisitionError(f"official PDF response body is not bytes: {exc}") from exc

    if not payload.startswith(PDF_MAGIC):
        raise PdfAcquisitionError("official PDF response is missing the %PDF- header")

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / _safe_cache_name(source_url)
    cache_path.write_bytes(payload)
    sha256 = hashlib.sha256(payload).hexdigest()

    try:
        page_count = _pdf_page_count(cache_path)
    except Exception as exc:
        raise PdfAcquisitionError(f"cached PDF page count failed: {exc}") from exc

    return {
        "source_url": source_url,
        "path": str(cache_path),
        "sha256": sha256,
        "byte_size": len(payload),
        "page_count": page_count,
    }


def _pdf_page_count(path: Path) -> int:
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        return len(pdf.pages)


def _words_to_lines(words: list[dict[str, Any]], *, page: int, column: int) -> list[dict[str, Any]]:
    """Rebuild source-layout lines and retain enough font evidence for parsing."""
    grouped: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (float(item.get("top", 0)), float(item.get("x0", 0)))):
        if not grouped or abs(float(word.get("top", 0)) - float(grouped[-1][0].get("top", 0))) > 1.5:
            grouped.append([word])
        else:
            grouped[-1].append(word)
    lines = []
    for group in grouped:
        ordered = sorted(group, key=lambda item: float(item.get("x0", 0)))
        text = " ".join(str(item.get("text", "")) for item in ordered).strip()
        if not text:
            continue
        bold_count = sum("bold" in str(item.get("fontname", "")).casefold() for item in ordered)
        lines.append(
            {
                "page": page,
                "column": column,
                "text": text,
                "words": [
                    {
                        "text": str(item.get("text", "")),
                        "bold": "bold" in str(item.get("fontname", "")).casefold(),
                        "italic": "italic" in str(item.get("fontname", "")).casefold(),
                    }
                    for item in ordered
                ],
                "bold_ratio": bold_count / len(ordered),
            }
        )
    return lines


def extract_pdf_pages(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract page text without OCR and retain immutable page provenance."""
    path = Path(str(artifact["path"]))
    source_url = str(artifact["source_url"])
    pdf_sha256 = str(artifact["sha256"])
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages = []
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                meaningful = bool(" ".join(text.split()))
                # Barbican's listings are a flowing two-column layout.  The
                # default extractor interleaves both columns by y-coordinate,
                # which can separate a title from its date.  Preserve a
                # geometry-aware reading stream for deterministic segmentation
                # while retaining the original page text above.
                midpoint = page.width / 2
                columns = []
                for column_index, bbox in enumerate(
                    ((0, 0, midpoint, page.height), (midpoint, 0, page.width, page.height)),
                    start=1,
                ):
                    cropped = page.crop(bbox)
                    column_text = cropped.extract_text() or ""
                    if " ".join(column_text.split()):
                        words = cropped.extract_words(extra_attrs=["fontname", "size"])
                        columns.append(
                            {
                                "column": column_index,
                                "text": column_text,
                                "lines": _words_to_lines(words, page=index, column=column_index),
                            }
                        )
                pages.append(
                    {
                        "page": index,
                        "text": text if meaningful else "",
                        "status": "TEXT_OK" if meaningful else "TEXT_EMPTY",
                        "source_url": source_url,
                        "pdf_sha256": pdf_sha256,
                        "columns": columns,
                    }
                )
            return pages
    except Exception as exc:
        raise PdfAcquisitionError(f"PDF text extraction failed: {exc}") from exc


def _fallback_lines(page: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "page": page["page"],
            "column": 1,
            "text": line.strip(),
            "words": [],
            "bold_ratio": 0.0,
        }
        for line in str(page.get("text") or "").splitlines()
        if line.strip()
    ]


def _parse_occurrence_marker(text: str) -> dict[str, Any] | None:
    normalized = " ".join(text.replace("\u00a0", " ").split())
    if not normalized:
        return None
    match = _DATE_LINE_RE.match(normalized)
    if not match:
        if _DATE_RANGE_RE.search(normalized):
            return {"kind": "range", "text": text}
        return None
    try:
        event_date = datetime.strptime(
            f"{match.group('day')} {match.group('month')} {match.group('year')}",
            "%d %b %Y",
        ).date().isoformat()
    except ValueError:
        return None
    rest = match.group("rest") or ""
    times = []
    for time_match in _TIME_RE.finditer(rest):
        hour = int(time_match.group("hour"))
        minute = int(time_match.group("minute") or "00")
        if time_match.group("ampm").casefold() == "pm" and hour != 12:
            hour += 12
        if time_match.group("ampm").casefold() == "am" and hour == 12:
            hour = 0
        times.append(f"{hour:02d}:{minute:02d}")
    room = None
    if times:
        last_time = list(_TIME_RE.finditer(rest))[-1]
        room_text = re.sub(r"^[\s,&]+", "", rest[last_time.end():]).strip()
        room = room_text or None
    return {"kind": "single", "date": event_date, "times": times, "room": room, "text": text}


def segment_event_blocks(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Segment the Barbican's flowing two-column text at explicit date lines."""
    blocks: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for page in pages:
        columns = page.get("columns") or [{"column": 1, "lines": _fallback_lines(page)}]
        for column in columns:
            lines = column.get("lines") or _fallback_lines({**page, "text": column.get("text", "")})
            for line in lines:
                marker = _parse_occurrence_marker(str(line.get("text") or ""))
                pending.append(line)
                if marker is None:
                    continue
                raw_text = "\n".join(str(item.get("text") or "") for item in pending).strip()
                blocks.append(
                    {
                        "block_index": len(blocks) + 1,
                        "kind": marker["kind"],
                        "date": marker.get("date"),
                        "times": marker.get("times", []),
                        "room": marker.get("room"),
                        "pdf_page": int(line.get("page") or page["page"]),
                        "pdf_pages": sorted({int(item.get("page") or page["page"]) for item in pending}),
                        "source_url": page["source_url"],
                        "pdf_sha256": page.get("pdf_sha256"),
                        "raw_text": raw_text,
                        "lines": pending,
                    }
                )
                pending = []
    return blocks


def _line_text(line: dict[str, Any]) -> str:
    return " ".join(str(line.get("text") or "").split()).strip()


def _is_header_line(text: str) -> bool:
    return bool(
        _MONTH_HEADER_RE.match(text)
        or text.casefold() in {"classical music 2026-27", "event listings", "performers", "creative team"}
        or text.casefold().startswith(("details current", "on sale at"))
    )


def _line_lead_and_tail(line: dict[str, Any]) -> tuple[str, str, bool]:
    words = line.get("words") or []
    if not words:
        return "", _line_text(line), False
    lead: list[str] = []
    tail: list[str] = []
    saw_regular = False
    for word in words:
        value = str(word.get("text") or "")
        if not saw_regular and bool(word.get("bold")):
            lead.append(value)
        else:
            saw_regular = True
            tail.append(value)
    return " ".join(lead).strip(), " ".join(tail).strip(), bool(lead)


def _title_from_block(body: list[dict[str, Any]]) -> tuple[str | None, int]:
    candidates = [
        (index, _line_text(line))
        for index, line in enumerate(body)
        if _line_text(line) and not _is_header_line(_line_text(line))
    ]
    if not candidates:
        return None, -1
    index, title = candidates[0]
    title_parts = [title]
    if index + 1 < len(body):
        next_text = _line_text(body[index + 1])
        if next_text and (
            title.endswith((":", "/"))
            or float(body[index + 1].get("bold_ratio", 0)) >= 0.75
        ) and len(title) < 100:
            title_parts.append(next_text)
    return " ".join(title_parts).strip(), index


def _role_function(role: str) -> str:
    normalized = " ".join(role.casefold().split())
    if "conductor" in normalized:
        return "conductor"
    if "director" in normalized:
        return "director"
    if "composer" in normalized:
        return "composer"
    if any(token in normalized for token in ("soprano", "mezzo", "contralto", "countertenor", "tenor", "baritone", "bass", "vocal", "voice")):
        return "performer"
    if any(token in normalized for token in ("orchestra", "ensemble", "choir", "chorus", "quartet", "trio", "singers", "musicians")):
        return "ensemble"
    return "performer"


def _credit_kind(function: str) -> str:
    if function in {"conductor", "director", "composer"}:
        return "artistic_team"
    if function == "ensemble":
        return "ensemble"
    return "cast"


def _parse_programme_line(line: dict[str, Any]) -> dict[str, Any] | None:
    text = _line_text(line)
    if not text or text.casefold() == "interval":
        return None
    lead, tail, has_bold_lead = _line_lead_and_tail(line)
    if not has_bold_lead or not tail:
        return None
    if _ROLE_RE.search(tail):
        return None
    if text.casefold().startswith(("a new ", "an evening ", "the ")) and len(text) > 45:
        return None
    return {
        "source_title": tail,
        "composer": lead or None,
        "provenance": {
            "source_field": "official.programme",
        },
    }


def _parse_credit_line(line: dict[str, Any]) -> dict[str, Any] | None:
    text = _line_text(line)
    if not text:
        return None
    lead, tail, has_bold_lead = _line_lead_and_tail(line)
    if has_bold_lead and tail and _ROLE_RE.search(tail):
        role = tail.strip()
        function = _role_function(role)
        return {
            "artist_name": lead,
            "source_role": role,
            "function": function,
            "credit_kind": _credit_kind(function),
            "source_field": "official.pdf.credit",
            "provenance": {"source_field": "official.pdf.credit"},
        }
    if float(line.get("bold_ratio", 0)) >= 0.75 and _ENSEMBLE_RE.search(text):
        return {
            "artist_name": text,
            "source_role": "ensemble",
            "function": "ensemble",
            "credit_kind": "ensemble",
            "source_field": "official.pdf.credit",
            "provenance": {"source_field": "official.pdf.credit"},
        }
    return None


def parse_deterministic_event_block(
    block: dict[str, Any],
    *,
    source_url: str,
) -> dict[str, Any] | None:
    """Parse one explicit-date block without using Hermes."""
    if block.get("kind") != "single" or not block.get("date"):
        return None
    body = list(block.get("lines") or [])[:-1]
    title, title_index = _title_from_block(body)
    if not title:
        return None
    programme: list[dict[str, Any]] = []
    credits: list[dict[str, Any]] = []
    for index, line in enumerate(body):
        if index <= title_index:
            continue
        row = _parse_programme_line(line)
        if row is not None:
            programme.append(row)
            continue
        credit = _parse_credit_line(line)
        if credit is not None:
            credits.append(credit)
            continue
        if programme and not line.get("words") and len(_line_text(line)) <= 45:
            continuation = _line_text(line)
            if continuation and programme[-1]["source_title"].endswith(("in", "of", "for", "from", "and", "No.")):
                programme[-1]["source_title"] += f" {continuation}"

    page = int(block["pdf_page"])
    pdf_sha256 = str(block.get("pdf_sha256") or "")
    for row in programme:
        row["provenance"].update({"source_url": source_url, "pdf_page": page})
        if pdf_sha256:
            row["provenance"]["pdf_sha256"] = pdf_sha256
    for row in credits:
        row["source_url"] = source_url
        row["provenance"].update({"source_url": source_url, "pdf_page": page})
        if pdf_sha256:
            row["provenance"]["pdf_sha256"] = pdf_sha256

    title_slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:40] or "event"
    events = []
    times = block.get("times") or [None]
    for occurrence_index, start_time in enumerate(times, start=1):
        source_event_id = f"pdf-{block['block_index']}-{block['date']}-{start_time or 'unknown'}-{title_slug}-{occurrence_index}"
        event = {
            "source_event_id": source_event_id,
            "source_url": source_url,
            "title": title,
            "date": block["date"],
            "start_time": start_time,
            "end_time": None,
            "room": block.get("room"),
            "event_type": "performance",
            "classification": "performance",
            "programme": copy.deepcopy(programme),
            "credits": copy.deepcopy(credits),
            "provenance": {
                "source_url": source_url,
                "pdf_page": page,
                "pdf_pages": block.get("pdf_pages", [page]),
                "pdf_sha256": pdf_sha256,
                "source_field": "official.pdf.event",
            },
            "raw_block_text": block.get("raw_text", ""),
            "data_quality": {
                "schedule": {"year_status": "YEAR_EXPLICIT", "source_field": "official.pdf.event"},
                "programme": {"status": "PROGRAMME_EVIDENCE_FOUND" if programme else "NO_PROGRAMME_EVIDENCE"},
            },
        }
        events.append(event)
    # The source-facts contract represents one event per occurrence.  The
    # caller expands multi-time blocks and receives a list below.
    return {"events": events}


def build_deterministic_source_facts(
    request: dict[str, Any],
    blocks: list[dict[str, Any]],
    *,
    pdf_source: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return deterministic facts and only the explicit-date residual blocks."""
    contract = copy.deepcopy(request.get("source_contract") or {})
    contract.update({"deterministic_pdf_parser": "v3", "pdf_source": copy.deepcopy(pdf_source)})
    facts: dict[str, Any] = {
        "schema_version": SOURCE_FACTS_SCHEMA_VERSION,
        "venue_id": request["venue_id"],
        "season": request["season"],
        "source_id": request.get("source_id", request["venue_id"]),
        "source_type": "html",
        "official_source_url": request["official_source_url"],
        "source_contract": contract,
        "events": [],
    }
    residual: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("kind") != "single":
            continue
        parsed = parse_deterministic_event_block(block, source_url=pdf_source["source_url"])
        if parsed is None:
            residual.append(block)
            continue
        facts["events"].extend(parsed["events"])
    from jobs.hermes_acquire_worker import _normalize_programme_order

    _normalize_programme_order(facts)
    validate_source_facts(facts)
    return facts, residual


def chunk_pdf_pages(
    pages: list[dict[str, Any]],
    *,
    max_pages: int = DEFAULT_MAX_CHUNK_PAGES,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    """Group complete pages into bounded chunks; never split a page."""
    if max_pages <= 0 or max_chars <= 0:
        raise PdfAcquisitionError("PDF chunk bounds must be positive")

    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current or not any(page.get("text") for page in current):
            current = []
            current_chars = 0
            return
        chunks.append(
            {
                "chunk_index": len(chunks) + 1,
                "pages": current,
                "page_start": current[0]["page"],
                "page_end": current[-1]["page"],
                "text": "\n\n".join(
                    f"[PDF PAGE {page['page']}]\n{page['text']}"
                    for page in current
                    if page.get("text")
                ),
                "char_count": sum(len(page.get("text") or "") for page in current),
            }
        )
        current = []
        current_chars = 0

    for page in pages:
        page_text = str(page.get("text") or "")
        proposed_chars = current_chars + len(page_text)
        if current and (len(current) >= max_pages or proposed_chars > max_chars):
            flush()
        current.append(page)
        current_chars += len(page_text)
    flush()
    return chunks


def build_pdf_chunk_prompt(
    request: dict[str, Any],
    chunk: dict[str, Any],
    *,
    pdf_source: dict[str, Any],
) -> str:
    """Ask Hermes to interpret only one bounded, already-downloaded chunk."""
    request_json = json.dumps(request, ensure_ascii=False, sort_keys=True)
    schema_text = json.dumps(SOURCE_FACTS_SCHEMA, ensure_ascii=False, sort_keys=True)
    pages_json = json.dumps(
        [
            {
                "page": page["page"],
                "source_url": page["source_url"],
                "pdf_sha256": page["pdf_sha256"],
                "status": page["status"],
            }
            for page in chunk["pages"]
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"""You are the Byelingua Hermes deterministic PDF chunk extractor.

Do not use Browser Automation, computer use, web search, network access,
Supabase, databases, or production writers. The official PDF is already
downloaded and verified. Interpret only the bounded extracted text enclosed
below. Do not ask for, fetch, or infer facts from any other page or chunk.

Return one JSON object using the existing {SOURCE_FACTS_SCHEMA_VERSION}
source-facts contract. This is a partial chunk response: events may be an
empty array when this chunk contains no explicit occurrences. The final merge
will require non-empty events. Top-level source_type must be exactly "html"
because the existing contract allows only "api" or "html"; do not invent a
new source type for PDF.

Only emit source-supported facts present in this chunk. An event may be
created only when this chunk contains an explicit individual occurrence date;
do not turn a season range, production run, premiere, or month heading into
an individual performance. Preserve the explicit date and time. Every event
must have a non-empty source-supported title; do not invent titles.

The exact PDF source URL is <pdf_source_url>{pdf_source['source_url']}</pdf_source_url>.
For every event, programme row, and credit extracted from the PDF, put the
exact PDF URL in source_url/provenance as applicable, put the 1-based page in
provenance.pdf_page, and put the source field in provenance.source_field.
Use existing programme evidence fields such as official.programme,
official.works, official.program, official.repertoire, official.music, or
official.detail.music. Use source_field values such as official.pdf.event or
official.pdf.credit for event/credit provenance. Never omit page evidence.

For opera/concert listings, a work or production title is programme evidence
only when the PDF explicitly associates it with the occurrence. Copy the
exact source title. Copy a composer only when the PDF explicitly names one;
otherwise preserve the work title and omit composer. Never invent a work,
composer, date, time, artist, or role.

Return JSON only. No markdown or explanation.

<acquisition_request_json>
{request_json}
</acquisition_request_json>
<pdf_source_record>
{json.dumps(pdf_source, ensure_ascii=False, sort_keys=True)}
</pdf_source_record>
<chunk_pages>
{pages_json}
</chunk_pages>
<extracted_pdf_text>
{chunk['text']}
</extracted_pdf_text>
<existing_source_facts_contract>
{schema_text}
</existing_source_facts_contract>
"""


def acquire_pdf_chunk_facts(
    request: dict[str, Any],
    chunk: dict[str, Any],
    *,
    pdf_source: dict[str, Any],
    timeout_seconds: int = DEFAULT_CHUNK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run Hermes once for one chunk and validate its partial contract."""
    prompt = build_pdf_chunk_prompt(request, chunk, pdf_source=pdf_source)
    raw = _run_hermes(prompt, timeout_seconds=timeout_seconds)
    return _parse_and_validate(
        raw,
        validate_source_facts,
        require_nonempty_events=False,
    )


def build_residual_block_prompt(
    request: dict[str, Any],
    block: dict[str, Any],
    *,
    source_url: str,
    max_chars: int = 3_000,
) -> str:
    """Build a strictly bounded no-browser prompt for one unresolved block."""
    if max_chars < 800:
        raise PdfAcquisitionError("residual Hermes prompt bound is too small")
    compact_request = json.dumps(
        {
            "venue_id": request["venue_id"],
            "season": request["season"],
            "source_id": request.get("source_id", request["venue_id"]),
            "official_source_url": source_url,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    prefix = (
        "Structure only this one ambiguous extracted PDF event block. "
        "No Browser Automation, web search, network, PDF download, Supabase, "
        "or production writes. Do not invent dates, titles, works, or credits. "
        "Return JSON only using hermes-source-facts-v1 with source_type=html; "
        "events may be empty if the block cannot be resolved. Preserve "
        "source_url, pdf_page, and source_field provenance.\n"
        f"REQUEST={compact_request}\n"
        f"PDF_PAGE={block.get('pdf_page')}\n"
        f"SOURCE_URL={source_url}\n"
        "BLOCK=\n"
    )
    suffix = "\nEND BLOCK"
    available = max_chars - len(prefix) - len(suffix)
    if available <= 0:
        raise PdfAcquisitionError("residual Hermes prompt metadata exceeds bound")
    raw_block = str(block.get("raw_text") or "")
    bounded_block = raw_block if len(raw_block) <= available else raw_block[: max(0, available - 20)] + "\n[TRUNCATED]"
    prompt = prefix + bounded_block + suffix
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars]
    return prompt


def acquire_residual_block_facts(
    request: dict[str, Any],
    block: dict[str, Any],
    *,
    source_url: str,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Ask Hermes about one unresolved block; caller may downgrade failure to review."""
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise PdfAcquisitionError("residual Hermes timeout must be between 1 and 120 seconds")
    prompt = build_residual_block_prompt(request, block, source_url=source_url)
    raw = _run_hermes(prompt, timeout_seconds=timeout_seconds)
    return _parse_and_validate(raw, validate_source_facts, require_nonempty_events=False)


def _fact_provenance(value: dict[str, Any]) -> dict[str, Any]:
    provenance = value.get("provenance")
    return provenance if isinstance(provenance, dict) else {}


def _text_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _event_key(event: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(event.get("date") or ""),
        str(event.get("start_time") or ""),
        _text_key(event.get("title")),
        str(event.get("source_url") or ""),
        _text_key(event.get("room")),
    )


def _row_key(row: dict[str, Any], *, kind: str) -> tuple[str, ...]:
    provenance = _fact_provenance(row)
    if kind == "programme":
        return (
            _text_key(row.get("source_title")),
            _text_key(row.get("composer")),
            str(provenance.get("source_url") or row.get("source_url") or ""),
            str(provenance.get("pdf_page") or ""),
            str(provenance.get("source_field") or ""),
        )
    return (
        _text_key(row.get("artist_name")),
        _text_key(row.get("source_role")),
        _text_key(row.get("function")),
        _text_key(row.get("credit_kind")),
        _text_key(row.get("character")),
        str(row.get("source_url") or provenance.get("source_url") or ""),
        str(provenance.get("pdf_page") or ""),
    )


def _add_pdf_page_provenance(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    target_provenance = _fact_provenance(target)
    incoming_provenance = _fact_provenance(incoming)
    if not target_provenance and incoming_provenance:
        target["provenance"] = copy.deepcopy(incoming_provenance)
        target_provenance = target["provenance"]
    pages = []
    for value in (target_provenance.get("pdf_page"), incoming_provenance.get("pdf_page")):
        if isinstance(value, int) and value > 0 and value not in pages:
            pages.append(value)
    if pages:
        target_provenance["pdf_page"] = min(pages)
        if len(pages) > 1:
            target_provenance["pdf_pages"] = sorted(pages)


def _ensure_pdf_provenance(value: dict[str, Any], pdf_source: dict[str, Any]) -> None:
    """Attach immutable PDF evidence to an event or nested source fact."""
    provenance = _fact_provenance(value)
    provenance.setdefault("source_url", value.get("source_url") or pdf_source.get("source_url"))
    provenance.setdefault("pdf_sha256", pdf_source.get("sha256"))
    value["provenance"] = provenance


def merge_pdf_chunk_facts(
    partials: list[dict[str, Any]],
    *,
    request: dict[str, Any],
    pdf_source: dict[str, Any],
    source_mode: str = PDF_SOURCE_MODE,
) -> dict[str, Any]:
    """Merge partial source facts deterministically into the existing contract."""
    if not partials:
        raise PdfAcquisitionError("no PDF chunk facts were returned")
    for partial in partials:
        validate_source_facts(partial)

    contract = copy.deepcopy(request.get("source_contract") or {})
    contract["pdf_source_mode"] = source_mode
    contract["pdf_sources"] = [copy.deepcopy(pdf_source)]
    merged: dict[str, Any] = {
        "schema_version": SOURCE_FACTS_SCHEMA_VERSION,
        "venue_id": request["venue_id"],
        "season": request["season"],
        "source_id": request.get("source_id", request["venue_id"]),
        "source_type": "html",
        "official_source_url": request["official_source_url"],
        "source_contract": contract,
        "events": [],
    }
    event_index: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for partial in partials:
        for raw_event in partial.get("events", []):
            event = copy.deepcopy(raw_event)
            _ensure_pdf_provenance(event, pdf_source)
            for row in event.get("programme", []):
                _ensure_pdf_provenance(row, pdf_source)
            for row in event.get("credits", []):
                _ensure_pdf_provenance(row, pdf_source)
            key = _event_key(event)
            existing = event_index.get(key)
            if existing is None:
                event_index[key] = event
                merged["events"].append(event)
                continue
            _add_pdf_page_provenance(existing, event)
            _ensure_pdf_provenance(existing, pdf_source)
            for collection_name, kind in (("programme", "programme"), ("credits", "credit")):
                rows = existing.setdefault(collection_name, [])
                seen = {_row_key(row, kind=kind) for row in rows}
                for row in event.get(collection_name, []):
                    row_key = _row_key(row, kind=kind)
                    if row_key not in seen:
                        row_copy = copy.deepcopy(row)
                        _ensure_pdf_provenance(row_copy, pdf_source)
                        rows.append(row_copy)
                        seen.add(row_key)

    if not merged["events"]:
        raise PdfAcquisitionError("merged PDF source facts contain no explicit events")

    from jobs.hermes_acquire_worker import _normalize_programme_order

    _normalize_programme_order(merged)
    try:
        validate_source_facts(merged)
    except Exception as exc:
        raise PdfAcquisitionError(f"merged PDF source facts failed validation: {exc}") from exc
    return merged
