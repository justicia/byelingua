from __future__ import annotations

import difflib
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIG
# ============================================================

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "",
).strip().rstrip("/")

SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "",
).strip()

INPUT_FILE = "paris-opera-programme-dry-run.json"

OUTPUT_FILE = (
    "paris-opera-programme-match-dry-run.json"
)

PAGE_SIZE = 1000

FUZZY_THRESHOLD = 0.82


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_space(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def norm(value: str) -> str:
    value = normalize_space(value)

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        ch
        for ch in value
        if not unicodedata.combining(ch)
    )

    value = (
        value
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )

    return value.casefold()


DURATION_SUFFIX_RE = re.compile(
    r"\s*\("
    r"\s*\d+"
    r"(?:\s*[’']\s*\d*)?"
    r"\s*\)"
    r"\s*$"
)


def clean_work_title(
    value: str,
) -> str:
    value = normalize_space(value)

    previous = None

    while previous != value:
        previous = value

        value = DURATION_SUFFIX_RE.sub(
            "",
            value,
        ).strip()

    return value


def title_keys(
    value: str,
) -> set[str]:
    raw = normalize_space(value)
    clean = clean_work_title(value)

    keys = {
        norm(raw),
        norm(clean),
    }

    return {
        key
        for key in keys
        if key
    }


# ============================================================
# ENVIRONMENT / SUPABASE
# ============================================================

def validate_environment() -> None:
    if not SUPABASE_URL:
        raise RuntimeError(
            "Missing SUPABASE_URL."
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "Missing SUPABASE_SERVICE_ROLE_KEY."
        )

    if SUPABASE_URL == "[SENSITIVE]":
        raise RuntimeError(
            "SUPABASE_URL contains "
            "Vercel placeholder."
        )

    if SUPABASE_KEY == "[SENSITIVE]":
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY contains "
            "Vercel placeholder."
        )


def supabase_get_all(
    path: str,
    select: str,
):
    rows = []
    offset = 0

    while True:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            params={
                "select": select,
                "limit": PAGE_SIZE,
                "offset": offset,
            },
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization":
                    f"Bearer {SUPABASE_KEY}",
            },
            timeout=60,
        )

        response.raise_for_status()

        batch = response.json()

        rows.extend(batch)

        if len(batch) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return rows


# ============================================================
# INPUT
# ============================================================

def load_parser_report():
    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
    ) as fh:
        return json.load(fh)


# ============================================================
# MASTER DATA
# ============================================================

def load_master_data():
    print(
        "Loading Composer / Work master..."
    )

    composers = supabase_get_all(
        "composers",
        (
            "id,canonical_name,"
            "identity_key"
        ),
    )

    composer_aliases = supabase_get_all(
        "composer_aliases",
        (
            "composer_id,alias,"
            "language,source"
        ),
    )

    works = supabase_get_all(
        "works",
        (
            "id,title,composer_id,"
            "identity_key,"
            "normalization_status"
        ),
    )

    work_aliases = supabase_get_all(
        "work_aliases",
        (
            "work_id,alias,"
            "language,source"
        ),
    )

    work_creators = supabase_get_all(
        "work_creators",
        (
            "work_id,composer_id,"
            "creator_role,is_primary"
        ),
    )

    queue = supabase_get_all(
        "canonical_rebuild_source_programme_queue",
        (
            "source_url,event_ids,"
            "event_count,status"
        ),
    )

    return {
        "composers":
            composers,
        "composer_aliases":
            composer_aliases,
        "works":
            works,
        "work_aliases":
            work_aliases,
        "work_creators":
            work_creators,
        "queue":
            queue,
    }


# ============================================================
# INDEXES
# ============================================================

