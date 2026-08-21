# Byelingua Global Canonical Entity Standard

Status: Active
Scope: Global
Applies to: All ingestion pipelines, parsers, matchers, staging jobs, repair scripts, database writers, APIs, and future venue integrations.

---

## 1. Purpose

Byelingua maintains one shared canonical identity layer across all countries, cities, organizations, venues, seasons, productions, performances, and source websites.

The following entities are global:

- Composer
- Artist
- Work
- Character

They must not belong to an individual venue, organization, city, season, parser, or source website.

A source may observe an entity.

A source does not own that entity.

The same real-world Composer, Artist, Work, or Character must reuse the same global canonical ID everywhere in Byelingua.

---

## 2. Core Architecture

The canonical architecture is:

GLOBAL CANONICAL ENTITY LAYER
│
├── composers
│   └── composer_aliases
│
├── artists
│   └── artist_aliases
│
├── works
│   └── work_aliases
│
└── characters
    └── character_aliases

Venue-specific ingestion sits below this global layer:

Official Source
        ↓
Source Adapter / Parser
        ↓
Raw Observation
        ↓
Semantic Classification
        ↓
GLOBAL Entity Matcher
        ↓
Canonical Staging
        ↓
Validation
        ↓
Production Relations

Examples:

Auditorio Nacional raw composer
→ Global Composer Matcher
→ composers.id

Paris Opera raw artist
→ Global Artist Matcher
→ artists.id

Teatro Real raw work
→ Global Work Matcher
→ works.id

Wiener Staatsoper raw character
→ Global Character Matcher
→ characters.id

---

## 3. Global Entity Ownership

### 3.1 Composer

Composer identity is global.

Canonical Composer identity belongs to:

composers
composer_aliases

A Composer appearing at multiple venues must reuse the same:

composers.id

For example:

Paris Opera
Auditorio Nacional
Teatro Real
Philharmonie de Paris
Wiener Staatsoper

may all reference the same Ludwig van Beethoven record.

They must not create separate Beethoven identities.

### 3.2 Artist

Artist identity is global.

This includes, where appropriate:

- singers
- conductors
- instrumentalists
- soloists
- stage directors
- artistic collaborators
- ensembles
- orchestras
- choirs

A person or ensemble appearing at different venues, cities, organizations, or seasons must reuse the same global:

artists.id

Event-specific roles belong to event or production relations.

They do not create a new Artist identity.

Example:

Artist:
Simon Rattle

Performance A:
role = conductor

Performance B:
role = conductor

Both performances reference the same global Artist ID.

### 3.3 Work

Work identity is global.

Canonical Work identity belongs to:

works
work_aliases

The canonical title must use the standard original-language title according to the existing Byelingua Work-title rule.

Local source translations must never overwrite the canonical title.

Example source observations:

Las bodas de Fígaro
Le nozze di Figaro
The Marriage of Figaro
Les Noces de Figaro

must resolve to one global Work when they refer to the same work.

The source wording may be preserved as:

- raw title
- alias
- provenance

but not as a competing canonical Work.

### 3.4 Character

Character identity is global.

Canonical Character identity belongs to:

characters
character_aliases

A Character must not be duplicated because it appears in:

- another production
- another venue
- another language
- another source website

Example:

Der Wanderer
The Wanderer
Le Voyageur

may resolve to one global Character identity when they refer to the same dramatic character.

Production-specific casting belongs to relationship tables.

It must not redefine Character identity.

---

## 4. Source-Specific Data

A venue or source owns only what it actually publishes.

Allowed source-specific data includes:

- raw event title
- raw programme text
- raw composer name
- raw artist name
- raw work title
- raw character or role name
- raw cast
- raw artistic team
- programme order
- source URL
- source timestamps
- source status
- production information
- performance information
- source provenance
- parser metadata
- scrape metadata

A source does not own canonical identity.

---

## 5. Forbidden Source-Specific Canonical Masters

