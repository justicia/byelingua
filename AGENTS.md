# Byelingua Engineering Rules

This file defines repository-level engineering rules for Byelingua.

These rules apply to all Codex/Luna tasks in this repository unless the user explicitly overrides them for a specific task.

Core principle:

**Evidence first → isolate the failing layer → make the minimum necessary change → validate → stop.**

---

# FRONTEND UI LOCK

The Byelingua frontend is a user-approved product surface.

Do not modify page layout, global navigation, headers, typography, spacing,
colors, component hierarchy, interaction structure, Schedule Builder UI,
User Center UI, Event Detail UI, My Schedules UI, Schedule Editor UI,
responsive layout, or visual design during data ingestion, scraper, adapter,
backend, database, API, email, or maintenance tasks.

Frontend changes are allowed only when the user explicitly requests a
frontend/UI/layout change.

Data-source incompatibilities must be solved in adapters, normalizers,
schemas, APIs, or ingestion logic, never by silently redesigning the
frontend.

---

# 1. EXECUTION ROLE

Codex/Luna is the implementation agent.

Follow the task scope literally.

Do not independently redefine:

- product logic
- UI behavior
- data architecture
- canonical identity rules
- database semantics
- ingestion workflow
- business rules

Do not perform unrelated cleanup, refactoring, dependency upgrades,
schema redesign, naming changes, or architectural improvements.

If an unrelated issue is discovered, report it separately instead of
silently fixing it.

---

# 2. SOURCE OF TRUTH

For code and repository state, the remote GitHub repository is the default
source of truth.

Do not rely on:

- local stash
- local terminal history
- uncommitted state from another computer
- undocumented local configuration
- assumptions based on an earlier development machine

Before substantial work, verify:

- repository
- current branch
- git status
- relevant remote branch
- relevant baseline commit

Do not push directly to `main` unless explicitly authorized.

Do not merge PRs unless explicitly authorized.

Do not deploy Vercel unless explicitly authorized.

Do not execute Supabase migrations or production data mutations unless
explicitly authorized.

---

# 3. DEBUGGING ORDER

When production or frontend data appears incorrect, investigate the actual
data path in this order:

**Official Source  
→ Scraper / Discovery  
→ Source Adapter  
→ Raw Data  
→ Normalizer / Canonical Schema  
→ Supabase  
→ Backend API  
→ Frontend Request  
→ Browser Actual Response  
→ Vercel Production / Cache  
→ Rendered UI**

Do not jump directly to:

- re-scraping
- rebuilding production data
- changing frontend code
- rewriting adapters
- changing database schema

Stop at the first confirmed failing layer.

Fix that layer first.

A visible frontend problem does not prove that the frontend is the root
cause.

---

# 4. EVIDENCE BEFORE REPAIR

Prefer measurable evidence over assumptions.

Depending on the task, inspect:

- source discovery results
- fetched count
- parsed count
- database COUNT
- MIN/MAX date
- monthly GROUP BY
- duplicate counts
- API response counts
- API pagination
- request parameters
- browser Network responses
- Vercel production commit
- production response

Do not claim a layer is broken until evidence shows it is broken.

Do not rebuild correct production data simply because the rendered page is
incomplete.

---

# 5. EVENT IDENTITY MODEL

Byelingua uses three distinct conceptual identity levels:

**Work → Production → Performance**

They must not be collapsed into one identity.

## Work

A Work represents the canonical artistic work itself.

The same Work appearing:

- at another venue
- under another organization
- in another season
- in another language
- on another source URL

must still resolve to the same canonical Work identity.

Canonical Work identity must not be venue-specific or source-specific.

## Production

A Production represents a specific staged or programmed realization of a
Work.

Production-level metadata may include:

- organization
- season
- director
- production team
- staging
- design
- production-specific credits

A Production must not be treated as a new Work.

## Performance

A Performance represents one actual dated occurrence.

Performance identity must preserve:

- date
- time
- venue
- organization
- production relationship
- performance-specific cast or credits where applicable

