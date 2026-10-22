"""Source-to-relation completeness checks shared by all venue adapters.

Counts never imply source completeness when no source programme was captured.
This module resolves no identities and performs no database access or writes.
"""
from collections import Counter, defaultdict


def programme_coverage_report(events, relationships, deferred=()):
    actual=defaultdict(list)
    for row in relationships:
        actual[str(row.get('event_key'))].append(row)
    holds={}
    for row in deferred:
        if not row.get('reason') or not row.get('reviewed'):
            raise ValueError('programme deferral needs an explicit reviewed reason')
        holds[(str(row['event_key']),int(row['source_programme_index']))]=row['reason']
    report=[]
    for event in events:
        key=str(event['event_key']);source=event.get('programme')
        if not isinstance(source,list):
            report.append({'event_key':key,'status':'source_unknown','missing':[],'deferred':[]});continue
        seen=Counter((int(r.get('order') or r.get('original_programme_order') or r.get('source_programme_index') or 1),str(r.get('work_id') or '')) for r in actual[key])
        missing=[];held=[]
        for i,item in enumerate(source,1):
            order=int(item.get('original_programme_order') or item.get('source_programme_index') or item.get('order') or i)
            work=str(item.get('work_id') or '')
            found=any(o==order and (not work or w==work) for (o,w),n in seen.items() if n)
            if not found:
                gap={'source_programme_index':order,'source_title':item.get('source_title'),'work_id':work or None}
                if (key,order) in holds:held.append({**gap,'reason':holds[(key,order)]})
                else:missing.append(gap)
        duplicates=[{'order':o,'work_id':w,'count':n} for (o,w),n in seen.items() if n>1]
        report.append({'event_key':key,'source_items':len(source),'staged_relations':len(actual[key]),'status':'unexplained_gap' if missing or duplicates else 'reviewed_partial' if held else 'matches_source_observations','missing':missing,'deferred':held,'duplicates':duplicates})
    event_keys={str(e['event_key']) for e in events}
    orphan_keys=sorted(set(actual)-event_keys)
    return {'events':report,'orphan_event_keys':orphan_keys,'unexplained_events':sum(r['status']=='unexplained_gap' for r in report),'source_unknown_events':sum(r['status']=='source_unknown' for r in report)}


def require_programme_coverage(events, relationships, deferred=()):
    report=programme_coverage_report(events,relationships,deferred)
    if report['unexplained_events'] or report['orphan_event_keys']:
        raise ValueError('unexplained source programme loss before production apply')
    return report
