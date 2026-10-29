# Shared Work-role selection

The database global Work and Character masters own canonical identity. Existing
`work_characters` rows describe a Work's role slots; `event_credits.character_id`
references `work_characters.id`, not `characters.id`. The separate
`character_uid` may remain unresolved on legacy rows.

`work_cast_registry.WORK_CAST_POLICIES` holds reviewed principal-role display
policies keyed by global Work ID. This is one shared policy registry for all
venues, not a canonical entity table. It preserves the 57 previously reviewed Work policies and adds thirteen
source-reviewed policies from the global stock-data review (70 existing Work IDs in total). Unlisted roles remain unclassified; no automatic
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

The additions cover Hänsel und Gretel, Katia Kabanová, Nabucco, Lohengrin,
Adriana Lecouvreur, Nixon in China, Pagliacci, Die lustige Witwe and
Příhody lišky Bystroušky, Der Miesepups, Maria Stuarda and
A kékszakállú herceg vára. The two existing
Katia/Káťa Kabanová IDs each use their own stored role slots or exact reviewed
source spellings; the stock Work-ID duplication remains separately under review.
This does not merge or reassign either Work identity. This is reviewed policy coverage, not a declaration
that every performance has complete programme or cast relations. Review
evidence and the remaining stock-data queue are in the global repair artifacts.

Legacy role-in-function credits are read through the same Work-role policy.
Only a unique exact match in a verified performed Work can supply a display
role; function/voice labels alone cannot. Detail may also reuse its already
loaded full Work-role schema. No canonical Character ID is assigned this way.
Explicit cast observations or reviewed role labels remain cast even when the
source function also names the singer’s voice type.

Broad source containers called “cast” can include conductors, orchestras and
chorus directors. The shared layer keeps recognized artistic functions separate
from dramatic characters. Existing linked Work-role identity is never rewritten
by this display compatibility; detail also preserves a known dramatic role from
its full Work-role graph. Ingestion holds contradictory function/character input
for source review instead of fabricating an assignment.
