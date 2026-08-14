from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def group_key(title: str) -> str:
    value = unicodedata.normalize("NFKD", title.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    for token, key in (
        (("figaro", "marriage"), "figaro"), (("barbero",), "barbiere"),
        (("barbiere",), "barbiere"), (("manon",), "manon"),
        (("blood wedding", "bodas de sangre"), "blood"),
        (("matthew", "pasion"), "matthew"), (("richard", "riccardo"), "richard"),
        (("saint john", "san giovanni"), "john"), (("bluebeard", "barbazul"), "bluebeard"),
        (("messiah", "mesias"), "messiah"), (("bayreuth",), "bayreuth"),
        (("chamber music", "domingos de camara"), "chamber"),
    ):
        if any(token in value for token in token):
            return key
    return value.replace(" ", "")


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    preview = json.loads(args.preview.read_text(encoding="utf-8"))
    events = preview["events"][args.start : args.start + args.limit] if args.limit else preview["events"][args.start :]
    incoming_values = ",\n".join(
        "(" + ", ".join(
            [sql_text(event["date"]), sql_text(event["start_time"]), sql_text(group_key(event["title"])),
             "$j$" + json.dumps({
                 key: event.get(key) for key in (
                     "source", "source_url", "date", "start_time", "event_type", "title",
                     "programme", "cast", "artistic_team", "other_artists", "source_event_id",
                 )
             }, ensure_ascii=False, separators=(",", ":")) + "$j$::jsonb"]
        ) + ")"
        for event in events
    )
    sql = f"""
CREATE TEMP TABLE teatro_real_repair_targets ON COMMIT DROP AS
WITH incoming(date_text, start_time_text, group_key, event) AS (VALUES
{incoming_values}
),
db AS (
  SELECT e.id, e.date, to_char(e.start_time, 'HH24:MI') AS start_time, e.title, s.source_url,
    CASE
      WHEN s.source_url ILIKE '%manon-lescaut%' THEN 'manon'
      WHEN s.source_url ILIKE '%figaro%' OR s.source_url ILIKE '%marriage%' OR e.title ILIKE '%Figaro%' THEN 'figaro'
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
  FROM events e JOIN event_sources s ON s.event_id=e.id JOIN organizations o ON o.id=e.organization_id
  WHERE o.name='Teatro Real'
), ranked AS (
  SELECT i.event, d.id AS target_id,
    row_number() OVER (PARTITION BY i.date_text,i.start_time_text ORDER BY
      CASE WHEN d.group_key=i.group_key THEN 0 ELSE 1 END,
      CASE WHEN d.source_url=replace(i.event->>'source_url', '#actividadesCulturales','') THEN 0 ELSE 1 END, d.id) AS rn
  FROM incoming i JOIN db d ON d.date=i.date_text::date
    AND d.start_time=i.start_time_text
)
SELECT event, target_id FROM ranked WHERE rn=1;

DO $repair$
DECLARE
  item jsonb;
  target uuid;
  v_work_id uuid;
  artist_id uuid;
  character_id uuid;
  programme_item jsonb;
  credit_item jsonb;
  role_name text;
  work_title text;
  composer_name text;
BEGIN
  IF (SELECT count(*) FROM teatro_real_repair_targets) <> {len(events)} THEN
    RAISE EXCEPTION 'Teatro Real repair target count mismatch';
  END IF;
  FOR item, target IN SELECT event, target_id FROM teatro_real_repair_targets LOOP
    UPDATE events SET event_key=item->>'source_event_id', title=item->>'title', original_title=item->>'title',
      event_type=item->>'event_type', updated_at=now(), fetched_at=now() WHERE id=target;
    DELETE FROM event_sources WHERE event_id=target;
    INSERT INTO event_sources(event_id,source,source_event_id,source_url)
      VALUES(target,item->>'source',item->>'source_event_id',item->>'source_url');
    DELETE FROM event_programme WHERE event_id=target;
    DELETE FROM event_credits WHERE event_id=target;
    FOR programme_item IN SELECT value FROM jsonb_array_elements(COALESCE(item->'programme','[]'::jsonb)) LOOP
      work_title := programme_item->>'title'; composer_name := NULLIF(programme_item->>'composer','');
      SELECT id INTO v_work_id FROM works WHERE lower(title)=lower(work_title)
        AND coalesce(lower(composer),'')=coalesce(lower(composer_name),'') LIMIT 1;
      IF v_work_id IS NULL THEN
        INSERT INTO works(title,composer) VALUES(work_title,composer_name) RETURNING id INTO v_work_id;
      END IF;
      INSERT INTO event_programme(event_id,work_id,"order")
        VALUES(target,v_work_id,(SELECT count(*) + 1 FROM event_programme WHERE event_id=target));
    END LOOP;
    FOR credit_item IN SELECT value FROM jsonb_array_elements(COALESCE(item->'cast','[]'::jsonb) || COALESCE(item->'artistic_team','[]'::jsonb) || COALESCE(item->'other_artists','[]'::jsonb)) LOOP
      IF credit_item->>'role_type'='character' AND EXISTS (
        SELECT 1 FROM jsonb_array_elements(COALESCE(item->'artistic_team','[]'::jsonb)) team_item
        WHERE team_item->>'person'=credit_item->>'person'
      ) THEN
        CONTINUE;
      END IF;
      SELECT id INTO artist_id FROM artists WHERE artist_name=credit_item->>'person' LIMIT 1;
      IF artist_id IS NULL THEN INSERT INTO artists(artist_name) VALUES(credit_item->>'person') RETURNING id INTO artist_id; END IF;
      role_name := COALESCE(NULLIF(credit_item->>'artistic_function',''), NULLIF(credit_item->>'raw_role_label',''), 'Artist');
      character_id := NULL;
      IF credit_item->>'role_type'='character' AND NULLIF(credit_item->>'character_role','') IS NOT NULL THEN
        SELECT ep.work_id INTO v_work_id FROM event_programme ep WHERE ep.event_id=target ORDER BY ep."order" LIMIT 1;
        IF v_work_id IS NOT NULL THEN
          SELECT wc.id INTO character_id FROM work_characters wc WHERE wc.work_id=v_work_id AND wc.canonical_name=credit_item->>'character_role' LIMIT 1;
          IF character_id IS NULL THEN INSERT INTO work_characters(work_id,canonical_name) VALUES(v_work_id,credit_item->>'character_role') RETURNING id INTO character_id; END IF;
        END IF;
      END IF;
      INSERT INTO event_credits(event_id,artist_id,role,"character",character_id,raw_character)
        VALUES(target,artist_id,role_name,NULLIF(credit_item->>'character_role',''),character_id,NULLIF(credit_item->>'raw_role_label',''));
    END LOOP;
  END LOOP;
END $repair$;

"""
    args.output.write_text(sql.strip() + "\n", encoding="utf-8")
    print(json.dumps({"event_count": len(preview["events"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
