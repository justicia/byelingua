# Production Manual-Apply SQL Standard

1. Generate and review production SQL before manual execution.
2. Codex does not execute production mutation SQL; the user manually applies approved SQL.
3. Keep apply and validation SQL in separate files.
4. Validation must be independently executable.
5. Do not depend on cross-statement TEMP TABLE lifetime in the Supabase SQL Editor.
6. Prefer a transaction with hard baseline guards and exact target identity checks.
7. Require and verify affected-row counts.
8. Require exact post-state validation.
9. Keep safe executable subsets separate from dependency or review backlogs.
10. Never rerun an apply script after an apparent SQL Editor error until production state has been independently checked; the mutation may already have committed.
