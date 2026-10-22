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
        for rule in REVIEWED_PRINCIPAL_ROLES.values():
            self.assertTrue(rule['evidence'].startswith('https://'))
            self.assertEqual(rule['reviewed_on'],'2026-10-22')
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
