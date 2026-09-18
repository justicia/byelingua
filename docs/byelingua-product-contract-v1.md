# Byelingua Product Contract V1

Status: **permanent, frozen, non-negotiable**.

The repository identifier is `BYELINGUA_PRODUCT_CONTRACT_VERSION=1`.  The
contract is owned by Byelingua, not by any source adapter, PDF parser, Hermes
worker, canonical resolver, or venue onboarding run.

## Immutable Event Detail semantics

- Programme contains musical Works only and renders `Composer — Work` in source
  order.  Composer-only fragments, marketing/subscription titles, performers,
  and production-team credits are not Programme rows.
- Opera/staged Cast is a dedicated `Artist — Character` group.  A known
  character is never downgraded to a generic performer.
- Artistic Team is a separate group for conductor, stage director,
  choreographer, set, costumes, lighting, video, dramaturgy, chorus master,
  and equivalent artistic-production functions.
- Concert/recital performers preserve a known instrument or voice type.
- Explicit Orchestra, Chorus, and Ensemble relationships remain separate.
- Composer metadata belongs to Works/Programme and never becomes Cast,
  Performers, or Artistic Team unless the same person has another explicitly
  documented performing role.

The frontend consumes normalized structured fields (`artist`, `work`,
`composer`, `character`, `function`, `instrument_or_voice`, and
`ensemble_type`).  It must not guess semantic meaning from raw role strings.

## Ingestion and release gates

Every source follows `SOURCE -> SEGMENT -> STRUCTURE -> NORMALIZE ->
CANONICAL_RESOLVE -> SEMANTIC_DEDUP -> PRODUCT_CONTRACT_VALIDATION ->
PRODUCTION_WRITE`.  Accepted facts are append-only; disagreements are
`CONFLICT / REVIEW`, never silent overwrites.  Each run declares its target
venues and events, and any out-of-scope mutation is a hard failure.

The accepted Event Detail frontend is frozen at commit
`1d7591dba2df428152b35ccb4a0b98e65c934efa`.  Normal ingestion cannot modify
frontend files or trigger an automatic frontend deployment.  Contract tests
and a live production smoke test are mandatory for release claims.

Changing this contract requires `EXPLICIT_PRODUCT_CONTRACT_CHANGE=YES` in a
dedicated product/UI semantics task.  Parser, venue, PDF, cleanup, deployment,
and refactor work remains V1-compatible by default.