def build_indexes(master):
    composers = master[
        "composers"
    ]

    composer_aliases = master[
        "composer_aliases"
    ]

    works = master[
        "works"
    ]

    work_aliases = master[
        "work_aliases"
    ]

    work_creators = master[
        "work_creators"
    ]

    queue = master[
        "queue"
    ]

    composer_by_id = {
        row["id"]: row
        for row in composers
    }

    composer_names = defaultdict(
        list
    )

    for row in composers:
        name = row.get(
            "canonical_name"
        )

        if name:
            composer_names[
                norm(name)
            ].append(
                {
                    "composer_id":
                        row["id"],
                    "canonical_name":
                        name,
                    "method":
                        "canonical_name",
                }
            )

    for row in composer_aliases:
        alias = row.get("alias")

        composer_id = row.get(
            "composer_id"
        )

        composer = composer_by_id.get(
            composer_id
        )

        if (
            alias
            and composer
        ):
            composer_names[
                norm(alias)
            ].append(
                {
                    "composer_id":
                        composer_id,
                    "canonical_name":
                        composer[
                            "canonical_name"
                        ],
                    "method":
                        "composer_alias",
                }
            )

    work_by_id = {
        row["id"]: row
        for row in works
    }

    creator_ids_by_work = (
        defaultdict(set)
    )

    for work in works:
        composer_id = work.get(
            "composer_id"
        )

        if composer_id:
            creator_ids_by_work[
                work["id"]
            ].add(
                composer_id
            )

    for row in work_creators:
        work_id = row.get(
            "work_id"
        )

        composer_id = row.get(
            "composer_id"
        )

        if (
            work_id
            and composer_id
        ):
            creator_ids_by_work[
                work_id
            ].add(
                composer_id
            )

    title_index = defaultdict(
        set
    )

    title_method = {}

    for work in works:
        work_id = work["id"]

        for key in title_keys(
            work.get(
                "title",
                "",
            )
        ):
            title_index[
                key
            ].add(
                work_id
            )

            title_method[
                (
                    work_id,
                    key,
                )
            ] = "canonical_title"

    for alias_row in work_aliases:
        work_id = alias_row.get(
            "work_id"
        )

        alias = alias_row.get(
            "alias"
        )

        if (
            not work_id
            or not alias
        ):
            continue

        if work_id not in work_by_id:
            continue

        for key in title_keys(
            alias
        ):
            title_index[
                key
            ].add(
                work_id
            )

            title_method[
                (
                    work_id,
                    key,
                )
            ] = "work_alias"

    queue_by_url = {
        row["source_url"]: row
        for row in queue
        if row.get("source_url")
    }

    works_by_creator = (
        defaultdict(set)
    )

    for work_id, creator_ids in (
        creator_ids_by_work.items()
    ):
        for composer_id in (
            creator_ids
        ):
            works_by_creator[
                composer_id
            ].add(
                work_id
            )

    return {
        "composer_by_id":
            composer_by_id,
        "composer_names":
            composer_names,
        "work_by_id":
            work_by_id,
        "creator_ids_by_work":
            creator_ids_by_work,
        "title_index":
            title_index,
        "title_method":
            title_method,
        "queue_by_url":
            queue_by_url,
        "works_by_creator":
            works_by_creator,
    }


# ============================================================
# COMPOSER MATCHING
# ============================================================

def composer_suggestions(
    raw_name: str,
    indexes,
):
    target = norm(raw_name)

    if not target:
        return []

    candidates = []

    seen = set()

    for (
        key,
        matches,
    ) in indexes[
        "composer_names"
    ].items():
        score = difflib.SequenceMatcher(
            None,
            target,
            key,
        ).ratio()

        if score < FUZZY_THRESHOLD:
            continue

        for match in matches:
            composer_id = match[
                "composer_id"
            ]

            if composer_id in seen:
                continue

            seen.add(
                composer_id
            )

            candidates.append(
                {
                    "composer_id":
                        composer_id,
                    "canonical_name":
                        match[
                            "canonical_name"
                        ],
                    "score":
                        round(
                            score,
                            4,
                        ),
                }
            )

    candidates.sort(
        key=lambda row:
            row["score"],
        reverse=True,
    )

    return candidates[:3]


