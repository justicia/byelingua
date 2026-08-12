# Byelingua schedule lifecycle WIP handoff

- Baseline: `main@022f2ea` (`Fix bilingual schedule editing flow`)
- Branch: `schedule-lifecycle-wip`
- Purpose: preserve unfinished schedule lifecycle work only.
- The database migration has not been executed.

## WIP files

- `api/index.py`
- `schedule-editor.html`
- `supabase_master_schema.sql`
- `supabase_schedule_lifecycle_migration.sql`

## Known incomplete areas

- `confirmed` is still compatibility-converted to `planned` in parts of the API.
- New `schedule_events` fields are not fully wired into the frontend.
- Attendance is not fully implemented.
- `event_snapshot` is not yet used consistently for all reads and exports.
- ICS still uses a fixed `Europe/Paris` timezone.
- Rules for migrating legacy archived data still require confirmation.
- Schedule delivery ID updates still have fallback behavior in this WIP.
- The `effective_subscriptions` change and its relationship to lifecycle work must be reviewed.

Do not merge this branch directly into `main`. Before further implementation, review the WIP, add regression tests, and obtain read-only metadata for the production event schema. No Supabase SQL has been run as part of this checkpoint.
