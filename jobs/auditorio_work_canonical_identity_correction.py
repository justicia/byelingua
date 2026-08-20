"""Narrow final canonical-title/identity correction pass.

Reads only accepted staging and the captured production fixture. No research,
reconciliation, SQL execution, or candidate reclassification is performed.
"""
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
from auditorio_work_match_dry_run import identity_key, _write_sql  # noqa: E402

CREATE_TITLES = {
    24: "Quintetto in Re maggiore, Op. 39 n. 3, G. 339",
    25: "Quintette à cordes en mi mineur, Op. 74",
    26: "Deuxième quintette à cordes, Op. 316",
    40: "In the South (Alassio), Op. 50",
    90: "Suite Nr. 4 für Violoncello solo in Es-Dur, BWV 1010",
    826: "Sinfonie Nr. 2 in c-Moll “Auferstehung”",
    1123: "Smyčcový kvartet č. 12 F dur, op. 96, B. 179 “Americký”",
    194: "La cathédrale engloutie, L. 117, CD 109 No. 10",
    584: "Passacaglia und Fuge in c-Moll, BWV 582",
    640: "Fantasie in C-Dur, D 760 “Wanderer-Fantasie”",
    782: "Ich ruf zu dir, Herr Jesu Christ, BWV 639",
    808: "Sinfonia in La maggiore, Op. 35 n. 3, G. 511",
    815: "Concerto per violino in si minore, RV 389",
    835: "Concerto in la minore, Op. 3 n. 8, RV 522",
    836: "Concerto in re minore, Op. 3 n. 11, RV 565",
    841: "Concerto alla rustica in sol maggiore, RV 151",
    1250: "Symphonie de psaumes",
    1251: "Cello Concerto in E minor, Op. 85",
    705: "Motet pour les trépassés, H. 311",
    706: "Annunciate superi, H. 333",
}

EXISTING_TITLES = {
    "3c759e0a-a0dc-4aa4-a56d-24f2c3f0e8df": "Sinfonie Nr. 1 in C-Dur, op. 21",
    "e73f3291-919f-40a4-8ec1-5b259f315f3d": "Sinfonie Nr. 4 in B-Dur, op. 60",
    "4579d8d5-c931-4a09-91df-e87d87746002": "Sinfonie Nr. 5 in c-Moll, op. 67",
    "e5b7b0d0-81ef-4d98-ba06-a323a7a567ed": "La mer, L. 109, CD 111",
    "4f3de1d5-3257-4c97-ab7a-d6ddbf3055cd": "Sinfonie Nr. 1 in D-Dur “Titan”",
    "14c4592b-b94c-40cd-b74a-d9ccd7ff6573": "Cuarteto con piano en la menor, op. 67",
    "69466d28-bc11-4182-9bdc-1112a51f9628": "Trio in a-Moll für Klarinette, Violoncello und Klavier, op. 114",
    "fa076544-1b8d-42cf-b0d6-831d03f03f19": "Konzert für Horn Nr. 1 in D-Dur, K. 412/386b",
    "32c1fcb3-c18f-4b6d-9e92-9584bba0bdb1": "Sinfonia in F-Dur, F. 67 “Dissonanzen”",
    "22301c44-e4b9-49a7-8258-f9f13442e410": "Toccata und Fuge in d-Moll, BWV 565",
}