User attendance and scheduling features should ultimately refer to the
Performance identity.

---

# 6. CANONICAL WORK TITLES

Canonical Work titles must use the standard original-language title.

Do not replace the canonical title with a venue's translated or localized
title.

Local titles may be retained as:

- aliases
- source metadata
- raw metadata
- search aliases

Search should support, where data exists:

- English titles
- common English translations
- Latin-alphabet artist names
- accent-insensitive input
- alternate spellings
- partial matching

Search aliases must never overwrite canonical Work titles.

---

# 7. PROGRAMME AND CREDITS

`programme` contains actual artistic programme content only.

Do not place the following in canonical programme data:

- marketing copy
- production descriptions
- venue descriptions
- ticket information
- navigation text
- generic event labels
- cast headings
- artistic-team headings

Cast and Artistic Team must remain semantically separate.

Cast represents roles and performers.

Artistic Team includes functions such as:

- conductor
- director
- orchestra
- chorus
- designer
- lighting
- dramaturgy

A conductor must not be classified as cast.

When casting or conducting assignments vary by date, preserve the
performance-specific mapping.

Do not flatten date-specific assignments into one production-wide list if
that creates false credits.

---

# 8. VENUE AND ORGANIZATION

`venue` and `organization` are different semantic fields.

Never treat them as interchangeable simply because they have similar names.

If filtering by organization, use the organization field.

If filtering by venue, use the venue field.

Frontend/API filtering parameters must correspond to the intended database
field.

---

# 9. QUERY SAFETY

Critical filtering should occur in the database query whenever practical.

Avoid patterns such as:

**LIMIT → application-side filtering**

when the limit can truncate valid matching records.

For event lists, verify where relevant:

- total count
- pagination
- date range
- organization filter
- venue filter
- season filter

A successful API response is not sufficient if the result set is silently
truncated.

---

# 10. SEASON INGESTION WORKFLOW

The intended season ingestion path is:

**Official source audit  
→ discovery  
→ venue adapter  
→ normalization  
→ canonical identity matching  
→ validation  
→ dry-run  
→ preflight / staging  
→ review  
→ guarded Supabase write  
→ post-write verification**

These stages must remain separable.

Do not combine discovery, normalization, and production writes into one
opaque operation.

---

# 11. VENUE ONBOARDING

Add and validate venues independently.

For each venue:

**Official source audit  
→ discovery adapter  
→ dry-run  
→ coverage validation  
→ identity validation  
→ detail enrichment  
→ preflight  
→ write approval**

Do not assume that one venue passing validation proves another venue is
ready.

One venue's failure must not corrupt or block unrelated venue data.

Venue-specific adapters are expected when official source structures differ.

Do not weaken global canonical rules merely to accommodate one unusual
website.

---

# 12. DRY-RUN FIRST

New or materially modified ingestion logic must run in dry-run mode before
production write.

Dry-run should verify where applicable:

- discovered events
- fetched count
- parsed count
- date coverage
- monthly distribution
- canonical Work matching
- Production identity
- Performance identity
- organization
- venue
- programme
- credits
- event type
- source URLs
- duplicates
- parser failures

Database write count should remain `0` until the write stage is explicitly
authorized.

A successful scraper run is not approval for production write.

---

# 13. IDENTITY SAFETY

Stable identities must survive ordinary source changes.

Do not generate a new canonical identity merely because:

- URL changed
- formatting changed
- metadata changed
- source page structure changed
- venue changed
- season changed
- translated title changed

Ambiguous canonical Work matching must not be guessed.

If matching is genuinely ambiguous, surface it for review.

Do not create a new Work simply to avoid resolving ambiguity.

UPSERT logic must prevent both:

- collapsing distinct performances into one record
- creating duplicate records for the same real performance

---

# 14. PRODUCTION DATA SAFETY

A failed scrape must never silently delete previously valid production data.

Do not interpret any of the following as cancellation:

- network failure
- parser failure
- source timeout
- incomplete discovery
- HTML structure change
- temporary source disappearance

