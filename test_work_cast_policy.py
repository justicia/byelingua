import unittest
from unittest.mock import patch
from types import SimpleNamespace
from work_cast_policy import work_role_policy, select_performance_principal, describe_work_cast_schema
from work_cast_registry import WORK_CAST_POLICIES
from schedule_summary_registry import PRINCIPAL_ROLES
from schedule_summary_data import REVIEWED_PRINCIPAL_ROLES, build_summary
from season_ingestion.credit_resolution import resolve_credit

WORK='8a8d9b81-329e-45c9-9ac7-3665898bd139'
ROLE='a2a742be-2919-4a99-b7ee-799dc7ad6c79'
PROG=[{'works':{'id':WORK,'normalization_status':'verified','work_kind':'work'}}]
def actor(name,*,linked=True,work=WORK,role=ROLE):
    return {'artist_id':name,'artists':{'artist_name':name},'role':'singer','character':'Tannhäuser',
            'character_id':role if linked else None,
            'work_characters':{'work_id':work,'canonical_name':'Tannhäuser'}if linked else None}

class WorkCastPolicyTests(unittest.TestCase):
    def test_all_consumers_share_one_policy_registry(self):
        self.assertIs(WORK_CAST_POLICIES,PRINCIPAL_ROLES)
        self.assertIs(WORK_CAST_POLICIES,REVIEWED_PRINCIPAL_ROLES)

    def test_generic_source_type_cannot_hide_a_verified_work_role(self):
        for event in [{'event_type':'performance'},{'event_type':'other','raw_event_type':'performance'}]:
            result=build_summary(event,PROG,[actor('Recorded actor')],[])
            self.assertEqual([x['artist_name']for x in result['principal_cast']],['Recorded actor'])

    def test_generic_source_requires_a_verified_full_work(self):
        for p in [[{'works':{'id':WORK}}],[{'works':{'id':WORK,'normalization_status':'review_required','work_kind':'work'}}],
                  [{'works':{'id':WORK,'normalization_status':'verified','work_kind':'programme_component'}}]]:
            self.assertIsNone(select_performance_principal({'event_type':'performance'},p,actor('A')))

    def test_explicit_different_presentation_is_not_overridden(self):
        for event in [{'event_type':'ballet'},{'event_type':'concert'},{'event_type':'other','raw_event_type':'workshop'},
                      {'event_type':'other'},{'event_type':'other','raw_event_type':'ballet'}]:
            self.assertIsNone(select_performance_principal(event,PROG,actor('A')))

    def test_same_work_roles_reused_while_dates_and_actors_remain_distinct(self):
        schema_before=describe_work_cast_schema([WORK],[{'id':ROLE,'work_id':WORK,'canonical_name':'Tannhäuser','character_uid':'global-existing-id'}])
        for venue in ['Berlin','Paris','Unseen venue']:
            first=build_summary({'event_type':'opera','venue':venue,'date':'2027-03-20'},PROG,[actor('First actor')],[])
            second=build_summary({'event_type':'opera','venue':venue,'date':'2027-03-26'},PROG,[actor('Second actor')],[])
            self.assertEqual(first['principal_cast'][0]['character_id'],second['principal_cast'][0]['character_id'])
            self.assertNotEqual(first['principal_cast'][0]['artist_id'],second['principal_cast'][0]['artist_id'])
        self.assertIsNone(schema_before[0]['artist_id'])
        self.assertEqual(schema_before[0]['global_character_id'],'global-existing-id')

    def test_wrong_work_link_is_not_reinterpreted_by_label(self):
        self.assertIsNone(select_performance_principal({'event_type':'opera'},PROG,actor('A',work='other-work')))
        self.assertIsNone(select_performance_principal({'event_type':'opera'},PROG,actor('A',role='unreviewed-role')))

    def test_source_only_role_does_not_assign_canonical_character_identity(self):
        result=select_performance_principal({'event_type':'performance'},PROG,actor('A',linked=False))
        self.assertEqual(result['display_order'],1)
        self.assertIsNone(result['work_character_id'])

    def test_full_work_schema_includes_unclassified_roles_without_fabricating_actors(self):
        roles=[{'id':ROLE,'work_id':WORK,'canonical_name':'Tannhäuser'},
               {'id':'minor-role','work_id':WORK,'canonical_name':'Published minor role'},
               {'id':'foreign','work_id':'other','canonical_name':'Other work role'}]
        result=describe_work_cast_schema([WORK],roles)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['principal_display_order'],1)
        self.assertEqual(result[1]['selection_status'],'unclassified')
        self.assertTrue(all(r['artist_id']is None and r['artist_name']is None for r in result))

    def test_ingestion_classifies_work_role_before_matching_artist(self):
        calls=[]
        def char(*args):calls.append('role');return {'status':'SAFE_CHARACTER','character_id':ROLE,'character':'Tannhäuser'}
        def artist(*args):calls.append('artist');return {'status':'SAFE_EXISTING','artist_id':'existing','canonical_name':'Published Actor'}
        with patch('season_ingestion.credit_resolution._character_resolution',side_effect=char),patch('season_ingestion.credit_resolution._artist_resolution',side_effect=artist):
            result=resolve_credit({'source_role':'singer','character':'Tannhäuser','artist_name':'Published Actor'},work_id=WORK,snapshot=SimpleNamespace())
        self.assertEqual(calls,['role','artist'])
        self.assertEqual(result['work_role_policy']['display_order'],1)
        self.assertEqual(result['artist_resolution']['artist_id'],'existing')


    def test_public_detail_and_owned_summary_use_identical_work_selection(self):
        from api.index import schedule_event_detail, get_schedule_summary
        programme=[{**PROG[0], 'event_id':'performance-1', 'order':1}]
        credits=[{**actor('Published actor'), 'event_id':'performance-1'}]
        source_event={'event_id':'source:one', 'event_type':'performance', 'title':'Tannhäuser'}
        def cached(path, params=None, ttl=60):
            if path=='/rest/v1/event_catalog_v1': return [source_event]
            if path=='/rest/v1/event_programme': return programme
            if path=='/rest/v1/event_credits':
                self.assertIn('character_id',params['select'])
                self.assertIn('work_id',params['select'])
                return credits
            self.fail(path)
        def service(method,path,params=None,**kwargs):
            self.assertEqual(method,'GET')
            if path=='/rest/v1/events': return [{'id':'performance-1','room':'Published room'}]
            if path=='/rest/v1/work_characters':
                return [{'id':ROLE,'work_id':WORK,'canonical_name':'Tannhäuser','character_uid':None}]
            self.fail(path)
        with patch('api.index._cached_supabase_get',side_effect=cached),patch('api.index.supabase_service',side_effect=service):
            detail=schedule_event_detail('source:one')['event']
        with patch('api.index.authenticated_user',return_value={'id':'owner'}),patch('api.index._schedule_owned',return_value={'id':'schedule'}),patch('api.index._schedule_events_payload',return_value=[{'event_id':'performance-1','event':source_event}]),patch('api.index._schedule_summary_relations',side_effect=[programme,credits]):
            summary=get_schedule_summary({},'schedule')['events'][0]['event']
        self.assertEqual(detail['summary']['principal_cast'],summary['summary']['principal_cast'])
        self.assertEqual(detail['summary']['principal_cast'][0]['artist_name'],'Published actor')
        self.assertEqual(detail['work_character_skeleton'][0]['principal_display_order'],1)
        self.assertIsNone(detail['work_character_skeleton'][0]['global_character_id'])

    def test_missing_performance_relations_do_not_inherit_neighbour_cast(self):
        populated=build_summary({'event_type':'performance'},PROG,[actor('Other date actor')],[])
        missing=build_summary({'event_type':'performance'},[],[],[])
        self.assertEqual(len(populated['principal_cast']),1)
        self.assertEqual(missing['principal_cast'],[])
        self.assertEqual(missing['conductors'],[])

if __name__=='__main__':unittest.main()
