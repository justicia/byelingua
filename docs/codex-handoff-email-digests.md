# Byelingua email digest integration handoff

- Repository: `https://github.com/justicia/byelingua.git`
- Baseline commit: `022f2ea` (`main`)
- Branch: `integrate-email-digests`
- Integration checkpoint commit: `efe96bbf3f72cc101820a30965e55f3f327e479f`.
- All database migrations remain unapplied online.

## Completed

- Restored the daily multilingual personal digest flow without merging the old branch.
- `run_personal_digest()` returns only newly inserted articles.
- No-new-article and disabled-digest sends are skipped.
- One delivery per user and Paris date is reserved by a database unique constraint.
- Recipients come from `profiles.email`; content language comes from `profiles.preferred_language`.
- HTML and plain text messages use server-only Resend credentials and escaped external content.
- User failures are isolated during scheduled processing.
- Canonical preference is `email_digest_enabled`, with `email_subscription_enabled` compatibility reads and writes while migration is pending.
- User Center renders one bilingual Daily email digest switch.
- Schedule and digest delivery tables remain separate.
- Schedule delivery updates now require and use the created delivery ID only.

## Selectively migrated from `email-digests`

- Digest copy, HTML/text builder, Resend sender, delivery reservation, and newly-inserted article tracking.
- Digest preference compatibility behavior and related regression tests.

The old branch was not merged and commits `481f913` and `a0eec0c` were not cherry-picked. Its older page implementations and master schema were not copied because they would overwrite current schedule, bilingual UI, subscription, and public-article work.

## Files changed

- `README.md`
- `account.html`
- `api/index.py`
- `supabase_master_schema.sql`
- `supabase_email_digests_migration.sql`
- `test_api.py`
- `docs/codex-handoff-email-digests.md`

## Database and compatibility

`supabase_email_digests_migration.sql` is repeatable and defines `profiles.email_digest_enabled`, `email_digest_deliveries`, the per-user/date unique constraint, article IDs, delivery status, provider ID, error timestamps, RLS, and grants. It safely backfills true values from the legacy preference without overwriting canonical true values. `supabase_master_schema.sql` now includes the digest table alongside the current schedule tables and full public article JSONB fields. No migration has been executed against Supabase.

## Verification

Command: `"/Users/chengnorah1/Programm/bye lingua-backup-20260813/.venv/bin/python" -m unittest -q`

Result: `67 tests OK`, including mocked Resend and schedule-delivery-ID coverage. Python AST checks, embedded JavaScript syntax checks, and `git diff --check` passed.

## Remaining work

- Obtain read-only production metadata for events, venues, organizations, catalog views, timezones, constraints, RLS, and grants before any migration.
- Review and approve the canonical preference migration and existing data backfill.
- Review timezone behavior and production delivery records.
- Do not merge this branch into `main` until the schema and API review is complete.

## Tomorrow: continue safely

```bash
cd "/Users/chengnorah1/Programm/bye lingua"
git fetch origin
git switch integrate-email-digests
git pull --ff-only
git status -sb
```

Review `docs/codex-handoff-email-digests.md`, run the verification commands again, and obtain approval before any Supabase migration. No credentials, tokens, or environment variable values are stored in this handoff.