Cancellation requires reliable source evidence and a successful comparison
under the defined ingestion rules.

Production writes should be:

- scoped
- deterministic
- idempotent where possible
- reviewable
- reversible where practical

---

# 15. SOURCE PROVENANCE

Canonical data should remain traceable to official source evidence.

Where supported by the schema, preserve relevant provenance such as:

- source URL
- source identifier
- raw title
- raw date/time
- raw programme
- raw credits
- scrape timestamp

Official venue or organization sources are preferred for event data.

---

# 16. ENCODING

Repository and ingestion text handling must preserve UTF-8.

Do not introduce mojibake or character corruption into:

- artist names
- Work titles
- venue names
- French
- German
- Spanish
- Italian
- Czech
- other original-language data

Encoding corruption introduced by a change is a regression.

---

# 17. REGRESSION PROTECTION

When repairing one venue, organization, parser, adapter, API path, or
production issue, treat unrelated confirmed components as read-only unless
the task explicitly requires changes there.

A fix for Venue A must not silently alter Venue B.

Do not introduce global parser, schema, or normalization changes to solve a
single venue unless evidence demonstrates that the problem is genuinely
global.

---

# 18. VALIDATION

After modification, run the smallest relevant validation first, followed by
broader validation when necessary.

Depending on the task, validation may include:

- syntax / compile check
- unit tests
- parser tests
- adapter fixtures
- dry-run
- preflight
- database COUNT
- MIN/MAX date
- monthly GROUP BY
- duplicate check
- identity check
- API response check
- browser Network check
- production verification

Never claim something works unless the relevant layer has actually been
verified.

Clearly distinguish:

- observed facts
- inferred causes
- changes made
- validation performed
- remaining uncertainty

---

# 19. GIT SAFETY

Before editing:

- inspect current branch
- inspect `git status`
- fetch relevant remote state when needed
- identify the relevant baseline commit

After editing:

- inspect the diff
- verify only expected files changed
- run required validation
- report branch and commit state

Do not:

- force-push
- rewrite shared history
- delete remote branches
- merge `main`
- expose credentials

unless explicitly authorized.

---

# 20. SECRETS

Never:

- print secrets
- commit secrets
- expose environment variables
- invent credentials
- place service-role keys in repository files
- include secrets in logs or reports

Supabase, GitHub Actions, Vercel, OpenAI, Resend, and other credentials must
remain in their designated secret/environment systems.

---

# 21. STOP CONDITIONS

Stop and report instead of expanding scope when:

- source behavior materially differs from expectations
- canonical identity is ambiguous
- production credentials are unavailable
- a database migration appears necessary but was not authorized
- destructive production changes would be required
- fixing the issue requires unrelated frontend changes
- production and remote Git state cannot be reconciled
- validation reveals unexpected regressions

Uncertainty requires additional investigation, not speculative modification.

---

# 22. FINAL REPORT

At the end of a substantial task, report:

## Finding / Root Cause

What was actually discovered.

## Changes

Files and components changed.

## Validation

Tests, commands, queries, dry-runs, API checks, or browser checks performed,
including results.

## Data Impact

Where relevant:

- fetched
- parsed
- new
- updated
- unchanged
- skipped
- failed
- cancelled
- database writes

## Unresolved Issues

Anything requiring further work or user approval.

## Git State

Report:

- branch
- commit
- push status
- whether `main` remained untouched

Do not report a task as complete without corresponding evidence.

# GLOBAL CANONICAL ENTITY OWNERSHIP

Byelingua uses one global canonical identity layer shared by all venues, organizations, cities, seasons, and source websites.

The following entities are GLOBAL and must never be owned by an individual venue or source:

- Composer
- Artist
- Work
- Character

Canonical identity tables and their alias systems are global.

Conceptually:

- `composers` → `composer_aliases`
- `artists` → `artist_aliases`
- `works` → `work_aliases`
- `characters` → `character_aliases`

A Composer, Artist, Work, or Character that appears at multiple venues must reuse the same global canonical ID.