The following architectural patterns are forbidden:

auditorio_composers
paris_opera_composers
teatro_real_composers

auditorio_artists
paris_opera_artists

venue_works
source_works

auditorio_characters

auditorio_composer_aliases
paris_opera_work_aliases
venue_artist_aliases

Any equivalent architecture that creates a source-owned or venue-owned canonical identity universe is also forbidden.

Venue-specific files may contain raw observations.

They may not become canonical master databases.

---

## 6. Parser and Matcher Separation

Parser and Matcher are separate responsibilities.

### Parser responsibility

The Parser answers:

What did the official source publish?

Parser output may include:

raw_title
raw_composers
raw_artists
raw_roles
raw_work_title
raw_programme
programme_order
source_url
source_event_id
source_metadata

The Parser must preserve source wording.

### Matcher responsibility

The Matcher answers:

Which existing global canonical entity does this raw observation represent?

The Matcher may resolve:

raw composer
→ composer_id

raw artist
→ artist_id

raw work
→ work_id

raw character
→ character_id

The Matcher must use the current global canonical master.

### Parser must not

A Parser must not:

- create Composer
- create Artist
- create Work
- create Character
- create aliases
- assign canonical identity by guess
- directly write canonical identity tables
- directly write event_programme
- directly create canonical Works to eliminate unmatched rows

---

## 7. Required Ingestion Pipeline

All programme and identity ingestion should follow:

Official Source
→ Source Parser
→ Raw Programme Item / Raw Credit
→ Semantic Classification
→ Global Composer Matcher
→ Global Artist Matcher
→ Global Work Matcher
→ Global Character Matcher
→ Canonical Staging
→ Validation
→ Production Apply

Not every source must use every Matcher.

For example, an orchestral concert may not require Character matching.

But canonical identity resolution must always use the global identity layer.

---

## 8. Source Artifacts Are Evidence, Not Masters

The following may exist as workflow artifacts:

- source audit JSON
- parser dry-run JSON
- semantic classification JSON
- Composer match JSON
- Artist match JSON
- Work match JSON
- staging JSON
- season batch artifacts
- repair artifacts
- historical migration artifacts

These files are evidence.

They are not canonical master sources.

A source-specific artifact must never define the full canonical universe.

For example:

paris-opera-programme-match-dry-run.json

may be used as:

- historical evidence
- regression fixture
- debugging reference

but must never be treated as:

Global Composer Master
Global Work Master
Global Artist Master
Global Character Master

Canonical identity must come from the current global canonical layer.

---

## 9. Global Alias Architecture

Aliases are global.

Examples:

composer_aliases
artist_aliases
work_aliases
character_aliases

A source may discover a new alias.

A source does not own that alias.

Correct flow:

Raw Source Variant
        ↓
Global Matcher
        ↓
Alias Gap
        ↓
Review
        ↓
Global Alias Table

After acceptance, the alias becomes reusable by every current and future venue.

---

## 10. Alias Provenance

Alias provenance may record:

- source
- source URL
- first observed venue
- first observed date
- raw source wording
- review evidence

Example:

alias:
Serguéi Rajmáninov

canonical:
Serge Rachmaninoff

observed_from:
Auditorio Nacional

The provenance is source-specific.

The alias itself remains global.

Auditorio Nacional does not own the alias.

---

## 11. Alias Normalization

Alias values should represent identity variants, not source formatting noise.

Avoid storing source-only decorations such as:

George Frideric Haendel (1685-1759)

when the useful identity alias is:

George Frideric Haendel

Lifespan may remain in raw source data or matching evidence.

It should not normally become part of the reusable identity alias.

---

## 12. Composer Matching Standard

Composer matching must use:

Global composers
+
Global composer_aliases

Recommended matching precedence:

1. exact canonical name
2. exact alias
3. normalized canonical exact
4. normalized alias exact
5. deterministic collision-safe high-confidence match
6. ambiguous
7. unmatched