def resolve_composer(
    raw_name: str,
    indexes,
):
    key = norm(raw_name)

    matches = indexes[
        "composer_names"
    ].get(
        key,
        [],
    )

    unique = {}

    for match in matches:
        unique[
            match["composer_id"]
        ] = match

    matches = list(
        unique.values()
    )

    if len(matches) == 1:
        match = matches[0]

        return {
            "raw_name":
                raw_name,
            "status":
                "matched",
            "composer_id":
                match[
                    "composer_id"
                ],
            "canonical_name":
                match[
                    "canonical_name"
                ],
            "method":
                match[
                    "method"
                ],
            "suggestions":
                [],
        }

    if len(matches) > 1:
        return {
            "raw_name":
                raw_name,
            "status":
                "ambiguous",
            "composer_id":
                None,
            "canonical_name":
                None,
            "method":
                None,
            "suggestions":
                [
                    {
                        "composer_id":
                            row[
                                "composer_id"
                            ],
                        "canonical_name":
                            row[
                                "canonical_name"
                            ],
                    }
                    for row
                    in matches
                ],
        }

    return {
        "raw_name":
            raw_name,
        "status":
            "unmatched",
        "composer_id":
            None,
        "canonical_name":
            None,
        "method":
            None,
        "suggestions":
            composer_suggestions(
                raw_name,
                indexes,
            ),
    }


# ============================================================
# WORK MATCHING
# ============================================================

def work_payload(
    work_id: str,
    indexes,
    matched_key: str | None = None,
):
    work = indexes[
        "work_by_id"
    ][work_id]

    creator_ids = sorted(
        indexes[
            "creator_ids_by_work"
        ].get(
            work_id,
            set(),
        )
    )

    creators = []

    for composer_id in creator_ids:
        composer = indexes[
            "composer_by_id"
        ].get(
            composer_id
        )

        if composer:
            creators.append(
                {
                    "composer_id":
                        composer_id,
                    "canonical_name":
                        composer[
                            "canonical_name"
                        ],
                }
            )

    match_method = None

    if matched_key:
        match_method = indexes[
            "title_method"
        ].get(
            (
                work_id,
                matched_key,
            )
        )

    return {
        "work_id":
            work_id,
        "canonical_title":
            work.get("title"),
        "identity_key":
            work.get(
                "identity_key"
            ),
        "normalization_status":
            work.get(
                "normalization_status"
            ),
        "title_match_method":
            match_method,
        "creators":
            creators,
    }


def exact_title_candidates(
    raw_title: str,
    indexes,
):
    candidates = {}

    for key in title_keys(
        raw_title
    ):
        for work_id in indexes[
            "title_index"
        ].get(
            key,
            set(),
        ):
            candidates[
                work_id
            ] = key

    return candidates


def fuzzy_work_suggestions(
    raw_title: str,
    allowed_work_ids,
    indexes,
):
    target = norm(
        clean_work_title(
            raw_title
        )
    )

    if not target:
        return []

    suggestions = []

    for work_id in allowed_work_ids:
        work = indexes[
            "work_by_id"
        ].get(
            work_id
        )

        if not work:
            continue

        candidate = norm(
            work.get(
                "title",
                "",
            )
        )

        if not candidate:
            continue

        score = difflib.SequenceMatcher(
            None,
            target,
            candidate,
        ).ratio()

        if score < FUZZY_THRESHOLD:
            continue

        suggestions.append(
            {
                "work_id":
                    work_id,
                "canonical_title":
                    work.get("title"),
                "score":
                    round(
                        score,
                        4,
                    ),
            }
        )

    suggestions.sort(
        key=lambda row:
            row["score"],
        reverse=True,
    )

    return suggestions[:5]