## Source-specific data is not canonical identity

Venue/source adapters and parsers may only describe what the source publishes.

They may produce source-specific/raw data such as:

- raw composer names
- raw artist names
- raw work titles
- raw character/role names
- raw programme order
- raw cast and artistic credits
- source URLs
- source timestamps
- source provenance
- production/performance data

They must not define a separate canonical identity universe.

The following patterns are forbidden:

- venue-specific Composer masters
- venue-specific Artist masters
- venue-specific Work masters
- venue-specific Character masters
- venue-specific alias tables
- source-specific canonical identity tables

Do not create architecture equivalent to:

- `auditorio_composers`
- `paris_opera_composers`
- `teatro_real_artists`
- `venue_works`
- `auditorio_composer_aliases`
- `source_work_aliases`

or any equivalent source-owned canonical identity system.

## Required ingestion boundary

All ingestion must respect this separation:

Official Source
→ Source Adapter / Parser
→ Raw Observation
→ Semantic Classification
→ GLOBAL Entity Matcher
→ Canonical Staging
→ Validation
→ Production Relations

Parser responsibility:

> What did the source publish?

Matcher responsibility:

> Which existing global canonical entity does this observation represent?

Parsers must never create canonical Composer, Artist, Work, or Character entities.

Parsers must never directly assign canonical identity merely to improve ingestion completeness.

## Global matcher rule

All venues must match against the same global canonical masters.

Examples:

Auditorio raw Composer
→ Global Composer Master

Paris Opera raw Composer
→ Global Composer Master

Teatro Real raw Artist
→ Global Artist Master

Wiener Staatsoper raw Work
→ Global Work Master

A venue-specific dry-run or historical match artifact must never be used as the canonical identity universe.

Artifacts such as:

- parser dry-runs
- match JSON
- source audits
- season batches
- repair artifacts
- historical matching outputs

are evidence only.

They must not replace the current global canonical master.

## Global alias rule

Aliases are global.

A source may discover a new spelling or name variant, but it does not own that alias.

Correct flow:

raw source variant
→ global matcher
→ alias-gap proposal
→ review
→ global alias table

Once accepted, the alias must be reusable by every venue and source.

Source provenance may record where an alias was observed, but provenance does not change global ownership.

## Unmatched does not mean create

An unmatched observation must never automatically create a canonical entity.

Before proposing a new Composer, Artist, Work, or Character, the system must check the complete global identity universe, including:

- exact canonical identity
- exact alias
- normalized canonical identity
- normalized alias
- deterministic identity evidence
- collisions
- ambiguous candidates

Only after the global master has been exhausted may an observation enter:

`new global entity staging review`

Automatic creation of canonical entities from unmatched parser output is forbidden.

## Identity and relationship must remain separate

Global identity:

- Composer
- Artist
- Work
- Character

Source/event-specific relationships:

- Work ↔ event programme
- Composer ↔ Work
- Artist ↔ performance
- Artist ↔ production credit
- Character ↔ casting
- Venue ↔ performance
- Organization ↔ production
- programme order
- performance-specific cast
- performance-specific artistic credits

Different relationships must never cause duplication of global identity.

## Work title rule

Canonical Work titles use the standard original-language title.

Local-language source titles must remain raw data or aliases.

English/common translated titles may be used for search aliases.

Search convenience must never overwrite canonical Work identity.

## Matcher reuse principle

Canonical identity resolution should be implemented as reusable global infrastructure:

- Global Composer Matcher
- Global Artist Matcher
- Global Work Matcher
- Global Character Matcher

Venue-specific differences belong primarily in:

- source adapters
- parsers
- semantic classification

Do not implement a separate canonical identity system for each venue.

## Canonical safety

Never create a canonical entity solely to increase match rate.

Never silently normalize an ambiguous identity.

Never choose the most famous candidate when multiple identities are plausible.

Ambiguity must remain explicit and reviewable.

All canonical identity creation, alias creation, identity merge, or other identity mutation requires explicit staging/review before production mutation.