"""Finalize only the previously unresolved Auditorio Work rows.

This is deliberately a residual post-processor: it reads the already accepted
staging and changes only rows whose current final_status is unresolved_work.
It never connects to Supabase and never reads or rewrites raw source evidence.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
REVIEW = OUT / "auditorio-work-final-consolidation-review.json"
STAGING = OUT / "auditorio-work-final-production-staging.json"
FIXTURE = Path("/private/tmp/auditorio-phase3-checkpoint-20260820/.work-master-fixture.json")
sys.path.insert(0, str(ROOT / "jobs"))
from auditorio_work_match_dry_run import identity_key, _write_sql  # noqa: E402

COMPOSERS = {
    "Bach": "0cb43b06-7258-4cb5-84cd-ab7f79e407e4",
    "Debussy": "36ec6fc4-e55c-4e87-80c8-01402609b286",
    "Schubert": "ad628acd-96a8-404a-821c-6dda86b5fcbf",
    "Vivaldi": "7e522176-a71f-4ce2-92e5-9e22b960323b",
    "Mahler": "25aab104-1c65-42ea-9338-852db4c79592",
    "Turina": "3e89c077-38cd-411a-a8b0-e95ba40c5e6a",
    "WFB": "32f9b04e-99a7-4953-b9c2-73655fbe4bab",
    "Mozart": "8fa0e4e1-883d-468e-a062-c743b7601a1f",
    "Boccherini": "2306b0e9-58fb-4cc2-8061-0b6d49e1f310",
    "Stravinsky": "63c53106-3321-4af3-8d17-b04806facc1c",
    "Elgar": "21826de0-1e32-4c72-96e1-2c7c3c2665f2",
    "Charpentier": "d52ab28f-7795-4372-9e45-9664e6f38e64",
    "Handel": "8cfdf8f7-929a-48bc-9400-cd88d41c5904",
}

ORIGINAL_TITLES = {
    'String Quintet in D major, G.339': 'Quintetto in Re maggiore, Op. 39 n. 3, G. 339',
    'String Quintet No. 30 in E minor, Op. 74': 'Quintette à cordes en mi mineur, Op. 74',
    'String Quintet No. 2, Op. 316': 'Deuxième quintette à cordes, Op. 316',
    'Symphony No. 2 in C minor “Resurrection”': 'Sinfonie Nr. 2 in c-Moll “Auferstehung”',
    'String Quartet No. 12 in F major, Op. 96, B.179 “American”': 'Streichquartett Nr. 12 in F-Dur, op. 96, B. 179 “Amerikanisches”',
    'Passacaglia and Fugue in C minor, BWV 582': 'Passacaglia und Fuge in c-Moll, BWV 582',
    'Fantasie in C major, D. 760 “Wanderer”': 'Fantasie in C-Dur, D 760 “Wanderer-Fantasie”',
    'String Quintet in A major, G. 511': 'Sinfonia in La maggiore, Op. 35 n. 3, G. 511',
    'Violin Concerto in B minor, RV 389': 'Concerto per violino in si minore, RV 389',
    'Concerto in A minor, Op. 3 No. 8, RV 522': 'Concerto in la minore, Op. 3 n. 8, RV 522',
    'Concerto in D minor, Op. 3 No. 11, RV 565': 'Concerto in re minore, Op. 3 n. 11, RV 565',
    'Concerto alla rustica in G major, RV 151': 'Concerto alla rustica in sol maggiore, RV 151',
    'Symphony of Psalms': 'Symphonie de psaumes',
    'Motet pour les trépassés, H. 311': 'Motet pour les trépassés, H. 311',
    'Annunciate superi, H. 333': 'Annunciate superi, H. 333',
}


def repair_actions(actions, rows, master):
    """Repair staged mutations without changing accepted candidate matching."""
    # Recover null aliases from the deterministic create_work action at the same occurrence.
    creates_by_occ = {a.get('source_occurrence_id'): a for a in actions if a.get('action') == 'create_work'}
    repaired = []
    for a in actions:
        a = dict(a)
        if a.get('action') == 'create_work_alias' and a.get('work_id') is None:
            owner = creates_by_occ.get(a.get('source_occurrence_id'))
            if owner is None:
                raise AssertionError(f"alias has no deterministic staged Work: {a}")
            a['work_id'] = owner['id']
        repaired.append(a)

    # One Work UUID gets one identity. These selections use source occurrence and
    # production/composer context, never action order.
    keep = {
        '69beed2a-a2fc-49b8-b91e-cb6b1efdf1fe': 'work:6a4757fd634aca84dbd44bcba8d64bd8',
        '22301c44-e4b9-49a7-8258-f9f13442e410': 'work:a1a7d16e1f002950321ac7fb2d5779de',
        'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed': 'work:f3e5c0ef8c370eb6a6fa8d9ca8f93cab',
        '4579d8d5-c931-4a09-91df-e87d87746002': 'work:70f5300b58ac7923896225ee110c113e',
    }
    out = []
    for a in repaired:
        if a.get('action') == 'update_existing_work_identity_key' and a.get('work_id') in keep:
            if a.get('identity_key') != keep[a['work_id']]:
                continue
        out.append(a)

    # Original-language canonical title gate for every new Work.
    for a in out:
        if a.get('action') != 'create_work':
            continue
        old = a['title']
        if old in ORIGINAL_TITLES:
            a['title'] = ORIGINAL_TITLES[old]
            a['identity_key'] = identity_key(a['composer_id'], a['title'])

    # Deduplicate by mutation target; aliases specifically by (Work, alias).
    unique = {}
    for a in out:
        if a.get('action') == 'create_work_alias':
            key = ('create_work_alias', a['work_id'], a['alias'])
        else:
            key = tuple(sorted((k, v) for k, v in a.items() if k != 'source_occurrence_id'))
        unique[key] = a
    out = list(unique.values())

    alias_actions = [a for a in out if a.get('action') == 'create_work_alias']
    for a in alias_actions:
        a['alias'] = re.sub(r"^\(\d{4}[–-]\d{4}\)\s*[–-]\s*", "", a['alias'])
    assert all(a.get('work_id') is not None for a in alias_actions)
    identity_actions = {}
    for a in out:
        if a.get('action') == 'update_existing_work_identity_key':
            identity_actions.setdefault(a['work_id'], set()).add(a['identity_key'])
    assert all(len(keys) <= 1 for keys in identity_actions.values())
    new_works = [a for a in out if a.get('action') == 'create_work']
    assert len({a['id'] for a in new_works}) == len(new_works)
    assert len({a['identity_key'] for a in new_works}) == len(new_works)
    assert len({(a['work_id'], a['alias']) for a in alias_actions}) == len(alias_actions)
    assert all(a.get('composer_id') for a in new_works)
    assert all(a.get('identity_key') for a in new_works)
    return out


def new_work(row, title, composer, alias=None):
    cid = COMPOSERS[composer]
    wid = str(uuid5(NAMESPACE_URL, f"auditorio-work:{cid}:{title}"))
    row["final_status"] = "confirmed_new_global_work"
    row["existing_work_id"] = None
    row["canonical_original_title"] = title
    row["proposed_new_work"] = {"id": wid, "title": title, "composer_id": cid,
                                "identity_key": identity_key(cid, title), "work_kind": "work"}
    row["proposed_aliases"] = [alias or row["raw_work_title"]]
    row["proposed_repairs"] = {}
    row["confidence"] = "high"
    row["review_reason"] = "catalogue_stable_identity_confirmed_in_residual_audit"


def existing(row, wid, status, composer=None, title=None, alias=False):
    row["final_status"] = status
    row["existing_work_id"] = wid
    row["proposed_new_work"] = None
    row["proposed_aliases"] = [row["raw_work_title"]] if alias else []
    repairs = {}
    if composer:
        repairs["composer_id"] = composer
    if title:
        repairs["canonical_title"] = title
    if composer and title:
        repairs["identity_key"] = identity_key(composer, title)
    row["proposed_repairs"] = repairs
    row["confidence"] = "high"
    row["review_reason"] = "catalogue_stable_identity_reuses_existing_work_master_row"


def review(row, status, reason):
    row["final_status"] = status
    row["confidence"] = "review"
    row["review_reason"] = reason
    row["proposed_new_work"] = None
    row["proposed_repairs"] = {}
    row["proposed_aliases"] = []


def main():
    review_doc = json.loads(REVIEW.read_text())
    staging_doc = json.loads(STAGING.read_text())
    master = json.loads(FIXTURE.read_text())
    rows = review_doc["rows"]
    residual = [r for r in rows if r.get("final_status") == "unresolved_work"]
    assert len(residual) in {19, 22, 49}, len(residual)
    before = {r["occurrence_id"]: r["raw_work_title"] for r in residual}

    existing_ids = {
        "titan": "4f3de1d5-3257-4c97-ab7a-d6ddbf3055cd",
        "brahms114": "69466d28-bc11-4182-9bdc-1112a51f9628",
        "turina67": "14c4592b-b94c-40cd-b74a-d9ccd7ff6573",
        "wfb67": "32c1fcb3-c18f-4b6d-9e92-9584bba0bdb1",
        "mozart412": "fa076544-1b8d-42cf-b0d6-831d03f03f19",
        "debussy_mer": "e5b7b0d0-81ef-4d98-ba06-a323a7a567ed",
        "toccata": "22301c44-e4b9-49a7-8258-f9f13442e410",
        "serenade": "ea38dda1-f683-41b5-8286-7230fa234b41",
        "snow": "1e0bda53-a32f-4004-bdec-b5fe995cc28f",
    }
    for r in residual:
        t = r["raw_work_title"]
        tl = t.lower()
        # Existing, catalogue-stable rows.
        if "titán" in tl or 'titan”' in tl:
            existing(r, existing_ids["titan"], "existing_work_needs_identity_key", COMPOSERS["Mahler"], 'Symphony No. 1 in D major “Titan”', True)
        elif "trío en la menor, op. 114" in tl:
            existing(r, existing_ids["brahms114"], "existing_work_needs_identity_key", None, 'Trio in A minor, Op. 114', True)
            r["proposed_repairs"]["identity_key"] = identity_key(COMPOSERS["Bach"].replace(COMPOSERS["Bach"], "2cffa372-2bc9-4321-bf4e-4a17aa772418"), 'Trio in A minor, Op. 114')
        elif "cuarteto con piano en la menor, op. 67" in tl:
            existing(r, existing_ids["turina67"], "existing_work_needs_composer_link", COMPOSERS["Turina"], 'Piano Quartet in A minor, Op. 67', True)
        elif "disonancias" in tl and "f 67" in tl:
            existing(r, existing_ids["wfb67"], "existing_work_needs_composer_link", COMPOSERS["WFB"], 'Sinfonia in F major, F. 67 “Dissonance”', True)
        elif "kv 412" in tl:
            existing(r, existing_ids["mozart412"], "existing_work_needs_composer_link", COMPOSERS["Mozart"], 'Horn Concerto No. 1 in D major, K. 412/386b', True)
        elif t == "El mar":
            existing(r, existing_ids["debussy_mer"], "existing_work_needs_identity_key", COMPOSERS["Debussy"], 'La mer, L. 109, CD 111', True)
        elif "serenade for the doll" in tl:
            review(r, "parent_work_excerpt_review", "Existing Debussy Children’s Corner excerpt; retain child/parent semantics for manual parent_work linkage.")
            r["existing_work_id"] = existing_ids["serenade"]
        elif "the snow is dancing" in tl:
            review(r, "parent_work_excerpt_review", "Existing Debussy Children’s Corner excerpt; retain child/parent semantics for manual parent_work linkage.")
            r["existing_work_id"] = existing_ids["snow"]
        # Parent/excerpt or arrangement review; deliberately no executable mutation.
        elif "bwv 596" in tl or "mes longs cheveux" in tl or "invierno" in tl or "verano" in tl or "wonderful town" in tl:
            review(r, "parent_work_excerpt_review", "Catalogue/title identifies a parent Work or excerpt, but production parent/excerpt convention is not deterministic enough for an automatic mutation.")
        # Catalogue-stable identities absent from the current relevant master subset.
        elif "toccata y fuga en re menor" in tl:
            existing(r, existing_ids["toccata"], "existing_work_needs_identity_key", COMPOSERS["Bach"], 'Toccata and Fugue in D minor, BWV 565', True)
        elif "bwv 582" in tl:
            new_work(r, 'Passacaglia and Fugue in C minor, BWV 582', "Bach")
        elif "bwv 639" in tl:
            new_work(r, 'Ich ruf zu dir, Herr Jesu Christ, BWV 639', "Bach")
        elif "d.760" in tl or "d760" in tl:
            new_work(r, 'Fantasie in C major, D. 760 “Wanderer”', "Schubert")
        elif "rv 389" in tl:
            new_work(r, 'Violin Concerto in B minor, RV 389', "Vivaldi")
        elif "op.3 n8" in tl:
            new_work(r, 'Concerto in A minor, Op. 3 No. 8, RV 522', "Vivaldi")
        elif "op.3 n11" in tl:
            new_work(r, 'Concerto in D minor, Op. 3 No. 11, RV 565', "Vivaldi")
        elif "rv151" in tl:
            new_work(r, 'Concerto alla rustica in G major, RV 151', "Vivaldi")
        elif "la catedral sumergida" in tl:
            new_work(r, 'La cathédrale engloutie, L. 117, CD 109 No. 10', "Debussy")
        elif "sinfonía de los salmos" in tl:
            new_work(r, 'Symphony of Psalms', "Stravinsky")
        elif "op. 85" in tl:
            new_work(r, 'Cello Concerto in E minor, Op. 85', "Elgar")
        elif "g 511" in tl:
            new_work(r, 'String Quintet in A major, G. 511', "Boccherini")
        elif "h 311" in tl:
            new_work(r, 'Motet pour les trépassés, H. 311', "Charpentier")
        elif "h 333" in tl:
            new_work(r, 'Annunciate superi, H. 333', "Charpentier")
        elif "danza macabra" in tl:
            review(r, "source_attribution_review", "Catalogue identity is stable, but the existing production row carries a contradictory Brahms composer link; do not overwrite attribution automatically.")
        else:
            review(r, "unresolved_work", "Evidence does not safely establish one canonical production Work: generic title, arrangement, excerpt, attribution, or insufficient source specificity.")

    # Preserve the accepted 691 actions and append only mutations from residual rows.
    actions = list(staging_doc["actions"])
    for r in residual:
        nw = r.get("proposed_new_work")
        if nw:
            actions.append({"action": "create_work", **nw, "source_occurrence_id": r["occurrence_id"]})
            for a in r.get("proposed_aliases", []):
                actions.append({"action": "create_work_alias", "work_id": nw["id"], "alias": a, "language": "es", "source": "auditorio_nacional", "source_occurrence_id": r["occurrence_id"]})
        p = r.get("proposed_repairs", {})
        if r.get("existing_work_id") and p.get("composer_id"):
            actions.append({"action": "update_existing_work_composer_id", "work_id": r["existing_work_id"], "composer_id": p["composer_id"], "source_occurrence_id": r["occurrence_id"]})
        if r.get("existing_work_id") and p.get("identity_key"):
            actions.append({"action": "update_existing_work_identity_key", "work_id": r["existing_work_id"], "identity_key": p["identity_key"], "source_occurrence_id": r["occurrence_id"]})
        if r.get("existing_work_id") and p.get("canonical_title"):
            actions.append({"action": "correct_existing_work_canonical_title", "work_id": r["existing_work_id"], "canonical_title": p["canonical_title"], "source_occurrence_id": r["occurrence_id"]})
        for a in r.get("proposed_aliases", []):
            if r.get("existing_work_id"):
                actions.append({"action": "create_work_alias", "work_id": r["existing_work_id"], "alias": a, "language": "es", "source": "auditorio_nacional", "source_occurrence_id": r["occurrence_id"]})
    actions = repair_actions(actions, rows, master)
    status_counts = Counter(r["final_status"] for r in rows)
    review_rows = [dict(r) for r in rows if r["final_status"] in {"unresolved_work", "ambiguous_work", "source_attribution_review", "parser_issue", "parent_work_excerpt_review"}]
    summary = {
        "source": "auditorio_nacional", "review_only": True, "database_writes": 0,
        "programme_candidates_processed": len(rows), "status_counts": dict(status_counts),
        "previous_unresolved_audited": 49,
        "residual_reclassified": sum(1 for r in residual if r["final_status"] != "unresolved_work"),
        "residual_genuinely_unresolved": sum(1 for r in residual if r["final_status"] == "unresolved_work"),
        "genuinely_unresolved_titles": sorted({r["raw_work_title"] for r in residual if r["final_status"] == "unresolved_work"}),
        "existing_works_recovered": sum(1 for r in rows if r.get("existing_work_id")),
        "new_works_confirmed": sum(1 for r in rows if r.get("final_status") == "confirmed_new_global_work"),
        "canonical_work_corrections": sum(1 for a in actions if a["action"] == "correct_existing_work_canonical_title"),
        "review_only_rows": len(review_rows), "planned_actions": len(actions),
        "planned_create_work": sum(1 for a in actions if a["action"] == "create_work"),
        "planned_create_work_alias": sum(1 for a in actions if a["action"] == "create_work_alias"),
        "planned_composer_repairs": sum(1 for a in actions if a["action"] == "update_existing_work_composer_id"),
        "planned_identity_key_repairs": sum(1 for a in actions if a["action"] == "update_existing_work_identity_key"),
        "expected_post_apply_work_count": len(master["works"]) + sum(1 for a in actions if a["action"] == "create_work"),
        "expected_post_apply_work_alias_count": len(master.get("aliases", [])) + sum(1 for a in actions if a["action"] == "create_work_alias"),
    }
    review_doc["rows"] = rows; review_doc["review_only_rows"] = review_rows; review_doc["database_writes"] = 0
    REVIEW.write_text(json.dumps(review_doc, ensure_ascii=False, indent=2) + "\n")
    STAGING.write_text(json.dumps({"source":"auditorio_nacional","review_only":True,"database_writes":0,"actions":actions,"summary":summary}, ensure_ascii=False, indent=2) + "\n")
    (OUT / "auditorio-work-final-consolidation-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    _write_sql(OUT, master, actions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