def match_work(
    raw_title: str,
    composer_matches,
    indexes,
):
    resolved_composer_ids = {
        row["composer_id"]
        for row in composer_matches
        if (
            row["status"]
            == "matched"
            and row[
                "composer_id"
            ]
        )
    }

    title_candidates = (
        exact_title_candidates(
            raw_title,
            indexes,
        )
    )

    # --------------------------------
    # Exact Work title + creator match
    # --------------------------------

    compatible = {}

    for (
        work_id,
        matched_key,
    ) in title_candidates.items():
        work_creator_ids = indexes[
            "creator_ids_by_work"
        ].get(
            work_id,
            set(),
        )

        if not resolved_composer_ids:
            continue

        if (
            resolved_composer_ids
            .issubset(
                work_creator_ids
            )
        ):
            compatible[
                work_id
            ] = matched_key

    if len(compatible) == 1:
        (
            work_id,
            matched_key,
        ) = next(
            iter(
                compatible.items()
            )
        )

        return {
            "status":
                "matched_verified",
            "confidence":
                "high",
            "match_method":
                "composer_and_exact_title",
            "proposed_work":
                work_payload(
                    work_id,
                    indexes,
                    matched_key,
                ),
            "candidate_works":
                [],
            "notes":
                None,
        }

    if len(compatible) > 1:
        return {
            "status":
                "work_ambiguous",
            "confidence":
                "review",
            "match_method":
                "multiple_exact_matches",
            "proposed_work":
                None,
            "candidate_works":
                [
                    work_payload(
                        work_id,
                        indexes,
                        matched_key,
                    )
                    for (
                        work_id,
                        matched_key,
                    )
                    in compatible.items()
                ],
            "notes":
                (
                    "Multiple canonical Works "
                    "match title and creator."
                ),
        }

    # --------------------------------
    # Exact title globally, but creator
    # differs / composer unresolved.
    # --------------------------------

    if title_candidates:
        return {
            "status":
                "title_match_review",
            "confidence":
                "review",
            "match_method":
                "exact_title_creator_unverified",
            "proposed_work":
                None,
            "candidate_works":
                [
                    work_payload(
                        work_id,
                        indexes,
                        matched_key,
                    )
                    for (
                        work_id,
                        matched_key,
                    )
                    in title_candidates.items()
                ],
            "notes":
                (
                    "Exact Work title exists, "
                    "but Composer/creator "
                    "relationship could not be "
                    "verified automatically."
                ),
        }

    # --------------------------------
    # No exact Work.
    # Fuzzy suggestions are REVIEW ONLY.
    # --------------------------------

    allowed_work_ids = set()

    for composer_id in (
        resolved_composer_ids
    ):
        allowed_work_ids.update(
            indexes[
                "works_by_creator"
            ].get(
                composer_id,
                set(),
            )
        )

    suggestions = (
        fuzzy_work_suggestions(
            raw_title,
            allowed_work_ids,
            indexes,
        )
        if allowed_work_ids
        else []
    )

    return {
        "status":
            "work_unmatched",
        "confidence":
            "review",
        "match_method":
            None,
        "proposed_work":
            None,
        "candidate_works":
            suggestions,
        "notes":
            (
                "No exact canonical Work "
                "match. No Work is created "
                "automatically."
            ),
    }


# ============================================================
# ITEM ROUTER
# ============================================================

def contains_compound_composer_string(
    raw_composers,
):
    return any(
        "," in value
        for value in raw_composers
    )


