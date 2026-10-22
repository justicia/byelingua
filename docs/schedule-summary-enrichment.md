# Schedule summary enrichment

The result page and downloaded calendar PNG share `schedule-summary-display.js` for content selection and line measurement. The new authenticated `get_schedule_summary` action enriches only the performances in the owned schedule. The existing `get_schedule`, editor, builder, header, pagination, email and ICS contracts remain unchanged.

## Read boundary

Ownership is checked before any schedule members or credits are returned. Programme and credits are fetched in batches of 100 performance IDs, with stable ordering and offset pagination until an empty page. A server cap below the requested limit does not truncate the relationship set. Public relation cache entries contain no schedule ownership or personal intent data.

The browser uses the enriched endpoint first; if it fails, it reads the existing basic schedule and displays a localized notice. The original rows, event keys and intent labels are retained. A summary read never mutates a schedule, event or global entity.

## Display policy

- Conductors are distinct from cast and soloists.
- Programme keeps the existing normalized programme semantics and canonical data. It is not reconstructed from event titles.
- Show up to 3 stored programme items, 2 soloists and 4 reviewed principal-role credits, with a count of additional known items. Counts do not imply official-source completeness.
- Instrument/voice labels alone do not establish soloist billing. Explicit soloist functions are accepted; the initial reviewed event-specific selections cover Sebastian Breit (4 June 2027), Jingwen Cai and Nicholas Brownlee (6 June 2027).
- `schedule_summary_data.py` contains a reviewed editorial selection of Arabella, Mandryka, Zdenka and Matteo, keyed by existing global Work and Character IDs. It selects the actual performance's credits. No cast names are embedded in the role rules.
- This selection is based on the official synopsis's two central relationships. It is not an exhaustive assertion that all other characters are supporting. Unlisted roles remain unclassified. Other works display the existing-detail fallback until their rules are reviewed.
- The role rules apply to opera performances of the linked Work; another work, a character-name coincidence or a ballet adaptation cannot trigger them.
- Missing data is never called officially unpublished without evidence. Known programme gaps are marked partial; otherwise the list is labelled as recorded programme, not a verified complete programme.

## Source review, 22 October 2026

- Arabella, performance-specific cast and synopsis: https://www.wiener-staatsoper.at/en/calendar/detail/arabella/2027-06-01/
- Beethoven 1–3 and conductor: https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-hrusa/63791
- Beethoven 4–5 and conductor: https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-hrusa/63792
- Beethoven 6–7: https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-hrusa/63793
- Beethoven 8–9 and four vocal soloists: https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-wiener-singakademie-hrusa/63794
- Thielemann / Breit, Strauss / Schönberg: https://spielplan.musikverein.at/spielplan?abo=&dcode=MEII2627&subpage=

A targeted read of these six public performances found missing Beethoven 1, 2 and 4, the Strauss oboe concerto on 4 June, and two vocal soloist relations on 6 June. Those are separate data-review tasks. No missing relations or canonical entities are fabricated, renamed or written by this feature. Some stored canonical titles also use different source languages; changing global Work titles is outside this display change.

`fixtures/schedule-summary.json` is a public-data snapshot for local verification, with synthetic schedule/entry IDs. Test intent choices are synthetic. It is neither an identity master nor a substitute for live database reads.

## Image layout

The existing 1400 logical pixel width, 2x output, brand/title positions for ordinary titles, colours, margins and date bars are retained. Each row uses the greater measured height of its two content areas. Long schedule titles are measured too. Long schedules split between complete rows into numbered PNG files at at most 7000 logical pixels per image, repeating a day's heading when necessary. Downloads remain behind the existing button. Extremely oversized individual rows report an export error instead of producing a clipped image; the page and ICS remain available.

## Validation

Run `python -m unittest test_schedule_summary test_event_key_resolution test_schedule_filtered_results` in the project's Python environment, and `npm test` with the existing Playwright installation. Set `SCHEDULE_CHROME_PATH` to an installed browser when the bundled executable is unavailable. `SCHEDULE_SUMMARY_ARTIFACT_DIR` optionally controls the preview output directory.

The summary UI test covers actual PNG download, equality of rendered summary content, intent preservation, desktop/mobile layout, Chinese/English, long rows and schedule titles, 90-entry multi-image layout, escaping and basic-schedule fallback. The Python tests cover ownership isolation, performance-specific credits, role/soloist classification, deduplication and server-capped relation pagination. `node test_schedule_summary.cjs --serve` starts a local public-data fixture preview; it never logs into production.

## Global coverage review (22 October 2026)

The shared selection now has reviewed policies for 57 existing global Works.
`schedule_summary_registry.py` is generated, public source-review data rather
than a canonical Work/Character/alias master. Policies contain no artist names
or venue ownership. Linked credits use reviewed Character IDs; source-only
credits can use an explicitly reviewed exact spelling within a performed Work,
without receiving a canonical Character ID. A role-name collision across two
performed Works stays unclassified. The `cast` source function is supported;
artistic team functions, ballet adaptations and unreviewed linked IDs are not
promoted to principals. The same artist's duplicate spelling of one selected
role is displayed once, while distinct roles remain separate.

The result page and PNG keep their existing shared renderer and limits. No
frontend files, layout, header, pagination, styles or controls changed.

Programme missingness is checked against 1,206 last-reviewed performance
expectations from eight source batches. This is evidence about those reviewed
observations, never a claim that unknown or currently unpublished programme
content is complete. Existing relations and source versions can change after
a historical batch; do not replay it. An eight-batch live reconciliation found
all 2,500 expected Work relationships present, with one later-reviewed order
change rather than a missing Work.

`season_ingestion.programme_coverage` checks known source programme rows
against staged relationships at graph construction and immediately before
apply. Unexplained loss blocks the write. A reviewed deferral requires an
explicit event key, source index, reason and `reviewed: true`; missing source
observations remain unknown. This protects the shared graph writer and
`apply_approved_season_run.py`; bespoke SQL must still undergo the equivalent
source/staging/live comparison and batch approval. The guard cannot discover
works an adapter never captured from the source.

Prepare a scoped, read-only delta query without accessing the database:

```sh
python jobs/audit_programme_coverage.py --staging reviewed/production-staging.json --output-sql reviewed/reconcile.sql
```

The command accepts repeated staging inputs, rejects conflicting historical
expectations, and distinguishes an existing relationship at another position
from a missing relationship. It generates only SELECT SQL and performs no
writes or canonical identity resolution.

Global first-pass inventory covered 9,464 events. Empty programme rows, ordinal
gaps and role/Work mismatches are review candidates, not automatic errors.
The cast-related inventory includes 201 Works/components across mixed event
types; 57 have reviewed selection policies and 144 remain in source review.
Unsupported items retain the performance-details fallback. Production data
remediation and deployment require their own concrete authorized scopes.

Additional validation: `python -m unittest test_global_summary_coverage
 test_schedule_summary test_event_key_resolution test_schedule_filtered_results`
and `python -m pytest test_production_graph.py test_venue_onboarding_factory.py
 test_europe_auto_factory.py`. Current live public Tosca snapshots from five
organizations test both linked and source-only roles; one performance lacks
its principals in the stored credits and is intentionally not filled from a
different performance.
