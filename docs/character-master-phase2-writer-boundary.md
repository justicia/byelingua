# Character Master V1 Phase 2 writer boundary

Phase 2 is evidence and staging only. `jobs/build_character_master_phase2.py`
does not import or call `season_ingestion/character_writer.py`, and it does
not call `upsert_global_character`, `upsert_work_character`, or
`upsert_character_aliases`.

The existing writer remains disabled until a separately approved apply phase.
Before it can be used, it must consume only approved `SAFE_*` staging rows,
carry the exact `work_character_id`, update that legacy relationship by ID,
execute the identity/alias/relationship changes atomically, and reject every
`REVIEW_*`, contamination, ensemble, voice-type, or unresolved composite row.
It must never identify a legacy relationship only by `canonical_name` and
must never create a `REVIEW` row.

The Phase 2 artifacts are local evidence, not a second Global Master and not
an instruction to copy registry contents into production.