def process_item(
    page,
    item,
    indexes,
):
    source_url = page[
        "source_url"
    ]

    queue_row = indexes[
        "queue_by_url"
    ].get(
        source_url,
        {},
    )

    raw_composers = [
        normalize_space(value)
        for value
        in item.get(
            "raw_composers",
            [],
        )
        if normalize_space(value)
    ]

    composer_matches = [
        resolve_composer(
            raw_name,
            indexes,
        )
        for raw_name
        in raw_composers
    ]

    # Source gave a single comma-separated
    # list of several creators.
    #
    # Never silently split this because names
    # such as surname/given-name forms may also
    # contain commas in other sources.

    if contains_compound_composer_string(
        raw_composers
    ):
        work_match = {
            "status":
                "multi_composer_source_review",
            "confidence":
                "review",
            "match_method":
                None,
            "proposed_work":
                None,
            "candidate_works":
                [],
            "notes":
                (
                    "Source music credit contains "
                    "a comma-delimited creator "
                    "string. Manual normalization "
                    "required."
                ),
        }

    elif any(
        row["status"]
        != "matched"
        for row
        in composer_matches
    ):
        # Still look for an exact Work title,
        # but never mark it verified.

        title_candidates = (
            exact_title_candidates(
                item["raw_title"],
                indexes,
            )
        )

        work_match = {
            "status":
                "composer_review_required",
            "confidence":
                "review",
            "match_method":
                None,
            "proposed_work":
                None,
            "candidate_works":
                [
                    work_payload(
                        work_id,
                        indexes,
                        matched_key,
                    )
                    for (
                        work_id,
                        matched_key,
                    )
                    in title_candidates.items()
                ],
            "notes":
                (
                    "At least one source Composer "
                    "could not be resolved exactly."
                ),
        }

    else:
        work_match = match_work(
            item["raw_title"],
            composer_matches,
            indexes,
        )

    return {
        "source_url":
            source_url,
        "event_type":
            page.get(
                "event_type"
            ),
        "source_titles":
            page.get(
                "source_titles"
            )
            or [],
        "event_ids":
            queue_row.get(
                "event_ids"
            )
            or [],
        "event_count":
            queue_row.get(
                "event_count"
            )
            or page.get(
                "event_count"
            )
            or 0,
        "programme_order":
            item.get(
                "order"
            ),
        "raw_title":
            item.get(
                "raw_title"
            ),
        "clean_title":
            clean_work_title(
                item.get(
                    "raw_title",
                    "",
                )
            ),
        "raw_composers":
            raw_composers,
        "composer_matches":
            composer_matches,
        **work_match,
    }


# ============================================================
# REPORT
# ============================================================

def main():
    validate_environment()

    parser_report = (
        load_parser_report()
    )

    master = load_master_data()

    indexes = build_indexes(
        master
    )

    results = []

    for page in parser_report[
        "pages"
    ]:
        if not page.get("ok"):
            continue

        for item in page.get(
            "items",
            []
        ):
            results.append(
                process_item(
                    page,
                    item,
                    indexes,
                )
            )

    status_counts = Counter(
        row["status"]
        for row in results
    )

    composer_status_counts = (
        Counter()
    )

    for row in results:
        for composer in row[
            "composer_matches"
        ]:
            composer_status_counts[
                composer["status"]
            ] += 1

    verified = [
        row
        for row in results
        if (
            row["status"]
            == "matched_verified"
        )
    ]

    review = [
        row
        for row in results
        if (
            row["status"]
            != "matched_verified"
        )
    ]

    report = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "source_parser_version":
            parser_report.get(
                "parser_version"
            ),
        "programme_items":
            len(results),
        "verified_matches":
            len(verified),
        "review_required":
            len(review),
        "status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),
        "composer_status_counts":
            dict(
                sorted(
                    composer_status_counts
                    .items()
                )
            ),
        "verified":
            verified,
        "review":
            review,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            report,
            fh,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "===== MATCH SUMMARY ====="
    )

    print(
        json.dumps(
            {
                "programme_items":
                    report[
                        "programme_items"
                    ],
                "verified_matches":
                    report[
                        "verified_matches"
                    ],
                "review_required":
                    report[
                        "review_required"
                    ],
                "status_counts":
                    report[
                        "status_counts"
                    ],
                "composer_status_counts":
                    report[
                        "composer_status_counts"
                    ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(
            "ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}",
            file=sys.stderr,
        )

        raise