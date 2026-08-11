-- Run only after Wiener credit normalization has been verified.
-- Characters remain scoped to the work; identical names in different works
-- are intentionally stored as different rows.

insert into public.work_characters (work_id, canonical_name)
select distinct ep.work_id, trim(ec.character)
from public.event_credits ec
join public.events e on e.id = ec.event_id
join public.event_programme ep on ep.event_id = e.id and ep."order" = 1
where e.event_type in ('opera', 'operetta', 'ballet')
  and ec.role in ('performer', 'singer')
  and ec.character is not null and trim(ec.character) <> ''
on conflict (work_id, canonical_name) do nothing;

update public.event_credits ec
set character_id = wc.id
from public.events e
join public.event_programme ep on ep.event_id = e.id and ep."order" = 1
cross join public.work_characters wc
where ec.event_id = e.id
  and wc.work_id = ep.work_id
  and wc.canonical_name = trim(ec.character)
  and e.event_type in ('opera', 'operetta', 'ballet')
  and ec.role in ('performer', 'singer')
  and ec.character is not null and trim(ec.character) <> '';

select wc.canonical_name, w.title as work_title, w.composer,
       count(ec.id) as credit_rows
from public.work_characters wc
join public.works w on w.id = wc.work_id
left join public.event_credits ec on ec.character_id = wc.id
group by wc.id, wc.canonical_name, w.title, w.composer
order by w.title, wc.canonical_name;
