import unittest
from unittest.mock import patch
from types import SimpleNamespace
from work_cast_policy import work_role_policy, select_performance_principal, describe_work_cast_schema, credit_for_display
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

    def test_reviewed_extension_uses_work_roles_across_venues_and_dates(self):
        work = '0d6b0faf-e33f-4e4e-bd13-028bff881cd0'
        role = 'f3fb97bf-1a71-5434-9425-6743bfeb647f'
        programme = [{'works': {'id': work, 'normalization_status': 'verified', 'work_kind': 'work'}}]
        for venue, date, name in [('Berlin', '2026-12-23', 'First singer'), ('Other venue', '2027-01-03', 'Different singer')]:
            credit = {'artist_id': name, 'artists': {'artist_name': name}, 'role': 'singer',
                      'character_id': role, 'work_characters': {'work_id': work, 'canonical_name': 'Hänsel'}}
            result = build_summary({'event_type': 'opera', 'venue': venue, 'date': date}, programme, [credit], [])
            self.assertEqual(result['principal_cast'][0]['artist_name'], name)
            self.assertEqual(result['principal_cast'][0]['display_order'], 1)

    def test_source_only_vixen_policy_keeps_character_identity_unresolved(self):
        work = 'de5772af-254e-59e5-aa8a-09c907cd4124'
        programme = [{'works': {'id': work, 'normalization_status': 'verified', 'work_kind': 'work'}}]
        credit = {'artist_id': 'published', 'artists': {'artist_name': 'Published singer'},
                  'role': 'cast', 'raw_character': 'Füchsin', 'character_id': None}
        result = build_summary({'event_type': 'opera'}, programme, [credit], [])
        selected = result['principal_cast'][0]
        self.assertEqual(selected['selection_basis'], 'reviewed_source_role')
        self.assertIsNone(selected['character_id'])
        self.assertEqual(result['principal_cast'][0]['character'], 'Füchsin')
        self.assertEqual(credit['character_id'], None)

    def test_extension_excludes_production_and_unreviewed_role_slots(self):
        work = '10f5309c-7ec8-48d7-8350-9f27f39a6d73'
        self.assertIsNone(work_role_policy(work, work_character_id='efbff082-644c-476d-9879-3f1007eee78a',
                                          source_character='Ballett 3. Akt: Pastoria'))
        self.assertIsNone(work_role_policy(work, source_character='lighting designer'))
        selected = work_role_policy(work, source_character='Princesa de Bouillon')
        self.assertEqual(selected['display_order'], 3)
        self.assertIsNone(selected['work_character_id'])

    def test_legacy_role_function_is_shared_by_detail_and_summary(self):
        from api.index import _serialize_event_credit
        work = 'd388a4fb-5bb6-4a8f-bc2f-3b5c201e7de2'
        programme = [{'works': {'id': work, 'normalization_status': 'verified', 'work_kind': 'work'}}]
        row = {'artist_id': 'published', 'artists': {'artist_name': 'Published Porgy'}, 'role': 'porgy'}
        detail = _serialize_event_credit(row, event={'event_type': 'opera'}, programme_rows=programme)
        summary = build_summary({'event_type': 'opera'}, programme, [row], [])
        self.assertEqual(detail['role_type'], 'cast')
        self.assertEqual(detail['character'], summary['principal_cast'][0]['character'])
        self.assertEqual(detail['raw_role_label'], 'porgy')
        self.assertNotIn('raw_character', row)
        self.assertIsNone(summary['principal_cast'][0]['character_id'])
        self.assertFalse(build_summary({'event_type': 'opera'}, [], [row], [])['principal_cast'])
        self.assertFalse(build_summary({'event_type': 'concert'}, programme, [row], [])['principal_cast'])

    def test_legacy_supporting_role_uses_full_schema_without_assigning_identity(self):
        programme = [{'works': {'id': WORK, 'normalization_status': 'verified', 'work_kind': 'work'}}]
        row = {'role': 'published_minor_role', 'artist_id': 'a'}
        roles = [{'id': 'minor', 'work_id': WORK, 'canonical_name': 'Published minor role'}]
        result = credit_for_display({'event_type': 'opera'}, programme, row, roles)
        self.assertEqual(result['raw_character'], 'Published minor role')
        self.assertIsNone(result.get('character_id'))
        ambiguous = programme + [{'works': {'id': 'another-work', 'normalization_status': 'verified', 'work_kind': 'work'}}]
        roles.append({'id': 'second', 'work_id': 'another-work', 'canonical_name': 'Published minor role'})
        self.assertIs(credit_for_display({'event_type': 'opera'}, ambiguous, row, roles), row)
        for label in ['Piano', 'Conductor', 'Soprano', 'Kampfmeister']:
            function = {'role': label}
            graph = [{'id': 'bad-slot', 'work_id': WORK, 'canonical_name': label}]
            self.assertIs(credit_for_display({'event_type': 'opera'}, programme, function, graph), function)

    def test_ingestion_recognizes_reviewed_role_in_source_function(self):
        def character(label, *args):
            self.assertEqual(label, 'Tannhäuser')
            return {'status': 'SAFE_CHARACTER', 'character_id': ROLE, 'character': label}
        artist = {'status': 'SAFE_EXISTING', 'artist_id': 'published', 'canonical_name': 'Published actor'}
        with patch('season_ingestion.credit_resolution._character_resolution', side_effect=character), patch('season_ingestion.credit_resolution._artist_resolution', return_value=artist):
            for raw in [{'source_role': 'Tannhäuser'}, {'source_role': 'Tenor', 'character': 'Tannhäuser', 'credit_kind': 'cast'}]:
                result = resolve_credit({**raw, 'artist_name': 'Published actor'}, work_id=WORK, snapshot=SimpleNamespace())
                self.assertEqual(result['canonical_role'], 'performer')
                self.assertEqual(result['work_role_policy']['display_order'], 1)
        with patch('season_ingestion.credit_resolution._character_resolution', return_value={'status': 'NO_CHARACTER'}), patch('season_ingestion.credit_resolution._artist_resolution', return_value=artist):
            result = resolve_credit({'source_role': 'Soprano', 'character': 'Soprano', 'credit_kind': 'cast'}, work_id=WORK, snapshot=SimpleNamespace())
            self.assertIsNone(result['source_character'])

    def test_artistic_functions_inside_legacy_cast_containers_are_not_cast(self):
        from api.index import _serialize_event_credit
        for label, function in [('Conductor', 'conductor'), ('Chorus Director', 'chorus_master'), ('Orchestra', 'orchestra')]:
            row = {'artist_id': 'published', 'artists': {'artist_name': 'Published musician'},
                   'role': 'performer', 'character': label, 'raw_character': label}
            normalized = credit_for_display({'event_type': 'opera'}, PROG, row)
            self.assertEqual(normalized['role'], function)
            self.assertIsNone(normalized['character'])
            detail = _serialize_event_credit(row, event={'event_type': 'opera'}, programme_rows=PROG)
            self.assertEqual(detail['role_type'], 'artistic_team')
            self.assertFalse(build_summary({'event_type': 'opera'}, PROG, [row], [])['principal_cast'])
            self.assertEqual(row['raw_character'], label)
        linked = {'role': 'performer', 'character_id': 'existing-role', 'raw_character': 'Conductor'}
        self.assertIs(credit_for_display({'event_type': 'opera'}, PROG, linked), linked)
        supporting = {'role': 'performer', 'raw_character': 'Stage director'}
        graph = [{'id': 'dramatic-role', 'work_id': WORK, 'canonical_name': 'Stage director'}]
        self.assertIs(credit_for_display({'event_type': 'opera'}, PROG, supporting, graph), supporting)

    def test_ingestion_function_semantics_take_priority_over_a_cast_wrapper(self):
        from season_ingestion.credit_resolution import canonical_role
        self.assertEqual(canonical_role('Chorus-Director'), 'chorus_master')
        self.assertEqual(canonical_role('cheffe de choeur'), 'chorus_master')
        artist = {'status': 'SAFE_EXISTING', 'artist_id': 'published', 'canonical_name': 'Published musician'}
        with patch('season_ingestion.credit_resolution._character_resolution', return_value={'status': 'NO_CHARACTER'}), patch('season_ingestion.credit_resolution._artist_resolution', return_value=artist):
            for raw in [{'source_role': 'Chorus Director', 'character': 'Chorus Director', 'credit_kind': 'cast'},
                        {'source_role': 'performer', 'character': 'Chorus Director', 'credit_kind': 'cast'},
                        {'source_role': 'Conductor', 'character': 'Conductor', 'credit_kind': 'cast'}]:
                result = resolve_credit({**raw, 'artist_name': 'Published musician'}, work_id=WORK, snapshot=SimpleNamespace())
                self.assertIn(result['canonical_role'], {'conductor', 'chorus_master'})
                self.assertEqual(result['credit_kind'], 'artistic_team')
                self.assertIsNone(result['source_character'])
            conflict = resolve_credit({'source_role': 'Conductor', 'character': 'Tannhäuser', 'artist_name': 'Published musician'}, work_id=WORK, snapshot=SimpleNamespace())
            self.assertEqual(conflict['resolution_status'], 'REVIEW_SOURCE_AMBIGUOUS')
            self.assertIsNone(conflict['source_character'])

    def test_missing_performance_relations_do_not_inherit_neighbour_cast(self):
        populated=build_summary({'event_type':'performance'},PROG,[actor('Other date actor')],[])
        missing=build_summary({'event_type':'performance'},[],[],[])
        self.assertEqual(len(populated['principal_cast']),1)
        self.assertEqual(missing['principal_cast'],[])
        self.assertEqual(missing['conductors'],[])

if __name__=='__main__':unittest.main()
