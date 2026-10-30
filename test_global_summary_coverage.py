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
            reviewed_on_30.update({'03789442-bc3d-5651-bbfd-1afa3be8c521', 'cb7fb035-b4ed-4a18-8841-3aaf82d34c28', 'e5357cde-7d7b-5531-b792-f5d239b87412', 'dc200d09-5674-42b8-a5e4-970ce5c7753a', '7b3158f8-a80f-57d6-81f6-954fb36b42b8', 'c37b88dd-d620-4e92-afe5-eae0ad6d09cc', 'af21deb5-5726-5cf7-babc-61be6ffc5f53', '50edbad5-9e58-4b01-b0a6-e1c760973d3e', '6039838c-42a0-517c-8089-3dcc15bee305', '1bb70185-77cb-561b-8fc8-045c036f082c', 'a27e0e30-1741-50ac-820b-939f0d8e25f4', 'eba10ae3-2db3-5d66-a969-eee504ca117e', 'ff44b983-f973-4e00-8e48-f4bd71f50ac8', '8c21d4ce-09c5-43fe-bf37-533b6681ae67', '21821df6-ebd5-4be4-8abe-8a6865f055dd', 'bec7040a-51b1-5fed-8ba0-25810c16eef4', '51a41546-6a5a-4646-bc0a-aea226e4856d', 'd61ee9e6-c0ed-5a37-8957-f92b08a0f920', '800bff67-f1ed-4d4c-87a5-c14b9e82323c', 'f9b30d34-1fb2-4ee7-8de1-08353ff6f1a9', '4141ea8b-e7be-5578-a6f3-3cf9cfec88e3', '7462644c-2cb5-429b-85a2-c2ea9735f48d', 'c527a34e-a7b0-40da-ad7d-6a4af5d58fd1', '27c95ae0-c9c6-4ef6-ba7a-39cfdc7c9e58', '85558edc-9ca9-5bd6-9f91-73597938fa4c', 'c7fca9db-9c25-5bcb-a928-30872575133b', '9ea85708-76c0-4d64-a69f-c6f84f039157', '2dc9de26-6060-5c26-9b9e-f6386c70a2e2', '8b5f4313-9a07-49ff-a188-7c06e688517c', '6dec4141-6680-53c5-b308-00aae6066dd8', '5159aa2c-f32e-5739-86bb-7c2d8b34ba56', '0c6fadd4-2189-45af-8f76-29f885fde07f', '8d762448-8b1e-4415-b0d5-8d2ce809fafd', '9115c5ee-8d2d-4fdc-af23-0c743d15b336', '31ee6859-53a9-51b0-95a1-e8b4b97ff51c', 'e98a3519-dc32-5cbd-baea-e3ee73b0227c', 'b8151f32-aaaf-409e-86c8-f4d08fdeaaf0', 'c7183ebe-358f-575e-98da-582c93f9ab6d', '23079899-ba70-418c-919c-c503a6cba28f', '12935dde-8f56-5127-bb55-c28ea18e1103', '56ac40ee-15dc-5d5a-9cf4-9ce6958f68d7', 'd80d8d7a-2f58-46ac-8c33-589fee285647', '62792d47-7e4c-4b8d-8e59-1d8dfa51f6ed', '222c330a-8151-4996-95bb-6b34a7bf2cf6', 'e09a5a07-9788-4cae-9d6a-a84cad9eb625', '6062d013-247a-5c05-ab99-86c0c953c975', 'e1fab70f-dd1d-5bd5-9494-32e8690e029d', '8b994ce5-e556-47fd-a373-f62ebe882b35', '4b245901-dd06-4e24-8bf6-0a58b882c794', '8c9e50f8-bffc-4e90-964c-509c298af60f', '98019d57-67ef-43b0-8e2a-c1de4bf21ee9', '481e2d19-7f7d-4f9e-a4c7-3cc8bba63895', '17a06497-38c5-5d90-aee4-e5172485a500', '4aa00908-1beb-50aa-83c3-36c35099fed6', '891ae003-0cc5-59e2-a1f0-185dca860123', 'bf62ec6e-c057-4c4b-9207-9087cf169e64', '52a938d2-16b6-4428-9c57-923af252cda2', '284d1a25-2ab1-583f-866b-72adc6fb5037', '23564414-ad2b-5b29-91c9-af7fb349f92b', '7badf1e3-d71e-582b-a117-7bde542f459b', 'a3a7935a-1e43-4d48-931a-a92fc53533c7', '26fcfc15-deb6-5171-b717-dde07388c323', '42f5cb1e-83a4-4635-9e33-e5fad59777f7', '98b42ce0-6563-44b2-b52b-5d86071b9ae6', '8e2a4c82-ec3b-5cbe-a4f1-6fec5018c10d', '6102804a-7c9b-418a-b804-e48bc54b4860', '425292f8-66ea-56c3-8816-c9d1821554d8', 'b91d88a5-3e48-4017-bc95-f7e3386acb19', '69dbb351-1792-45a5-9e28-4005f8be6050', 'c1bf7819-2c85-483a-b69e-aef2dc1eb2c6', '5a0800d5-a998-514f-80f4-78865ee17c32', '2531c8e4-a707-58bf-adb7-9d481cf651a6', '4f7c7b2e-928b-4b18-b628-1f6d4a7adf22'})
            reviewed_on_30.update({'8b042d52-2d23-4b7b-bcdb-524d10e992cb', '03d676c5-df6a-4b27-a2ca-c18d4ef02fba', 'fbf1e422-bec4-59ec-9e02-1c3046f67f03', '8ee0f793-8378-5980-be23-6e8978575af2', 'cf6b91b8-045c-58cb-b36b-935630737658', '0b302bbd-813a-56b2-9c43-5cdcef7ba46a', 'd15d726c-0e7c-463b-a272-b38780b56a25', '9cbb09b4-d8cc-45a1-a56d-6d1887e1ac91', 'b22b4b2b-37b3-4f80-91c3-25aceeee7c79', 'ff19a877-a11c-5c7c-873f-4846afcb261a', 'd7835c88-7d1d-5036-a2da-a848c2f7b0c9', '825e1f24-5b95-4e9a-9050-2e64e9395df6', 'b9e1674f-c290-56b3-978c-de9ed6b90450', '7859b3da-0ffa-52e8-8b11-313d1b612859', 'c01ef840-80e5-534f-8ee7-619d5e896f20', '695df17a-91fd-5fc8-85f8-df97ff8e51d9', '9a110ca2-d4b5-40c7-b6d0-56bf55909301', '73003312-7de6-42a0-9e21-327bb0a9a40c', 'f623f325-fefc-5df2-b19a-444bac473d98', 'b32c8817-e7b8-5927-8a0c-86735c08849d'})
            reviewed_on_30.update({'41bf570d-75c0-5401-9415-cf47ed6189c3', 'c3664983-2719-54d1-9ce6-31cbd75b8462', '2c1209b8-5e60-42b2-9b08-3bb4c08571dc', '6d222672-ec92-4aa4-82c1-13711b5e43a2', '7e809a3f-a6b0-47b7-bf22-8ac23265b562', '3a49b72f-918c-46d6-9984-78479d53fcdd', 'a97c6f9b-7f9f-50be-91c0-253f97fe9c2c', '140a1d6f-2944-44a2-8cca-925b58053404', 'b83d6335-5e37-42fd-9b31-cc07a57fbc56', 'c946cf3f-8b7d-4b0a-ba16-671a92141512', '440df241-66d5-4778-b354-4cc44deb36d6', '81d99864-489b-4ba1-bbee-7f453c7966b2'})
            reviewed_on_30.update({'b597e357-f28b-49a9-8743-85a65d9d7bae', '96940e9a-4956-49f8-81e6-270df6e53570', 'd6079dc4-b0e2-43f7-b42d-79db98ef2843'})
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