def main() -> None:
    doc = json.loads(STAGING.read_text())
    master = json.loads(FIXTURE.read_text())
    actions = [dict(a) for a in doc["actions"]]
    create = [a for a in actions if a["action"] == "create_work"]
    corrections = {a["work_id"]: a for a in actions if a["action"] == "correct_existing_work_canonical_title"}
    assert len(create) == 20
    assert len(corrections) == 10

    # Canonical title audit for every new Work.
    for a in create:
        title = CREATE_TITLES[a["source_occurrence_id"]]
        a["title"] = title
        a["identity_key"] = identity_key(a["composer_id"], title)

    # Canonical title audit for every existing correction and its paired identity repair.
    composer_by_work = {a["work_id"]: a["composer_id"] for a in actions if a["action"] == "update_existing_work_composer_id"}
    composer_by_work.update({
        "69466d28-bc11-4182-9bdc-1112a51f9628": "2cffa372-2bc9-4321-bf4e-4a17aa772418",
    })
    for wid, correction in corrections.items():
        title = EXISTING_TITLES[wid]
        correction["canonical_title"] = title
        cid = composer_by_work[wid]
        expected = identity_key(cid, title)
        matched = [a for a in actions if a["action"] == "update_existing_work_identity_key" and a["work_id"] == wid]
        assert len(matched) == 1, (wid, matched)
        matched[0]["identity_key"] = expected

    # Preserve clean Spanish source aliases; repair only the contaminated G.511 alias.
    g511 = next(a for a in create if a["source_occurrence_id"] == 808)
    aliases = [a for a in actions if a["action"] == "create_work_alias" and a.get("work_id") == g511["id"]]
    assert len(aliases) == 1
    aliases[0]["alias"] = "Sinfonía en La mayor, op. 35 n.º 3, G 511"
    # Remove parser lifespan prefixes from every staged Work alias.
    for a in alias_actions if 'alias_actions' in locals() else [x for x in actions if x["action"] == "create_work_alias"]:
        a["alias"] = re.sub(r"^\(\d{4}[–-]\d{4}\)\s*[–-]\s*", "", a["alias"])

    # Batch hard assertions.
    alias_actions = [a for a in actions if a["action"] == "create_work_alias"]
    assert sum(a.get("work_id") is None for a in alias_actions) == 0
    assert len({(a["work_id"], a["alias"]) for a in alias_actions}) == len(alias_actions)
    identity_by_work = defaultdict(set)
    composer_by_target = defaultdict(set)
    for a in actions:
        if a["action"] == "update_existing_work_identity_key": identity_by_work[a["work_id"]].add(a["identity_key"])
        if a["action"] == "update_existing_work_composer_id": composer_by_target[a["work_id"]].add(a["composer_id"])
    for a in create:
        identity_by_work[a["id"]].add(a["identity_key"])
        composer_by_target[a["id"]].add(a["composer_id"])
    assert all(len(v) <= 1 for v in identity_by_work.values())
    assert all(len(v) <= 1 for v in composer_by_target.values())
    all_staged_identity_keys = [next(iter(v)) for v in identity_by_work.values()]
    assert len(all_staged_identity_keys) == len(set(all_staged_identity_keys))
    assert all(not re.search(r"^\(\d{4}[–-]\d{4}\)", a["alias"]) for a in alias_actions)
    assert g511["title"] == "Sinfonia in La maggiore, Op. 35 n. 3, G. 511"
    g339 = next(a for a in create if a["source_occurrence_id"] == 24)
    assert "Re maggiore" in g339["title"] and "La maggiore" not in g339["title"]
    assert "Sinfonia" in g511["title"] and "Quintetto" not in g511["title"]

    # Reuse the generator's complete batch validation and SQL safety assertions.
    _write_sql(OUT, master, actions)
    summary = dict(doc.get("summary", {}))
    summary.update({
        "planned_actions": len(actions),
        "planned_create_work": sum(a["action"] == "create_work" for a in actions),
        "planned_create_work_alias": sum(a["action"] == "create_work_alias" for a in actions),
        "planned_composer_repairs": sum(a["action"] == "update_existing_work_composer_id" for a in actions),
        "planned_identity_key_repairs": sum(a["action"] == "update_existing_work_identity_key" for a in actions),
        "canonical_work_corrections": sum(a["action"] == "correct_existing_work_canonical_title" for a in actions),
        "expected_post_apply_work_count": len(master["works"]) + sum(a["action"] == "create_work" for a in actions),
        "expected_post_apply_work_alias_count": len(master.get("aliases", [])) + sum(a["action"] == "create_work_alias" for a in actions),
        "database_writes": 0,
    })
    doc["actions"] = actions
    doc["summary"] = summary
    doc["database_writes"] = 0
    STAGING.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