Fuzzy matching must not automatically create or assign canonical identity.

Fuzzy similarity may be used only as review evidence unless the matching rule is explicitly deterministic and collision-safe.

---

## 13. Artist Matching Standard

Artist matching must use the global Artist Master.

Identity matching must remain separate from event role.

Example:

raw artist:
Kirill Petrenko

event credit:
conductor

The Artist Matcher resolves identity.

The event relation stores the role.

Do not create different Artist identities for:

Kirill Petrenko — conductor
Kirill Petrenko — music director
Kirill Petrenko — artistic credit

if they refer to the same person.

---

## 14. Work Matching Standard

Work matching must occur only after Composer identity is sufficiently established where Composer identity is relevant.

Preferred evidence includes:

- global composer ID
- original-language canonical title
- work aliases
- catalogue number
- opus number
- key
- work number
- known source title variants

Catalogue identifiers are strong evidence.

Examples:

BWV
K.
KV
Op.
Hob.
D.
RV
S.

must be preserved and used when available.

---

## 15. Composer Identity Before Work Identity

Composer identity should normally be resolved before Work identity.

Recommended sequence:

raw composer
→ global composer_id

raw work
+
global composer_id
→ global work_id

This reduces collisions between generic titles such as:

Symphony No. 1
Piano Concerto
Requiem
Sonata

A Work must not be created merely because the Work matcher fails.

---

## 16. Work Original-Language Rule

Canonical Work titles must use the standard original-language title.

Source-local translations belong in:

raw source data
work_aliases
search layer

They must not overwrite canonical title.

The canonical title should follow the language in which the work is canonically identified or originally titled.

Examples include preserving:

Le nozze di Figaro

rather than replacing it with:

Las bodas de Fígaro

or:

The Marriage of Figaro

as the canonical Work title.

---

## 17. Search and Canonical Identity Are Different Layers

Search convenience must not modify canonical data.

Search may support:

- English title
- common translated title
- localized spelling
- accent-free input
- Latin transliteration
- initials
- abbreviations
- alternate historical spelling

Examples:

Tchaikovsky
Chaikovski
Tchaïkovski
Tschaikowski

may all help locate one global Composer.

Canonical identity remains stable.

---

## 18. Character Matching Standard

Character identity must remain separate from:

- performer
- production
- performance
- casting

Example:

Character:
Wotan

Artist:
Artist A

Performance:
Performance X

Casting:
Performance X
→ Character Wotan
→ Artist A

A new casting does not create a new Wotan Character.

---

## 19. Identity vs Relationship

This distinction is mandatory.

### Global identity

Composer
Artist
Work
Character

### Source-specific or event-specific relationship

Composer ↔ Work
Artist ↔ Performance
Artist ↔ Production
Character ↔ Artist casting
Work ↔ Event programme
Venue ↔ Performance
Organization ↔ Production

Additional event-specific attributes include:

- programme order
- event date
- event time
- cast for that performance
- conductor for that performance
- source URL
- ticket information
- cancellation status
- event-specific artistic team

Different relationships must not create duplicate global entities.

---

## 20. Unmatched Does Not Mean New Entity

An unmatched observation must never automatically create a canonical entity.

Required logic:

Raw Identity
↓
Exact Canonical Search
↓
Alias Search
↓
Normalized Canonical Search
↓
Normalized Alias Search
↓
Collision Review
↓
Ambiguity Review
↓
Possible Existing Identity Review
↓
New Global Entity Candidate

Only after the complete global master has been checked may a record enter:

new global entity staging review

---

## 21. New Global Entity Creation

New Composer, Artist, Work, or Character creation must be an explicit canonical operation.

It must not happen implicitly inside:

- Parser
- scraper
- source adapter
- dry-run
- normalization helper
- event ingestion loop

New entity flow should be:

Unmatched Observation
↓
Global Master Exhausted
↓
Candidate Review
↓
Staging
↓
Validation
↓
Explicit Production Apply

