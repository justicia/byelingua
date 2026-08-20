"""Production preflight repair over the accepted Work staging only."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
STAGING = OUT / "auditorio-work-final-production-staging.json"
FIXTURE = Path("/private/tmp/auditorio-phase3-checkpoint-20260820/.work-master-fixture.json")
sys.path.insert(0, str(ROOT / "jobs"))
from auditorio_work_match_dry_run import identity_key, title_key, _write_sql  # noqa: E402

REUSE = {
    826: ("ee0c1ff0-357b-48d3-9fb9-ebe72e35c571", "Sinfonie Nr. 2 in c-Moll “Auferstehung”", "Mahler.- Sinfonía núm 2 “Resurrección”"),
    640: ("695e6a60-ff3e-42ac-aecb-b931ef589a05", "Fantasie in C-Dur, D 760 “Wanderer-Fantasie”", "Fantasie in C Major, D.760, «Wanderer-Fantasie»"),
    835: ("86125da7-ccd1-4f02-aa2e-a26e4f7fdee1", "Concerto in la minore, Op. 3 n. 8, RV 522", "Concierto L’estro Armonico Op.3 N8"),
    836: ("0929efa0-e7d0-4d4f-9d80-d3cfeda607da", "Concerto in re minore, Op. 3 n. 11, RV 565", "Concerto grosso Op.3 N11"),
}
COMPOSERS = {
    "ee0c1ff0-357b-48d3-9fb9-ebe72e35c571": "25aab104-1c65-42ea-9338-852db4c79592",
    "695e6a60-ff3e-42ac-aecb-b931ef589a05": "ad628acd-96a8-404a-821c-6dda86b5fcbf",
    "86125da7-ccd1-4f02-aa2e-a26e4f7fdee1": "7e522176-a71f-4ce2-92e5-9e22b960323b",
    "0929efa0-e7d0-4d4f-9d80-d3cfeda607da": "7e522176-a71f-4ce2-92e5-9e22b960323b",
}


def main() -> None:
    doc = json.loads(STAGING.read_text())
    master = json.loads(FIXTURE.read_text())
    by_id = {w["id"]: w for w in master["works"]}
    actions = [dict(a) for a in doc["actions"]]

    # Convert exactly four confirmed creates into existing Work reuse/repair.
    creates = {a["source_occurrence_id"]: a for a in actions if a["action"] == "create_work"}
    removed_ids = {creates[n]["id"] for n in REUSE if n in creates}
    actions = [a for a in actions if not (a["action"] == "create_work" and a.get("source_occurrence_id") in REUSE)]
    for n, (wid, title, alias) in REUSE.items():
        if n not in creates:
            continue
        old = by_id[wid]["title"]
        cid = COMPOSERS[wid]
        actions = [a for a in actions if not (a["action"] == "update_existing_work_identity_key" and a.get("work_id") == wid)]
        actions.append({"action": "correct_existing_work_canonical_title", "work_id": wid, "canonical_title": title, "expected_old_title": old, "composer_id": cid, "source_occurrence_id": n})
        # Replace any alias formerly attached to the discarded staged UUID.
        for a in list(actions):
            if a["action"] == "create_work_alias" and a.get("work_id") == creates[n]["id"]:
                a["work_id"] = wid
                a["alias"] = alias
        actions.append({"action": "update_existing_work_identity_key", "work_id": wid, "identity_key": identity_key(cid, title), "source_occurrence_id": n})

    # Remove stale NULL-only Composer repairs where production is already correct.
    stale = {"4f3de1d5-3257-4c97-ab7a-d6ddbf3055cd", "22301c44-e4b9-49a7-8258-f9f13442e410"}
    actions = [a for a in actions if not (a["action"] == "update_existing_work_composer_id" and a.get("work_id") in stale)]

    # Clean only obvious parser debris from proposed aliases; raw evidence remains untouched.
    cleaned = []
    for a in actions:
        if a["action"] != "create_work_alias":
            cleaned.append(a)
            continue
        alias = a["alias"]
        alias = re.sub(r"^\([^)]*\)\s*[–-]\s*", "", alias)
        alias = re.sub(r"^(?:J\.\s*Haydn|W\.\s*A\.\s*Mozart)\s*[–-]\s*", "", alias)
        alias = re.sub(r"\s*\([^()]*\d{4}[^()]*\)", "", alias).strip()
        if alias.lower().startswith("para órgano en do menor"):
            continue
        if "(arr. David Walter)" in alias:
            alias = alias.replace(" (arr. David Walter)", "")
        a["alias"] = alias
        cleaned.append(a)
    actions = cleaned

    # Add old-title snapshots to every canonical correction for safe apply-time branching.
    for a in actions:
        if a["action"] == "correct_existing_work_canonical_title":
            if "expected_old_title" not in a:
                a["expected_old_title"] = by_id[a["work_id"]]["title"]
            if "composer_id" not in a:
                a["composer_id"] = next((x["composer_id"] for x in actions if x["action"] == "update_existing_work_composer_id" and x.get("work_id") == a["work_id"]), by_id[a["work_id"]].get("composer_id"))

    # Remove exact duplicate mutations while preserving the accepted classifications.
    unique = {}
    for a in actions:
        key = (a["action"], a.get("work_id", a.get("id")), a.get("alias"), a.get("identity_key"), a.get("composer_id"), a.get("canonical_title"))
        unique[key] = a
    actions = list(unique.values())

    # Required hard assertions.
    aliases = [a for a in actions if a["action"] == "create_work_alias"]
    creates = [a for a in actions if a["action"] == "create_work"]
    assert sum(a.get("work_id") is None for a in aliases) == 0
    assert len({(a["work_id"], a["alias"]) for a in aliases}) == len(aliases)
    assert len({a["id"] for a in creates}) == len(creates)
    identity_by_work = defaultdict(set)
    composer_by_work = defaultdict(set)
    for a in actions:
        if a["action"] == "update_existing_work_identity_key": identity_by_work[a["work_id"]].add(a["identity_key"])
        if a["action"] == "update_existing_work_composer_id": composer_by_work[a["work_id"]].add(a["composer_id"])
    for a in creates:
        identity_by_work[a["id"]].add(a["identity_key"]); composer_by_work[a["id"]].add(a["composer_id"])
    assert all(len(v) <= 1 for v in identity_by_work.values())
    assert all(len(v) <= 1 for v in composer_by_work.values())
    assert len({next(iter(v)) for v in identity_by_work.values()}) == len(identity_by_work)
    assert not any(a["action"] == "update_existing_work_composer_id" and a["work_id"] in stale for a in actions)
    assert not any(a["action"] == "create_work_alias" and a.get("work_id") in removed_ids for a in actions)
    alias_by_work = defaultdict(list)
    for a in master.get("aliases", []): alias_by_work[a["work_id"]].append(a["alias"])
    for a in creates:
        assert a["id"] not in by_id
        duplicate = [w for w in master["works"] if w.get("composer_id") == a["composer_id"] and title_key(w.get("title", "")) == title_key(a["title"])]
        duplicate += [w for w in master["works"] if w.get("composer_id") == a["composer_id"] and any(title_key(x) == title_key(a["title"]) for x in alias_by_work[w["id"]])]
        assert not duplicate, (a, duplicate)

    _write_sql(OUT, master, actions)
    summary = dict(doc.get("summary", {}))
    status_counts = dict(summary.get("status_counts", {}))
    status_counts["confirmed_new_global_work"] = status_counts.get("confirmed_new_global_work", 0) - 4
    status_counts["existing_work_needs_identity_key"] = status_counts.get("existing_work_needs_identity_key", 0) + 4
    summary.update({
        "status_counts": status_counts,
        "preflight_existing_work_reuse": 4,
        "existing_works_recovered": summary.get("existing_works_recovered", 0) + 4,
        "planned_actions": len(actions),
        "planned_create_work": sum(a["action"] == "create_work" for a in actions),
        "new_works_confirmed": sum(a["action"] == "create_work" for a in actions),
        "planned_create_work_alias": sum(a["action"] == "create_work_alias" for a in actions),
        "planned_composer_repairs": sum(a["action"] == "update_existing_work_composer_id" for a in actions),
        "planned_identity_key_repairs": sum(a["action"] == "update_existing_work_identity_key" for a in actions),
        "canonical_work_corrections": sum(a["action"] == "correct_existing_work_canonical_title" for a in actions),
        "expected_post_apply_work_count": len(master["works"]) + sum(a["action"] == "create_work" for a in actions),
        "expected_post_apply_work_alias_count": len(master.get("aliases", [])) + sum(a["action"] == "create_work_alias" for a in actions),
        "database_writes": 0,
    })
    doc["actions"] = actions; doc["summary"] = summary; doc["database_writes"] = 0
    STAGING.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
