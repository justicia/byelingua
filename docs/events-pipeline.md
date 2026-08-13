# Automated event ingestion

The production event source of truth is Supabase. GitHub stores adapters,
normalization, validation, tests, and application code; raw scrape output and
production datasets are not committed.

## Current safe commands

Run the existing local fixtures without network access or production writes:

```bash
./.venv/bin/python -m events_pipeline ingest --source wiener_musikverein
./.venv/bin/python -m events_pipeline ingest --city Vienna
./.venv/bin/python -m events_pipeline ingest --all
```

Reports are written to `reports/ingestion/` and are git-ignored. Records that
fail hard validation are quarantined in the report. The current first adapter
layer only accepts stable JSON-LD event identities; it refuses to guess from
generic headings.

`--write-production` is intentionally disabled until the source-specific
Supabase upsert adapter and post-import verification are reviewed. This keeps
the pipeline idempotent and prevents a generic parser from writing bad events.

## Required production upsert contract

The next implementation step is an entity-first, source-identity upsert:

1. organization and canonical venue
2. works and artists
3. event occurrence keyed by `event_sources(source, source_event_id)`
4. programme and credits
5. source provenance and last-seen timestamps

Each run must report inserted, updated, unchanged, quarantined, and failed
records. Missing events must be marked through last-seen/status logic and never
deleted automatically.