---

## 22. No Match-Rate-Driven Entity Creation

It is forbidden to create canonical entities solely to increase:

- match percentage
- ingestion completion rate
- validation pass rate
- programme coverage

A low match rate is evidence.

It is not permission to create data.

---

## 23. Ambiguity Must Remain Explicit

If identity cannot be proven, the result should remain:

ambiguous
unmatched
review_required

or an equivalent explicit review status.

The Matcher must not:

- choose the most famous person
- assume surname identity
- silently correct malformed source text
- create an entity from weak fuzzy similarity

---

## 24. Name Collisions

Short-form names require collision awareness.

Examples:

Bach
Strauss
Schumann
Scarlatti
Couperin

may refer to multiple people.

Initial forms may also collide.

Example:

J. Strauss

must not be automatically resolved if multiple canonical candidates remain plausible.

---

## 25. Lifespan Data

Lifespan may be used as secondary identity evidence.

Examples:

1685-1750
1833-1897
*1979
ca. 1610-1677

Lifespan may help:

- confirm identity
- reject an impossible candidate
- resolve a collision

Lifespan must not independently create canonical identity.

Source lifespan data must not automatically overwrite canonical metadata.

---

## 26. Multi-Entity Source Strings

Source text may contain multiple identities.

Example:

Claude Debussy / José Luis Turina

This must not create one combined Composer.

Correct representation:

raw:
Claude Debussy / José Luis Turina

components:
- Claude Debussy
- José Luis Turina

Each component must independently match the global Composer Master.

The same principle applies to Artists and other identity types.

---

## 27. Semantic Roles Must Not Be Invented

A source may list multiple names around one Work.

Do not automatically infer:

- composer
- arranger
- orchestrator
- editor
- lyricist

unless the source provides sufficient evidence.

Identity resolution and semantic credit role are separate problems.

---

## 28. Traditional, Anonymous, and Non-Person Attribution

Text such as:

Tradicional
Anonymous
Anónimo
Traditional

must not automatically become a Composer person identity.

Such values belong in a non-person attribution path unless the schema explicitly supports a canonical non-person attribution entity.

Example:

Tradicional de Venezuela / Alonso Mudarra

may contain:

non-person attribution:
Tradicional de Venezuela

named person:
Alonso Mudarra

The named person may enter Composer matching.

The traditional attribution must not be forced into composers.

---

## 29. Malformed Source Data

Malformed source text must be preserved.

Example:

Ludwig van Universo Beethoven

must not be silently rewritten during parsing.

Possible corrected identity may be emitted as review evidence.

Raw source remains unchanged.

Canonical identity may only be assigned when evidence is sufficient under the global matching rules.

---

## 30. False-Positive Identity Protection

Global Matchers must include a safety backstop against obvious non-identity input.

Examples include:

- ensemble abbreviations extracted incorrectly
- cast role names
- instrument names
- job titles
- programme headings
- work titles
- place names
- institution names
- traditional attribution
- freeform programme text

Such values should become:

false_positive_input
not_applicable
review_required

rather than becoming new-entity candidates.

This safety layer does not replace correct Semantic Classification.

It is a final protection boundary.

---

## 31. Canonical Staging

No source ingestion should write uncertain canonical identity directly into production.

Preferred flow:

Matcher Output
↓
Canonical Staging
↓
Validation
↓
Explicit Apply

Staging should preserve:

- raw source value
- proposed canonical ID
- match method
- confidence
- provenance
- ambiguity
- source URL
- source context

---

## 32. Production Mutation

Production identity mutation requires explicit authorization.

Examples include:

- create Composer
- create Artist
- create Work
- create Character
- create alias
- merge identities
- reassign canonical IDs

These must not happen silently during source ingestion.

---

## 33. Venue-Specific Logic Boundary

Venue-specific code should primarily handle:

- source discovery
- pagination
- HTML/API parsing
- source block interpretation
- semantic structure classification
- source-specific formatting

