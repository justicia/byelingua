from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def group_key(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    key = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    if any(token in key for token in ("figaro", "marriage")):
        return "figaro"
    if "barbero" in key or "barbiere" in key:
        return "barbiere"
    if "manon" in key:
        return "manon"
    if "blood wedding" in key or "bodas de sangre" in key:
        return "blood"
    if "matthew" in key or "pasion" in key:
        return "matthew"
    if "richard" in key or "riccardo" in key:
        return "richard"
    if "saint john" in key or "san giovanni" in key:
        return "john"
    if "bluebeard" in key or "barbazul" in key:
        return "bluebeard"
    if "messiah" in key or "mesias" in key:
        return "messiah"
    if "bayreuth" in key:
        return "bayreuth"
    if "chamber music" in key or "domingos de camara" in key:
        return "chamber"
    return key.replace(" ", "")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    preview = json.loads(args.preview.read_text(encoding="utf-8"))
    values = ",\n".join(
        "(" + ", ".join([
            sql_literal(event["date"]),
            sql_literal(event["start_time"]),
            sql_literal(group_key(event["title"])),
            sql_literal(event["source_url"]),
        ]) + ")"
        for event in preview["events"]
    )
    query = f"""
WITH official(date_text, start_time, group_key, source_url) AS (VALUES
{values}
), db AS (
  SELECT e.id, e.event_key, e.date, to_char(e.start_time, 'HH24:MI') AS start_time,
         e.title, e.original_title, s.source_url,
         CASE
           WHEN s.source_url ILIKE '%manon-lescaut%' THEN 'manon'
           WHEN s.source_url ILIKE '%figaro%' OR s.source_url ILIKE '%marriage%' OR s.source_url ILIKE '%bodas-figaro%' OR e.title ILIKE '%Figaro%' THEN 'figaro'
           WHEN s.source_url ILIKE '%barbero%' OR s.source_url ILIKE '%barbiere%' OR e.title ILIKE '%barbero%' THEN 'barbiere'
           WHEN s.source_url ILIKE '%blood-wedding%' OR e.title ILIKE '%Bodas de sangre%' THEN 'blood'
           WHEN s.source_url ILIKE '%matthew%' OR e.title ILIKE '%Mateo%' OR e.title ILIKE '%Pasi%' THEN 'matthew'
           WHEN s.source_url ILIKE '%richard%' OR s.source_url ILIKE '%riccardo%' OR e.title ILIKE '%Richard%' OR e.title ILIKE '%Riccardo%' THEN 'richard'
           WHEN s.source_url ILIKE '%katia-kabanova%' THEN 'katiakabanova'
           WHEN s.source_url ILIKE '%compania-nacional-danza%' THEN 'companianacionaldedanza'
           WHEN s.source_url ILIKE '%tannhauser%' THEN 'tannhauser'
           WHEN s.source_url ILIKE '%concierto-concurso-tenor-vinas%' THEN 'conciertoconcursotenorvinas'
           WHEN s.source_url ILIKE '%veronique-gens%' THEN 'veroniquegens'
           WHEN s.source_url ILIKE '%saint-john%' OR e.title ILIKE '%Giovanni Battista%' THEN 'john'
           WHEN s.source_url ILIKE '%bluebeard%' OR e.title ILIKE '%Barbazul%' THEN 'bluebeard'
           WHEN s.source_url ILIKE '%messiah%' OR e.title ILIKE '%Mesías%' THEN 'messiah'
           WHEN s.source_url ILIKE '%bayreuth%' OR e.title ILIKE '%Bayreuth%' THEN 'bayreuth'
           WHEN s.source_url ILIKE '%chamber%' OR e.title ILIKE '%Cámara%' THEN 'chamber'
           ELSE regexp_replace(lower(e.title), '[^a-z0-9]+', '', 'g')
         END AS group_key
  FROM events e
  JOIN event_sources s ON s.event_id=e.id
  JOIN organizations o ON o.id=e.organization_id
  WHERE o.name='Teatro Real'
), candidates AS (
  SELECT o.date_text, o.start_time, o.group_key, o.source_url,
         d.id, d.event_key, d.title, d.original_title, d.source_url AS db_source_url,
         row_number() OVER (PARTITION BY o.date_text,o.start_time,o.group_key ORDER BY
           CASE WHEN d.source_url=o.source_url THEN 0 ELSE 1 END, d.id) AS rn
  FROM official o JOIN db d
    ON d.date=o.date_text::date AND d.start_time=o.start_time AND d.group_key=o.group_key
), matched AS (SELECT * FROM candidates WHERE rn=1)
SELECT json_build_object(
  'official_count', (SELECT count(*) FROM official),
  'database_count', (SELECT count(*) FROM db),
  'matched_count', (SELECT count(*) FROM matched),
  'unmatched_count', (SELECT count(*) FROM official o WHERE NOT EXISTS (SELECT 1 FROM matched m WHERE m.date_text=o.date_text AND m.start_time=o.start_time AND m.group_key=o.group_key)),
  'unmatched', (SELECT coalesce(json_agg(o ORDER BY o.date_text,o.start_time),'[]') FROM official o WHERE NOT EXISTS (SELECT 1 FROM matched m WHERE m.date_text=o.date_text AND m.start_time=o.start_time AND m.group_key=o.group_key)),
  'ambiguous_count', (SELECT count(*) FROM candidates WHERE rn>1),
  'extra_count', (SELECT count(*) FROM db d WHERE NOT EXISTS (SELECT 1 FROM matched m WHERE m.id=d.id)),
  'extra_ids', (SELECT coalesce(json_agg(d.id ORDER BY d.date,d.start_time),'[]') FROM db d WHERE NOT EXISTS (SELECT 1 FROM matched m WHERE m.id=d.id)),
  'extra_event_relations', (SELECT count(*) FROM user_event_relations r WHERE r.event_id IN (SELECT d.id FROM db d WHERE NOT EXISTS (SELECT 1 FROM matched m WHERE m.id=d.id))),
  'extra_schedule_memberships', (SELECT count(*) FROM schedule_events r WHERE r.event_id IN (SELECT d.id FROM db d WHERE NOT EXISTS (SELECT 1 FROM matched m WHERE m.id=d.id)))
)
"""
    args.output.write_text(query.strip() + "\n", encoding="utf-8")
    print(json.dumps({"official_count": len(preview["events"]), "sql": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
