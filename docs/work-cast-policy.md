# Shared Work-role selection

The database global Work and Character masters own canonical identity. Existing
`work_characters` rows describe a Work's role slots; `event_credits.character_id`
references `work_characters.id`, not `characters.id`. The separate
`character_uid` may remain unresolved on legacy rows.

`work_cast_registry.WORK_CAST_POLICIES` holds reviewed principal-role display
policies keyed by global Work ID. This is one shared policy registry for all
venues, not a canonical entity table. It currently preserves the 57 previously
reviewed Work policies. Unlisted roles remain unclassified; no automatic
supporting-role label is assigned.

`work_cast_policy` is consumed by ingestion, event detail and schedule summary:

1. Match the observed Work against the global master.
2. Resolve its role against the global Work-role graph.
3. Apply the reviewed principal display policy.
4. Match the published performer against the global Artist master.
5. Store/use the dated performance relationship.

Roles and principal priority belong to the Work policy. Performers and conducting
assignments belong to the particular performance. Never inherit an adjacent
date's cast, or substitute another performance when its relations are missing.

A legacy source type `performance` cannot suppress reviewed principal roles
when the programme identifies a verified full Work. Explicit ballet, concert,
workshop and other presentations keep their existing gates. This selection rule
does not change event genres, infer a Work from its title, create aliases or
assign canonical Character IDs from text.

A linked Work-role must match the performed Work and an explicitly reviewed role
ID. An unknown linked role is never reinterpreted by raw spelling. Source-only
credits may use an exact reviewed spelling within a uniquely matching performed
Work, retaining no canonical Character ID.

The detail endpoint exposes the existing complete Work-role skeleton, including
unclassified roles, without filling artist names. It and the schedule summary
use the same principal selection function. Existing webpage and PNG renderers
consume the resulting summary without layout changes.

Validation: `test_work_cast_policy.py` covers shared registry ownership, generic
source types, negative presentation cases, Work boundaries, unresolved identity,
per-performance actor separation, and detail/summary agreement. Existing summary,
ingestion factory and pagination regressions must remain valid.
