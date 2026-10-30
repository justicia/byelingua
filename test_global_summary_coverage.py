import json, unittest
from pathlib import Path
from unittest.mock import patch
from schedule_summary_data import build_summary, REVIEWED_PRINCIPAL_ROLES, REVIEWED_PROGRAMME_EXPECTATIONS
from season_ingestion.programme_coverage import require_programme_coverage
from season_ingestion.production_graph import build_payload, apply_graph

TOSCA='c4551c69-40aa-41d6-8d8b-8f4caa9b372f'
def programme(work=TOSCA):return [{'works':{'id':work}}]
def cast(name,character='Floria Tosca',**extra):return {'artist_id':name,'artists':{'artist_name':name},'role':'performer','raw_character':character,**extra}

class GlobalSelectionTests(unittest.TestCase):
    def test_source_only_role_works_across_venues_without_assigning_character_identity(self):
        for venue in ['Vienna','Paris','Berlin','London']:
            s=build_summary({'event_type':'opera','venue':venue},programme(),[cast(venue)],[])
            self.assertEqual(s['principal_cast'][0]['artist_name'],venue)
            self.assertIsNone(s['principal_cast'][0]['character_id'])
            self.assertEqual(s['principal_cast'][0]['selection_basis'],'reviewed_source_role')
    def test_cast_function_from_current_source_credits_is_supported(self):
        result=build_summary({'event_type':'opera'},programme(),[cast('Source credit',role='cast')],[])
        self.assertEqual(result['principal_cast'][0]['artist_name'],'Source credit')
    def test_wrong_work_ballet_and_production_function_are_excluded(self):
        for event,progs,credit in [({'event_type':'ballet'},programme(),cast('A')),({'event_type':'opera'},programme('other'),cast('A')),({'event_type':'opera'},programme(),cast('A',character='Floria Tosca',role='stage_director'))]:
            self.assertFalse(build_summary(event,progs,[credit],[])['principal_cast'])
    def test_linked_unreviewed_id_cannot_be_overridden_by_its_raw_label(self):
        s=build_summary({'event_type':'opera'},programme(),[cast('A',character_id='unreviewed',work_characters={'work_id':TOSCA,'canonical_name':'Floria Tosca'})],[])
        self.assertFalse(s['principal_cast'])
    def test_new_work_unknown_role_never_becomes_principal_by_billing_order(self):
        s=build_summary({'event_type':'opera'},programme('new-work'),[cast('Star','First role')],[])
        self.assertEqual(s['cast_status'],'unclassified')
    def test_reviewed_variants_and_performance_specific_artists(self):
        work='2746a542-69dc-4047-856d-6f2162bdcd46'
        for name in ['First night','Second night']:
            s=build_summary({'event_type':'opera'},programme(work),[cast(name,'Cio-Cio San'),cast(name,'Cio-Cio-San')],[])
            self.assertEqual(len(s['principal_cast']),1)
            self.assertEqual(s['principal_cast'][0]['artist_name'],name)
    def test_multiwork_role_name_collision_is_not_guessed(self):
        progs=programme('34151afa-505c-4f03-b190-9774d6b81630')+programme('72413b78-c83c-4131-ac0c-d2452ae71131')
        self.assertFalse(build_summary({'event_type':'opera'},progs,[cast('A','Sophie')],[])['principal_cast'])
    def test_linked_and_source_spelling_do_not_duplicate_same_role_artist(self):
        cid=next(cid for cid,rank in REVIEWED_PRINCIPAL_ROLES[TOSCA]['characters'].items() if rank==1)
        rows=[cast('A',character_id=cid,work_characters={'work_id':TOSCA,'canonical_name':'Floria Tosca'}),cast('A')]
        self.assertEqual(len(build_summary({'event_type':'opera'},programme(),rows,[])['principal_cast']),1)
    def test_all_rule_ids_are_from_reviewed_current_global_inventory(self):
        self.assertGreaterEqual(len(REVIEWED_PRINCIPAL_ROLES),38)
        for work_id, rule in REVIEWED_PRINCIPAL_ROLES.items():
            self.assertTrue(rule['evidence'].startswith('https://'))
            reviewed_on_29 = {
                '5f65922a-184b-4485-9562-37d9bd688bd3',
                '0d6b0faf-e33f-4e4e-bd13-028bff881cd0', '34614acb-087a-4603-a4e2-8b57ae786a32',
                '3d3bd914-7a54-4e98-bcb4-a1955127c2eb', 'cbae154e-1883-4150-a99f-598bfd921ea0',
                '10f5309c-7ec8-48d7-8350-9f27f39a6d73', 'd2744f32-d954-5472-a2d9-2f0c4d2b7906',
                'b6fb8e68-537c-4d69-bfd7-550fde3df04c', 'e7f4848e-6560-5708-8dd4-054627334e6a',
                'de5772af-254e-59e5-aa8a-09c907cd4124',
                '4e0a910d-406d-50f7-b2f4-fe51cb8b763c',
                '4f51f3ac-3f0c-4591-9191-5c6735c33e9e', '5f5d66e8-8e3f-47ae-a68c-bc1ee2338a73',
                '69e72a89-ecca-4725-b8d1-936adfe1a024',
            }
            reviewed_on_30 = {'a2657822-cdaf-4750-bfbf-f3daa762244e', '8482965a-c819-47aa-808d-8407c86a8d31', '475053d9-8d32-451e-baed-a7d950ebca2c', 'e2661dab-fa7d-42bb-92b5-e3ca9dae0ea9', '7f552f18-d0bf-4ad7-bb2c-812ae1e05821', '93072805-d1ae-472c-a7c9-3a2237962b97', '146036ca-40eb-48d7-b8f8-b61322c77989', 'f7dad73d-91fe-4e8c-8e7f-86615b286900'}
            reviewed_on_30.update({'1a063e71-a8ab-4d4d-b45d-55f07897849c', '242085af-163c-42de-a7a5-7da206bf2835', '852d9462-99a5-48a3-95e1-7914a1540031', 'fb7c48b8-209f-4bac-91c6-f70e6d25435c'})
            expected_review = '2026-10-30' if work_id in reviewed_on_30 else ('2026-10-29' if work_id in reviewed_on_29 else '2026-10-22')
            self.assertEqual(rule['reviewed_on'], expected_review)
    def test_expectation_checks_work_identity_not_count_alone(self):
        key,expected=next((k,v) for k,v in REVIEWED_PROGRAMME_EXPECTATIONS.items() if len(v['work_ids'])>1)
        event={'event_type':'concert','event_key':key}
        count=len(expected['work_ids'])
        wrong=build_summary(event,programme('wrong'),[],[{'title':'Wrong'}]*count)
        self.assertEqual(wrong['programme_status'],'partial')
        complete=[{'works':{'id':x}} for x in expected['work_ids']]
        self.assertEqual(build_summary(event,complete,[],[{'title':'Recorded'}]*count)['programme_status'],'unknown')

