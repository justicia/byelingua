-- FINAL Auditorio relationship reconciliation. DO NOT EXECUTE in this phase.
-- database_writes = 0; generated 2026-08-21T10:11:20.503104+02:00
BEGIN;
DO $$ DECLARE events_now integer; programme_now integer;
BEGIN
  SELECT count(*) INTO events_now FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
  SELECT count(*) INTO programme_now FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
  IF events_now <> 583 THEN RAISE EXCEPTION 'Auditorio event baseline changed: expected 583, got %', events_now; END IF;
  IF programme_now <> 2909 THEN RAISE EXCEPTION 'Auditorio event_programme baseline changed: expected 2909, got %', programme_now; END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM (VALUES ('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '0a99202e-622b-5a39-b813-58251346eb33'::uuid, 1::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '6127809b-2e55-547d-bfdf-2a46e78953e5'::uuid, 2::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '5afa95cb-1073-596f-9fde-9f3ba3123bcb'::uuid, 3::integer, 'auditorio_nacional:performance:9'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:44'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:44'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:45'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:45'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:47'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:47'::text),
('db88f2cd-4d5e-4e2d-8983-ed124b0d288e'::uuid, 'b8733ad8-0e0d-4fba-aead-8783cc1e78e3'::uuid, 8::integer, 'auditorio_nacional:performance:51'::text),
('674ededc-61e5-4b49-9602-32716eb6a9ce'::uuid, 'ef0e761d-443e-4407-88dc-45f683e2a460'::uuid, 18::integer, 'auditorio_nacional:performance:153'::text),
('c0081b19-194d-40d3-9c6b-c4e850beae43'::uuid, '27cc0883-d00e-4a11-b321-90d480afbd25'::uuid, 2::integer, 'auditorio_nacional:performance:336'::text),
('146bea0b-6e12-435d-8190-2700a815ef6d'::uuid, '6e8e4bef-9204-5d3f-a031-7e2f4f1417c5'::uuid, 2::integer, 'auditorio_nacional:performance:349'::text)) b(event_id,work_id,programme_order,source_occurrence_id) WHERE b.event_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.events e WHERE e.id=b.event_id)) THEN RAISE EXCEPTION 'Missing event target'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES ('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '0a99202e-622b-5a39-b813-58251346eb33'::uuid, 1::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '6127809b-2e55-547d-bfdf-2a46e78953e5'::uuid, 2::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '5afa95cb-1073-596f-9fde-9f3ba3123bcb'::uuid, 3::integer, 'auditorio_nacional:performance:9'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:44'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:44'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:45'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:45'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:47'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:47'::text),
('db88f2cd-4d5e-4e2d-8983-ed124b0d288e'::uuid, 'b8733ad8-0e0d-4fba-aead-8783cc1e78e3'::uuid, 8::integer, 'auditorio_nacional:performance:51'::text),
('674ededc-61e5-4b49-9602-32716eb6a9ce'::uuid, 'ef0e761d-443e-4407-88dc-45f683e2a460'::uuid, 18::integer, 'auditorio_nacional:performance:153'::text),
('c0081b19-194d-40d3-9c6b-c4e850beae43'::uuid, '27cc0883-d00e-4a11-b321-90d480afbd25'::uuid, 2::integer, 'auditorio_nacional:performance:336'::text),
('146bea0b-6e12-435d-8190-2700a815ef6d'::uuid, '6e8e4bef-9204-5d3f-a031-7e2f4f1417c5'::uuid, 2::integer, 'auditorio_nacional:performance:349'::text)) b(event_id,work_id,programme_order,source_occurrence_id) WHERE b.work_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.works w WHERE w.id=b.work_id)) THEN RAISE EXCEPTION 'Missing Work target'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES ('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '0a99202e-622b-5a39-b813-58251346eb33'::uuid, 1::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '6127809b-2e55-547d-bfdf-2a46e78953e5'::uuid, 2::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '5afa95cb-1073-596f-9fde-9f3ba3123bcb'::uuid, 3::integer, 'auditorio_nacional:performance:9'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:44'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:44'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:45'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:45'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:47'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:47'::text),
('db88f2cd-4d5e-4e2d-8983-ed124b0d288e'::uuid, 'b8733ad8-0e0d-4fba-aead-8783cc1e78e3'::uuid, 8::integer, 'auditorio_nacional:performance:51'::text),
('674ededc-61e5-4b49-9602-32716eb6a9ce'::uuid, 'ef0e761d-443e-4407-88dc-45f683e2a460'::uuid, 18::integer, 'auditorio_nacional:performance:153'::text),
('c0081b19-194d-40d3-9c6b-c4e850beae43'::uuid, '27cc0883-d00e-4a11-b321-90d480afbd25'::uuid, 2::integer, 'auditorio_nacional:performance:336'::text),
('146bea0b-6e12-435d-8190-2700a815ef6d'::uuid, '6e8e4bef-9204-5d3f-a031-7e2f4f1417c5'::uuid, 2::integer, 'auditorio_nacional:performance:349'::text)) b(event_id,work_id,programme_order,source_occurrence_id) JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep."order"=b.programme_order WHERE ep.work_id<>b.work_id) THEN RAISE EXCEPTION 'Stable programme slot conflict'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES ('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '0a99202e-622b-5a39-b813-58251346eb33'::uuid, 1::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '6127809b-2e55-547d-bfdf-2a46e78953e5'::uuid, 2::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '5afa95cb-1073-596f-9fde-9f3ba3123bcb'::uuid, 3::integer, 'auditorio_nacional:performance:9'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:44'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:44'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:45'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:45'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:47'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:47'::text),
('db88f2cd-4d5e-4e2d-8983-ed124b0d288e'::uuid, 'b8733ad8-0e0d-4fba-aead-8783cc1e78e3'::uuid, 8::integer, 'auditorio_nacional:performance:51'::text),
('674ededc-61e5-4b49-9602-32716eb6a9ce'::uuid, 'ef0e761d-443e-4407-88dc-45f683e2a460'::uuid, 18::integer, 'auditorio_nacional:performance:153'::text),
('c0081b19-194d-40d3-9c6b-c4e850beae43'::uuid, '27cc0883-d00e-4a11-b321-90d480afbd25'::uuid, 2::integer, 'auditorio_nacional:performance:336'::text),
('146bea0b-6e12-435d-8190-2700a815ef6d'::uuid, '6e8e4bef-9204-5d3f-a031-7e2f4f1417c5'::uuid, 2::integer, 'auditorio_nacional:performance:349'::text)) b(event_id,work_id,programme_order,source_occurrence_id) JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep.work_id=b.work_id AND ep."order"<>b.programme_order) THEN RAISE EXCEPTION 'Same Event+Work already exists at another order'; END IF;
END $$;
INSERT INTO public.event_programme(event_id, work_id, "order")
SELECT event_id, work_id, programme_order FROM (VALUES ('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '0a99202e-622b-5a39-b813-58251346eb33'::uuid, 1::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '6127809b-2e55-547d-bfdf-2a46e78953e5'::uuid, 2::integer, 'auditorio_nacional:performance:9'::text),
('0ee05fb5-0ea6-4a93-a6d2-dc34072f61ba'::uuid, '5afa95cb-1073-596f-9fde-9f3ba3123bcb'::uuid, 3::integer, 'auditorio_nacional:performance:9'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:44'::text),
('3f3bdd56-095c-4c1c-a75f-eb60da8542f7'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:44'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:45'::text),
('334542de-b897-4e20-9ca1-033470430406'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:45'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, '2dc95177-f6b8-5347-a663-51bed58941d0'::uuid, 1::integer, 'auditorio_nacional:performance:47'::text),
('81bf964c-a6a3-4108-9d02-6b287980e1fb'::uuid, 'e5b7b0d0-81ef-4d98-ba06-a323a7a567ed'::uuid, 2::integer, 'auditorio_nacional:performance:47'::text),
('db88f2cd-4d5e-4e2d-8983-ed124b0d288e'::uuid, 'b8733ad8-0e0d-4fba-aead-8783cc1e78e3'::uuid, 8::integer, 'auditorio_nacional:performance:51'::text),
('674ededc-61e5-4b49-9602-32716eb6a9ce'::uuid, 'ef0e761d-443e-4407-88dc-45f683e2a460'::uuid, 18::integer, 'auditorio_nacional:performance:153'::text),
('c0081b19-194d-40d3-9c6b-c4e850beae43'::uuid, '27cc0883-d00e-4a11-b321-90d480afbd25'::uuid, 2::integer, 'auditorio_nacional:performance:336'::text),
('146bea0b-6e12-435d-8190-2700a815ef6d'::uuid, '6e8e4bef-9204-5d3f-a031-7e2f4f1417c5'::uuid, 2::integer, 'auditorio_nacional:performance:349'::text)) b(event_id,work_id,programme_order,source_occurrence_id)
ON CONFLICT (event_id,"order") DO NOTHING;
-- expected_event_programme_before=2909; expected_safe_insert_count=13; expected_after=2922
COMMIT;
