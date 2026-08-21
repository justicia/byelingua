"""Generate Phase 3.5R Composer staging artifacts from a fresh read-only snapshot."""
from __future__ import annotations
import argparse, hashlib, json, re, unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/"artifacts/global-entities/auditorio-composer-enrichment-review.json"
PREFLIGHT=ROOT/"artifacts/global-entities/composer-production-preflight-master.json"
OUT=ROOT/"artifacts/global-entities"
TRANSLIT=str.maketrans({"ł":"l","Ł":"L","ø":"o","Ø":"O","đ":"d","Đ":"D","ð":"d","Ð":"D","þ":"th","Þ":"Th","æ":"ae","Æ":"Ae","œ":"oe","Œ":"Oe"})

def norm(value:str)->str:
    value=unicodedata.normalize("NFKD",(value or "").translate(TRANSLIT))
    value="".join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",value)).strip()
def strip_source_decoration(value:str)->str:
    value=re.sub(r"\s*\((?:ca\.\s*)?\d{3,4}\s*[–-]\s*(?:ca\.\s*)?\d{3,4}\)\s*$","",value)
    return re.sub(r"\s*\(\*?\d{4}\)\s*$","",value).strip()
def quote(value:str)->str: return "'"+value.replace("'","''")+"'"
def key(value:str)->str: return "composer:"+hashlib.md5(value.lower().encode("utf-8")).hexdigest()
def mmap(rows:list[dict],field:str)->dict[str,list[dict]]:
    out:dict[str,list[dict]]={}
    for row in rows: out.setdefault(norm(row[field]),[]).append(row)
    return out

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--review-json",type=Path,default=REVIEW); p.add_argument("--preflight-json",type=Path,default=PREFLIGHT); a=p.parse_args()
    review=json.loads(a.review_json.read_text(encoding="utf-8")); pf=json.loads(a.preflight_json.read_text(encoding="utf-8"))
    composers=list(pf["composers"]); aliases=list(pf["aliases"]); cb=mmap(composers,"canonical_name"); ab=mmap(aliases,"alias")
    checks=[(r["identity_key"],key(r["canonical_name"])) for r in composers]; mismatches=[x for x in checks if x[0]!=x[1]]
    if mismatches: raise SystemExit(f"identity_key verification failed for {len(mismatches)} rows; refusing to generate SQL")
    approved=[x for x in review["identities"] if x["review_status"]=="confirmed_new_global_composer"]
    if len(approved)!=10: raise SystemExit(f"expected 10 accepted identities, found {len(approved)}")
    staging=[]; alias_rows=[]; canonical_collisions=0
    for item in approved:
        canonical=item["proposed_canonical_name"]; cm=cb.get(norm(canonical),[]); exact=[x for x in composers if x["canonical_name"]==canonical]; collision=len({x["id"] for x in cm})>1; canonical_collisions+=int(collision); target=exact[0]["id"] if len(exact)==1 else None; safe_aliases=[]
        variants=[]
        for raw in item["raw_identity_variants"]:
            cleaned=strip_source_decoration(raw)
            if cleaned and norm(cleaned)!=norm(canonical): variants.append(cleaned)
        for alias in sorted(set(variants)):
            matches=ab.get(norm(alias),[]); ids={x["composer_id"] for x in matches}; alias_collision=len(ids)>1 or (len(ids)==1 and target not in ids); exists=len(ids)==1 and target in ids; action="alias_collision_review" if alias_collision else ("already_exists_before_apply" if exists else "create_alias")
            alias_rows.append({"canonical_name":canonical,"alias":alias,"normalized_alias":norm(alias),"existing_normalized_matches":matches,"existing_exact_matches":[x for x in aliases if x["alias"]==alias],"already_exists":exists,"collision":alias_collision,"planned_action":action})
            if not alias_collision: safe_aliases.append(alias)
        action="canonical_collision_review" if collision else ("already_exists_before_apply" if exact or cm else "create_composer")
        staging.append({"canonical_name":canonical,"identity_key":key(canonical),"raw_source_variants":item["raw_identity_variants"],"approved_aliases":safe_aliases,"source_occurrences":item["source_occurrences"],"evidence":item["evidence"],"current_global_lookup":{"canonical_matches":cm,"canonical_exact_matches":exact,"existing_composer_id":target,"collision":collision},"planned_action":action,"reason":"accepted Phase 3.4R.2 identity; fresh global snapshot used for all preflight decisions"})
    alias_collisions=[x for x in alias_rows if x["collision"]]; newc=[x for x in staging if x["planned_action"]=="create_composer"]; newa=[x for x in alias_rows if x["planned_action"]=="create_alias"]; existingc=[x for x in staging if x["planned_action"]=="already_exists_before_apply"]; existinga=[x for x in alias_rows if x["planned_action"]=="already_exists_before_apply"]
    if canonical_collisions or alias_collisions: raise SystemExit("fresh preflight found canonical or alias collisions; refusing to generate apply SQL")
    snap=pf["snapshot_generated_at"]; ncomp=len(composers); nalias=len(aliases)
    summary={"source":"auditorio_nacional","phase":"3.5R","fresh_snapshot_generated_at":snap,"baseline_composer_row_count":ncomp,"baseline_alias_row_count":nalias,"identity_key_rows_checked":len(checks),"identity_key_mismatch_count":len(mismatches),"approved_composer_identity_count":10,"already_existing_composer_count":len(existingc),"planned_new_composer_count":len(newc),"canonical_collision_count":canonical_collisions,"raw_verified_alias_variant_count":len(alias_rows),"already_existing_alias_count":len(existinga),"planned_new_alias_count":len(newa),"alias_collision_count":len(alias_collisions),"expected_post_apply_composer_row_count":ncomp+len(newc),"expected_post_apply_alias_row_count":nalias+len(newa),"database_writes":0}
    payload={"source":"auditorio_nacional","phase":"3.5R","review_only":True,"database_writes":0,"fresh_snapshot_generated_at":snap,"global_master_recheck":{"composer_row_count":ncomp,"alias_row_count":nalias,"identity_key_rows_checked":len(checks),"identity_key_matches":len(checks)-len(mismatches),"identity_key_mismatches":len(mismatches)},"identities":staging}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"composer-production-staging.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (OUT/"composer-production-staging-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    cv=",\n        ".join(f"({quote(x['canonical_name'])}, {quote(x['identity_key'])})" for x in staging); av=",\n        ".join(f"({quote(x['canonical_name'])}, {quote(x['alias'])})" for x in newa) or "(NULL::text, NULL::text)"; sv=",\n        ".join(f"({quote(x['id'])}::uuid, {quote(x['alias'])}, {quote(x['composer_id'])}::uuid)" for x in aliases)
    apply=f"""-- Byelingua Phase 3.5R manual Composer apply SQL.
-- Fresh snapshot: {snap}. Do not execute automatically.
BEGIN;
DO $$
BEGIN
 IF (SELECT count(*) FROM public.composers) <> {ncomp} OR (SELECT count(*) FROM public.composer_aliases) <> {nalias} THEN RAISE EXCEPTION 'Composer master row counts changed since preflight'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES {cv}) a(canonical_name,identity_key) JOIN public.composers c ON c.identity_key=a.identity_key WHERE c.canonical_name<>a.canonical_name) THEN RAISE EXCEPTION 'Composer identity_key collision'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES {cv}) a(canonical_name,identity_key) JOIN public.composers c ON c.canonical_name=a.canonical_name WHERE c.identity_key<>a.identity_key) THEN RAISE EXCEPTION 'Composer canonical-name collision'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES {sv}) s(id,alias,composer_id) WHERE NOT EXISTS (SELECT 1 FROM public.composer_aliases ca WHERE ca.id=s.id AND ca.alias=s.alias AND ca.composer_id=s.composer_id)) THEN RAISE EXCEPTION 'Alias master changed since preflight'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES {av}) a(canonical_name,alias) JOIN public.composer_aliases ca ON ca.alias=a.alias JOIN public.composers c ON c.id=ca.composer_id WHERE c.canonical_name<>a.canonical_name) THEN RAISE EXCEPTION 'Exact staged alias collision'; END IF;
END $$;
WITH approved(canonical_name,identity_key) AS (VALUES {cv}), inserted AS (INSERT INTO public.composers(canonical_name,identity_key) SELECT a.canonical_name,a.identity_key FROM approved a WHERE NOT EXISTS (SELECT 1 FROM public.composers c WHERE c.identity_key=a.identity_key OR c.canonical_name=a.canonical_name) RETURNING id,canonical_name) SELECT 'created_composer' AS result,id,canonical_name FROM inserted;
WITH staged(canonical_name,alias) AS (VALUES {av}) INSERT INTO public.composer_aliases(composer_id,alias,source) SELECT c.id,s.alias,'auditorio_nacional_phase3.5R' FROM staged s JOIN public.composers c ON c.canonical_name=s.canonical_name WHERE s.alias IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.composer_aliases ca WHERE ca.composer_id=c.id AND ca.alias=s.alias) RETURNING id,composer_id,alias;
COMMIT;
"""; (OUT/"composer-production-apply.sql").write_text(apply,encoding="utf-8")
    validation=f"""-- Byelingua Phase 3.5R read-only validation SQL.
-- Expected Composer inserts: {len(newc)}; expected alias inserts: {len(newa)}.
SELECT count(*) AS composer_rows_after_apply FROM public.composers;
SELECT count(*) AS alias_rows_after_apply FROM public.composer_aliases;
WITH intended(canonical_name,identity_key) AS (VALUES {cv}) SELECT i.canonical_name,c.id,c.identity_key,(c.id IS NOT NULL AND c.identity_key=i.identity_key) AS target_match FROM intended i LEFT JOIN public.composers c ON c.canonical_name=i.canonical_name ORDER BY i.canonical_name;
WITH staged(canonical_name,alias) AS (VALUES {av}) SELECT s.alias,c.id AS composer_id,c.canonical_name,(c.canonical_name=s.canonical_name) AS target_match FROM staged s LEFT JOIN public.composer_aliases ca ON ca.alias=s.alias LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE s.alias IS NOT NULL ORDER BY s.alias;
SELECT count(*) AS duplicate_exact_canonical_names FROM (SELECT canonical_name FROM public.composers GROUP BY canonical_name HAVING count(*)>1) x;
SELECT count(*) AS orphan_aliases FROM public.composer_aliases ca LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE c.id IS NULL;
WITH intended(canonical_name,identity_key) AS (VALUES {cv}) SELECT count(*) AS batch_canonical_target_mismatches FROM intended i LEFT JOIN public.composers c ON c.canonical_name=i.canonical_name WHERE c.id IS NULL OR c.identity_key<>i.identity_key;
WITH staged(canonical_name,alias) AS (VALUES {av}) SELECT count(*) AS batch_alias_target_mismatches FROM staged s LEFT JOIN public.composer_aliases ca ON ca.alias=s.alias LEFT JOIN public.composers c ON c.id=ca.composer_id WHERE s.alias IS NOT NULL AND (c.id IS NULL OR c.canonical_name<>s.canonical_name);
"""; (OUT/"composer-production-validation.sql").write_text(validation,encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