Venue-specific code should not independently redesign canonical identity logic.

For example:

Auditorio parser
Paris Opera parser
Teatro Real parser

may differ significantly.

But after raw identity extraction, they should converge toward reusable global matchers.

---

## 34. Global Matcher Reuse

Preferred architecture:

global composer matcher
global artist matcher
global work matcher
global character matcher

Venue adapters feed structured raw observations into these shared systems.

Do not duplicate Composer matching logic independently for:

Auditorio
Paris Opera
Teatro Real
Wiener Staatsoper
Philharmonie de Paris

unless source-specific preprocessing is required.

Source extraction may differ.

Canonical identity logic should converge.

---

## 35. Global Knowledge Accumulation

Every successfully reviewed source should improve the global canonical layer.

Example:

Auditorio discovers a valid Composer alias:

Serguéi Rajmáninov
→ Serge Rachmaninoff

After global review and insertion into:

composer_aliases

the same alias should immediately benefit:

- Paris Opera
- Teatro Real
- Wiener Staatsoper
- Philharmonie de Paris
- future sources

Canonical knowledge must accumulate globally.

It must not remain trapped inside one venue pipeline.

---

## 36. Event / Production / Performance Ownership

The following entities and relations are legitimately source-specific or event-specific:

organization
venue
production
performance/event
event date
event time
programme order
performance-specific cast
production-specific cast
performance-specific conductor
artistic team
ticket information
source URL
source provenance
source status

These records may reference global canonical IDs.

Example:

performance_id
work_id
programme_order

or:

performance_id
artist_id
role

---

## 37. Work → Production → Performance Hierarchy

Where applicable, Byelingua should preserve the distinction:

Work
↓
Production
↓
Performance

Work is global.

Production represents a specific staged or programmed realization.

Performance represents an actual scheduled occurrence.

Do not duplicate the Work because multiple productions exist.

Do not duplicate the Production merely because multiple performances exist unless production identity genuinely differs.

---

## 38. Venue and Organization Are Different

Venue and Organization must remain separate concepts.

Example:

Organization:
Orquesta y Coro Nacionales de España

Venue:
Auditorio Nacional de Música

They may participate in the same Event but must not be treated as interchangeable identity fields.

Source-specific filtering must respect this distinction.

---

## 39. Cancellation and Source Failure

Parser failure, HTTP failure, or source discovery failure must not automatically imply:

cancelled
deleted
removed

Existing production data must not be deleted solely because a scrape failed.

Cancellation requires positive source evidence or another explicit lifecycle rule.

---

## 40. Dry-Run Requirement

New or repaired ingestion stages should support dry-run before production mutation.

Recommended workflow:

parser dry-run
→ matcher dry-run
→ staging dry-run
→ validation
→ explicit apply

Dry-run artifacts should be inspectable and reproducible.

---

## 41. Auditability

Each canonical relationship should remain traceable to source evidence where practical.

Important provenance includes:

- source name
- source URL
- raw source wording
- ingestion run
- parser version
- matcher version
- matching method
- source timestamp

Canonical identity must not erase provenance.

---

## 42. Review Statuses

Recommended review vocabulary includes:

exact
alias
normalized_exact
normalized_alias
high_confidence
ambiguous
unmatched
false_positive_input
attribution_review
new_global_entity_candidate

Existing repository conventions may use equivalent names.

The important requirement is that uncertainty remains explicit.

---

## 43. Current Global Master Must Be Used

Matchers must use the current global canonical layer.

They must not assume that a historical snapshot remains complete.

Before a major ingestion run, the Matcher should load or create a reproducible read-only snapshot of the current relevant global Master where appropriate.

Example:

composer-master-snapshot.json

may be generated for reproducibility.

The snapshot represents the global Master at that moment.

It does not become a venue-specific identity database.

---

## 44. Historical Artifacts

Historical artifacts may contain incomplete or outdated canonical mappings.

They may be used to:

- understand past decisions
- run regressions
- investigate bugs
- compare ingestion results

They must not override current canonical data automatically.

Current global canonical data is authoritative unless an explicit migration or correction process says otherwise.

---

## 45. Legacy Code

Legacy code may violate this standard.

Example violations may include:

- Parser creating Work
- Parser creating Artist
- venue module directly inserting canonical identity
- find_or_create_work() inside source ingestion
- historical per-source matching universe

Legacy code must not be treated as architectural precedent merely because it already exists.

When encountered, classify it as:

ACTIVE VIOLATION
LEGACY VIOLATION
HISTORICAL ARTIFACT
NOT A VIOLATION

Repair should follow a separate controlled task.

---

## 46. Active Architecture Takes Priority

If historical code, comments, scripts, or artifacts contradict this document, the intended architecture in this document takes precedence unless a newer explicitly approved repository standard supersedes it.

Do not reproduce an old violation in new code for consistency.

---

## 47. Canonical Safety Checklist

Before any new venue ingestion reaches canonical staging, verify:

- [ ] Parser only describes source data.
- [ ] Composer matching uses global Composer Master.
- [ ] Artist matching uses global Artist Master.
- [ ] Work matching uses global Work Master.
- [ ] Character matching uses global Character Master where applicable.
- [ ] Source artifacts are not used as canonical masters.
- [ ] Existing aliases are reused.
- [ ] New aliases are global proposals.
- [ ] Unmatched does not auto-create entities.
- [ ] Ambiguous identities remain explicit.
- [ ] Canonical Work titles preserve original-language standard.
- [ ] Raw source wording remains available.
- [ ] Venue and organization remain distinct.
- [ ] Production and performance identity remain distinct.
- [ ] No failed scrape deletes valid production data.
- [ ] Dry-run exists before production mutation.
- [ ] Database mutation is explicitly authorized.

---

## 48. Canonical Entity Creation Checklist

Before approving a new global Composer, Artist, Work, or Character:

- [ ] Exact canonical lookup performed.
- [ ] Alias lookup performed.
- [ ] Normalized canonical lookup performed.
- [ ] Normalized alias lookup performed.
- [ ] Collision check performed.
- [ ] Existing candidate identities reviewed.
- [ ] Source provenance preserved.
- [ ] Entity type confirmed.
- [ ] False-positive input excluded.
- [ ] Ambiguity resolved or explicitly accepted for review.
- [ ] Creation is global, not venue-specific.
- [ ] Production mutation is explicitly authorized.

---

## 49. Global Alias Creation Checklist

Before approving a new alias:

- [ ] Canonical entity already exists.
- [ ] Alias does not already exist globally.
- [ ] Normalized equivalent does not already exist.
- [ ] Alias does not contain unnecessary source formatting.
- [ ] Lifespan is not embedded unnecessarily.
- [ ] Alias points to the correct global entity ID.
- [ ] Source provenance is recorded where useful.
- [ ] Alias is not restricted to one venue.
- [ ] Collision risk has been checked.
- [ ] Production write is explicitly authorized.

---

## 50. Definition of Done for Venue Identity Ingestion

A venue identity-ingestion phase is not complete merely because all source strings received IDs.

It is complete when:

- raw source data is preserved
- semantic structure is valid
- global masters were used
- successful matches reuse global IDs
- aliases are global
- ambiguity is surfaced
- false positives are excluded
- unmatched identities are reviewed
- new entities are staged rather than auto-created
- canonical Work titles follow original-language rules
- provenance is preserved
- no unauthorized production mutation occurred

---

## 51. Guiding Principle

The fundamental rule is:

A venue describes what happened there.

The Byelingua global canonical layer defines who and what the entities are.

Operationally:

Source-specific knowledge
        ↓
Raw observation
        ↓
Global identity resolution
        ↓
Shared canonical knowledge

Byelingua must accumulate canonical knowledge globally rather than create isolated venue-specific identity silos.