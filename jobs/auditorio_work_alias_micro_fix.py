"""One accepted Work-alias hygiene correction; no classification changes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
STAGING = OUT / "auditorio-work-final-production-staging.json"
FIXTURE = Path("/private/tmp/auditorio-phase3-checkpoint-20260820/.work-master-fixture.json")
sys.path.insert(0, str(ROOT / "jobs"))
from auditorio_work_match_dry_run import _write_sql  # noqa: E402

TARGET = "ee0c1ff0-357b-48d3-9fb9-ebe72e35c571"

doc = json.loads(STAGING.read_text())
actions = doc["actions"]
matches = [a for a in actions if a.get("action") == "create_work_alias" and a.get("work_id") == TARGET]
assert len(matches) == 1
assert matches[0]["alias"] == "Mahler.- Sinfonía núm 2 “Resurrección”"
matches[0]["alias"] = "Sinfonía núm. 2 “Resurrección”"

aliases = [a for a in actions if a.get("action") == "create_work_alias"]
assert sum(a.get("work_id") is None for a in aliases) == 0
assert len({(a["work_id"], a["alias"]) for a in aliases}) == len(aliases)
assert len(actions) == 730
assert sum(a["action"] == "create_work" for a in actions) == 16
assert len(aliases) == 34
assert sum(a["action"] == "update_existing_work_composer_id" for a in actions) == 149
assert sum(a["action"] == "update_existing_work_identity_key" for a in actions) == 517
assert sum(a["action"] == "correct_existing_work_canonical_title" for a in actions) == 14

doc["actions"] = actions
doc["database_writes"] = 0
doc["summary"].update({
    "planned_actions": 730,
    "planned_create_work": 16,
    "planned_create_work_alias": 34,
    "planned_composer_repairs": 149,
    "planned_identity_key_repairs": 517,
    "canonical_work_corrections": 14,
    "expected_post_apply_work_count": 3229,
    "expected_post_apply_work_alias_count": 99,
    "database_writes": 0,
})
STAGING.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
_write_sql(OUT, json.loads(FIXTURE.read_text()), actions)

sql = (OUT / "auditorio-work-final-production-apply.sql").read_text()
assert "'None'::uuid" not in sql
assert "event_programme" not in sql
print(json.dumps(doc["summary"], ensure_ascii=False, indent=2))
