"""Prepare a read-only, scoped reconciliation query from reviewed staging.

Does not connect to a database, export a table, resolve entities or apply data.
An audit expectation is evidence, never authorization to replay a past batch.
"""
import argparse
import json
from pathlib import Path


def expectations_from_staging(paths):
    expected=[]
    for path in paths:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        for event in data.get('events',[]):
            if not event.get('event_key') or not isinstance(event.get('programme'),list):
                continue
            for row in event['programme']:
                if not row.get('work_id') or not isinstance(row.get('order'),int):
                    raise ValueError('reviewed staging requires explicit global work_id and order')
                expected.append({'event_key':event['event_key'],'work_id':row['work_id'],'order':row['order']})
    # Conflicting reviewed expectations must be resolved before querying.
    by_slot={}
    for row in expected:
        slot=(row['event_key'],row['order'])
        if slot in by_slot and by_slot[slot]!=row['work_id']:
            raise ValueError('conflicting historical expectations; review source version first')
        by_slot[slot]=row['work_id']
    return sorted({(r['event_key'],r['work_id'],r['order']) for r in expected})


def reconciliation_sql(expected):
    if not expected:
        raise ValueError('no explicit source-backed relationships to reconcile')
    def quote(value):return "'"+str(value).replace("'","''")+"'"
    values=',\n'.join('('+quote(key)+','+quote(work)+'::uuid,'+str(order)+')' for key,work,order in expected)
    return '''with expected(event_key,work_id,programme_order) as(values
'''+values+'''), scoped as(
select x.*,e.id event_id from expected x left join public.events e using(event_key)
), findings as(
select s.event_key,s.event_id,s.work_id,s.programme_order,
case when s.event_id is null then 'performance_key_not_found'
when w.id is null then 'work_id_not_found'
when exists(select 1 from public.event_programme p where p.event_id=s.event_id and p.work_id=s.work_id) then 'order_changed'
else 'missing_relationship' end issue
from scoped s left join public.works w on w.id=s.work_id
where not exists(select 1 from public.event_programme p where p.event_id=s.event_id and p.work_id=s.work_id and p."order"=s.programme_order)
)
select jsonb_build_object('expected_relationships',(select count(*) from expected),
'expected_performances',(select count(distinct event_key) from expected),
'findings',(select jsonb_agg(to_jsonb(f) order by event_key,programme_order) from findings f)) audit;
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--staging',type=Path,action='append',required=True)
    p.add_argument('--output-sql',type=Path,required=True)
    a=p.parse_args()
    expected=expectations_from_staging(a.staging)
    a.output_sql.write_text(reconciliation_sql(expected),encoding='utf-8')
    print(json.dumps({'expected_relationships':len(expected),'expected_performances':len({r[0] for r in expected}),'database_reads':0,'database_writes':0}))


if __name__=='__main__':main()
