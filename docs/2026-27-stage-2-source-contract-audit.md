# 2026–27 stage-two official source-contract audit

Audit date: 2026-08-16  
Scope: `operadeparis`, `philharmonie_paris`, and `auditorio_nacional`  
Decision: **none of the three sources is approved for adapter implementation or preflight**

## Method and safety boundary

This is a read-only contract audit. No database, SQL, migration, deployment,
writer, reconciliation, existing adapter, or frontend operation was run or
changed. The public sites were requested from the audit environment, but its
egress proxy returned `403 CONNECT` before an origin response for all three
domains. Consequently, this report records only facts that can be supported by
an existing official URL in the repository or by a successful origin capture;
it does **not** promote guessed routes, DOM selectors, identifiers, pagination,
or third-party search results into a source contract.

The production baselines supplied for comparison are retained as acceptance
targets, not evidence about a website contract:

| Source | Expected performances | Inclusive observed range |
|---|---:|---|
| `operadeparis` | 506 | 2026-08-28–2027-07-15 |
| `philharmonie_paris` | 268 | 2026-09-01–2027-06-22 |
| `auditorio_nacional` | 583 | 2026-09-18–2027-07-02 |

## Unified result

| Required contract item | Opera de Paris | Philharmonie de Paris | Auditorio Nacional |
|---|---|---|---|
| Official discovery page/endpoint confirmed by origin capture | blocked | blocked | blocked |
| Complete 2026–27 retrieval and pagination confirmed | no | no | no |
| Performance-level stable ID proven | no | no | no |
| Production URL reuse across performances proven | no | no | no |
| Date/time/room/type provenance proven | no | no | no |
| Detail and artist provenance proven | no | no | no |
| Date-level programme/cast/conductor evidence proven | no | no | no |
| Reproducible fixture can be captured now | no | no | no |
| `discovery_ready` | false | false | false |
| `detail_enrichment_ready` | false | false | false |
| `preflight_ready` | false | false | false |

“Blocked” is deliberately different from “does not exist”: origin access must
be repeated from an environment that can reach the official domains. Production
row counts and dates cannot answer any of the contract questions above.

## `operadeparis`

### Independently established facts

The configured season boundary begins on **2026-08-28**, so any later audit and
adapter must query an inclusive window starting on that date. The current venue
configuration intentionally contains no adapter or calendar URL. No official
origin response was captured during this audit.

### Unresolved contract

The calendar/discovery URL or endpoint, request parameters, maximum date span,
pagination termination, sort order, and total-count semantics remain unproven.
It is also unproven whether a performance has its own immutable identifier or
whether only a production identifier/slug is public; whether one production
detail URL represents several dates; and which payload owns date, local start
time, house/room, official type, canonical detail URL, and artist links.

Programme, cast, and conductor data must not be treated as date-level evidence
until a captured response demonstrates their association with a specific
performance ID/date. Production-level credits are insufficient where casts or
conductors change by date.

### Minimum reproducible fixture plan

1. Capture the official calendar HTML plus every first-party XHR/fetch response
   for an inclusive request beginning `2026-08-28` and ending `2027-07-15`.
2. If the source limits ranges, capture the smallest sequence of adjacent,
   non-overlapping requests that covers that interval, including the first,
   second, and terminal pages for every pagination mode.
3. Preserve response bodies and a manifest containing URL, method, sanitized
   request parameters/body, status, content type, capture time, and SHA-256.
4. Select one production with at least two performances and capture discovery
   rows plus its official detail and artist responses. The fixture is acceptable
   only if it proves distinct stable performance IDs and date-specific credits.
5. Reconcile the fixture-derived full run to 506 performances, minimum date
   `2026-08-28`, and maximum date `2027-07-15`; discrepancies block readiness.

## `philharmonie_paris`

### Independently established facts

The venue is configured without an adapter or calendar URL. No official origin
response was captured, so neither a public agenda page nor a machine endpoint
is asserted here as a contract.

### Unresolved contract

The discovery route, filters that distinguish concerts at the requested venue
from the wider institutional programme, pagination/date-window behavior, and
performance identity are all unresolved. An event/product identifier must not
be assumed to identify an individual performance. The audit also could not
prove whether repeated dates share one production URL, or establish the source
of date, time, room, official event type, detail URL, artist profile, programme,
cast, or conductor fields.

### Minimum reproducible fixture plan

1. Capture the official agenda document and first-party network responses for
   `2026-09-01` through `2027-06-22`, retaining all venue/category filters.
2. Capture the first, second, and last page (or each cursor transition), plus an
   empty terminal response. Demonstrate that range boundaries are inclusive and
   that adjacent ranges neither omit nor duplicate a performance.
3. Capture a multi-performance production from discovery through detail and
   artist-profile responses. Require a stable per-performance ID independent of
   a shared production URL.
4. Store raw bytes and a sanitized request/SHA-256 manifest; do not hand-edit a
   response into a synthetic fixture.
5. A complete replay must yield 268 performances over the supplied inclusive
   range before `discovery_ready` can be true.

## `auditorio_nacional`

### Independently established facts

The repository's existing, non-discovery enrichment module restricts accepted
details to the official prefix
`https://auditorionacional.inaem.gob.es/es/programacion/`. It parses content
from those already-attached detail URLs; it does not establish calendar
discovery, pagination, season completeness, or stable performance identity.
No response from that official host was captured during this audit.

### Unresolved contract

There is no audited discovery endpoint or request contract. It remains unknown
whether promoter-specific pages expose one record per performance, whether a
programme URL is reused for several dates, and which official response supplies
date, start time, hall/room, event type, and artist profile. The existing detail
parser can extract apparent artists and programme text, but without a captured
performance join it is not proof that programme, cast, or conductor applies to
a particular date.

### Minimum reproducible fixture plan

1. Capture the official programme/calendar entry page and all first-party data
   responses needed to cover `2026-09-18` through `2027-07-02`.
2. Prove venue/hall filtering, inclusive date semantics, pagination termination,
   and a stable per-performance ID using first, second, and terminal pages.
3. Include at least one promoter layout already recognized by the enrichment
   module and one production with multiple dates. Capture discovery, every
   distinct performance, detail HTML, and any artist-profile response.
4. Preserve unmodified bytes with sanitized request metadata and SHA-256; the
   fixture replay must not need live network or database access.
5. Require 583 performances across the supplied range and verify programme,
   cast, and conductor against each performance rather than copying production-
   level text to every date.

## Readiness gate

An adapter proposal may begin only after each venue has its own committed raw
fixture and manifest proving all required fields and identity/pagination rules.
Until then, configuration must remain disabled and no inferred scraper, staging
data, preflight, reconciliation, or write should be produced for these sources.
