create or replace function public.apply_canonical_production_graph(p_payload jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_org_id uuid;
  v_venue_id uuid;
  v_event_id uuid;
  v_work_id uuid;
  v_existing_id uuid;
  v_source_event text;
  v_key text;
  v_count integer;
  v_result jsonb := '{}'::jsonb;
begin
  if jsonb_typeof(p_payload) <> 'object' then raise exception 'graph payload must be an object'; end if;
  if jsonb_array_length(coalesce(p_payload->'events','[]'::jsonb)) = 0 then raise exception 'graph payload has no events'; end if;

  select id into v_org_id from organizations where slug = p_payload->'organization'->>'slug';
  if v_org_id is null then
    insert into organizations(name, slug) values (p_payload->'organization'->>'name', p_payload->'organization'->>'slug') returning id into v_org_id;
  elsif exists (select 1 from organizations where id=v_org_id and name <> p_payload->'organization'->>'name') then
    raise exception 'organization slug/name conflict';
  end if;
  select id into v_venue_id from venues where organization_id=v_org_id and name=p_payload->'venue'->>'name';
  if v_venue_id is null then
    insert into venues(organization_id,name,city,country_code) values (v_org_id,p_payload->'venue'->>'name',p_payload->'venue'->>'city',p_payload->'venue'->>'country_code') returning id into v_venue_id;
  end if;

  create temporary table _graph_events(staging_key text primary key, production_id uuid not null) on commit drop;
  create temporary table _graph_works(candidate_key text primary key, production_id uuid not null) on commit drop;
  for v_key, v_source_event in select x->>'event_key', x->>'source_event_id' from jsonb_array_elements(p_payload->'events') x loop
    select e.id into v_existing_id from events e where e.event_key=v_key;
    select es.event_id into v_event_id from event_sources es where es.source=p_payload->>'source' and es.source_event_id=v_source_event;
    if v_existing_id is not null and v_event_id is not null and v_existing_id <> v_event_id then raise exception 'EVENT_IDENTITY_CONFLICT %', v_key; end if;
    v_event_id := coalesce(v_existing_id,v_event_id);
    if v_event_id is null then
      insert into events(event_key,organization_id,venue_id,room,date,start_time,end_time,timezone,event_type,title,original_title,status,ticket_url,fetched_at,review_status)
      select x->>'event_key',v_org_id,v_venue_id,x->>'room',(x->>'date')::date,nullif(x->>'start_time','')::time,nullif(x->>'end_time','')::time,x->>'timezone',x->>'event_type',x->>'title',x->>'original_title','scheduled',x->>'ticket_url',now(),'unreviewed'
      from jsonb_array_elements(p_payload->'events') x where x->>'event_key'=v_key returning id into v_event_id;
    else
      if exists (select 1 from events e join jsonb_array_elements(p_payload->'events') x on x->>'event_key'=v_key where e.id=v_event_id and (e.organization_id<>v_org_id or e.venue_id<>v_venue_id or e.date<>(x->>'date')::date or e.timezone<>x->>'timezone' or e.original_title<>x->>'original_title')) then raise exception 'existing Event field conflict %',v_key; end if;
    end if;
    insert into _graph_events values (v_key,v_event_id);
    if exists (select 1 from event_sources where source=p_payload->>'source' and source_event_id=v_source_event and event_id<>v_event_id) then raise exception 'source identity conflict %',v_source_event; end if;
    if not exists (select 1 from event_sources where source=p_payload->>'source' and source_event_id=v_source_event) then
      insert into event_sources(event_id,source,source_event_id,source_url) select v_event_id,p_payload->>'source',v_source_event,x->>'source_url' from jsonb_array_elements(p_payload->'events') x where x->>'event_key'=v_key;
    end if;
  end loop;

  for v_key in select x->>'candidate_key' from jsonb_array_elements(coalesce(p_payload->'composers','[]'::jsonb)) x loop
    if not exists (select 1 from composers c join jsonb_array_elements(p_payload->'composers') x on x->>'candidate_key'=v_key where c.canonical_name=x->>'canonical_name' and c.identity_key=x->>'normalized_form') then
      insert into composers(canonical_name,identity_key) select x->'raw_forms'->>0, x->>'normalized_form' from jsonb_array_elements(p_payload->'composers') x where x->>'candidate_key'=v_key;
    end if;
  end loop;
  for v_key in select x->>'candidate_key' from jsonb_array_elements(coalesce(p_payload->'works','[]'::jsonb)) x loop
    if not exists (select 1 from works w join jsonb_array_elements(p_payload->'works') x on x->>'candidate_key'=v_key where w.composer_id=(x->>'composer_id')::uuid and w.identity_key=x->>'normalized_source_title') then
      insert into works(title,composer,composer_id,identity_key,work_kind,parent_work_id,normalization_status) select x->>'proposed_canonical_title',x->>'composer',(x->>'composer_id')::uuid,x->>'normalized_source_title','work',null,'canonical' from jsonb_array_elements(p_payload->'works') x where x->>'candidate_key'=v_key;
    end if;
    select id into v_work_id from works w join jsonb_array_elements(p_payload->'works') x on x->>'candidate_key'=v_key where w.composer_id=(x->>'composer_id')::uuid and w.identity_key=x->>'normalized_source_title' limit 1;
    insert into _graph_works values (v_key,v_work_id);
  end loop;
  for v_key,v_work_id in select x->>'event_key',coalesce(nullif(x->>'work_id','')::uuid,(select production_id from _graph_works where candidate_key=x->>'candidate_key')) from jsonb_array_elements(coalesce(p_payload->'relationships','[]'::jsonb)) x loop
    select production_id into v_event_id from _graph_events where staging_key=v_key;
    if v_event_id is null or v_work_id is null then raise exception 'relationship identity unresolved %',v_key; end if;
    if exists(select 1 from event_programme ep join jsonb_array_elements(p_payload->'relationships') x on x->>'event_key'=v_key where ep.event_id=v_event_id and ((ep.work_id=v_work_id and ep."order"<>(x->>'order')::integer) or (ep."order"=(x->>'order')::integer and ep.work_id<>v_work_id))) then raise exception 'event programme conflict %',v_key; end if;
    if not exists(select 1 from event_programme ep join jsonb_array_elements(p_payload->'relationships') x on x->>'event_key'=v_key where ep.event_id=v_event_id and ep.work_id=v_work_id and ep."order"=(x->>'order')::integer) then
      insert into event_programme(event_id,work_id,"order") select v_event_id,v_work_id,(x->>'order')::integer from jsonb_array_elements(p_payload->'relationships') x where x->>'event_key'=v_key;
    end if;
  end loop;
  select jsonb_build_object('organization_id',v_org_id,'venue_id',v_venue_id,'events',count(*)) into v_result from _graph_events;
  return v_result;
end;
$$;
revoke all on function public.apply_canonical_production_graph(jsonb) from public, anon, authenticated;
grant execute on function public.apply_canonical_production_graph(jsonb) to service_role;