class ProgrammeGuardTests(unittest.TestCase):
    def test_multiwork_overwrite_is_rejected_for_any_venue(self):
        for source in ['venue-a','venue-b']:
            e={'event_key':source,'programme':[{'source_title':str(i),'source_programme_index':i} for i in [1,2,3]]}
            with self.assertRaises(ValueError):require_programme_coverage([e],[{'event_key':source,'work_id':'third','order':3}])
    def test_reviewed_deferral_preserves_source_order_and_partial_status(self):
        event={'event_key':'e','programme':[{'source_title':'One'},{'source_title':'Two'}]}
        report=require_programme_coverage([event],[{'event_key':'e','work_id':'two','order':2}],[{'event_key':'e','source_programme_index':1,'reason':'Ambiguous edition','reviewed':True}])
        self.assertEqual(report['events'][0]['status'],'reviewed_partial')
    def test_unknown_source_cannot_be_claimed_complete(self):
        report=require_programme_coverage([{'event_key':'e'}],[])
        self.assertEqual(report['events'][0]['status'],'source_unknown')
    def test_duplicate_and_orphan_relationships_are_rejected(self):
        for rels in [[{'event_key':'e','work_id':'w','order':1}]*2,[{'event_key':'other','work_id':'w','order':1}]]:
            with self.assertRaises(ValueError):require_programme_coverage([{'event_key':'e','programme':[{'source_title':'One'}]}],rels)
    def test_apply_rechecks_after_payload_was_built_before_network(self):
        payload={'events':[{'event_key':'e','programme':[{'source_title':'One'},{'source_title':'Two'}]}],'relationships':[{'event_key':'e','work_id':'w','order':2}]}
        sender=lambda *a,**kw:self.fail('No network is allowed when source coverage fails')
        with self.assertRaisesRegex(ValueError,'programme loss'):apply_graph(payload,sender=sender)

if __name__=='__main__':unittest.main()
