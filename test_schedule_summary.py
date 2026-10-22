import unittest
from unittest.mock import patch
import api.index as api
from schedule_summary_data import build_summary, ARABELLA_WORK, REVIEWED_PRINCIPAL_ROLES

CHAR = 'c55729ad-c7f0-4efa-8c2f-d4f810077112'
def credit(name, role='performer', character=None, work=ARABELLA_WORK, char_id=CHAR):
    return {'artist_id': name, 'artists': {'artist_name': name}, 'role': role, 'character': character,
            'character_id': char_id if character else None,
            'work_characters': {'work_id': work, 'canonical_name': character} if character else None}
PROG = [{'works': {'id': ARABELLA_WORK}}]

class SummarySelectionTests(unittest.TestCase):
    def test_date_specific_cast_and_conductor_stay_separate(self):
        event = {'event_type': 'opera'}
        one = build_summary(event, PROG, [credit('June 1', character='Arabella'), credit('Conductor 1', 'conductor', character='Bad old label')], [])
        two = build_summary(event, PROG, [credit('June 2', character='Arabella'), credit('Conductor 2', 'conductor')], [])
        self.assertEqual([r['artist_name'] for r in one['principal_cast']], ['June 1'])
        self.assertEqual([r['artist_name'] for r in two['principal_cast']], ['June 2'])
        self.assertEqual(one['conductors'][0]['artist_name'], 'Conductor 1')

    def test_famous_or_first_unknown_role_is_not_a_principal(self):
        result = build_summary({'event_type': 'opera'}, PROG, [credit('Famous person', character='Unknown', char_id='not-reviewed')], [])
        self.assertEqual(result['principal_cast'], [])
        self.assertEqual(result['cast_status'], 'unclassified')

    def test_wrong_work_and_adaptation_cannot_reuse_a_principal_rule(self):
        for kind, programme, work in [('opera', [], ARABELLA_WORK), ('ballet', PROG, ARABELLA_WORK), ('opera', PROG, 'other-work')]:
            with self.subTest(kind=kind, programme=programme, work=work):
                result = build_summary({'event_type': kind}, programme, [credit('Name', character='Arabella', work=work)], [])
                self.assertEqual(result['principal_cast'], [])

    def test_director_and_assistant_are_never_principal_or_conductor(self):
        result = build_summary({'event_type': 'opera'}, PROG, [credit('Director', 'stage_director', character='Arabella'), credit('Assistant', 'assistant conductor')], [])
        self.assertEqual(result['conductors'], [])
        self.assertEqual(result['principal_cast'], [])

    def test_singers_are_soloists_in_concert_not_opera_cast_by_voice(self):
        credits = [credit('Singer', 'soloist'), credit('Orchestra', 'orchestra'), credit('Chorus', 'chorus')]
        result = build_summary({'event_type': 'concert'}, [], credits, [])
        self.assertEqual([r['artist_name'] for r in result['soloists']], ['Singer'])
        result = build_summary({'event_type': 'opera'}, [], credits, [])
        self.assertEqual(result['principal_cast'], [])
        self.assertEqual(result['soloists'], [])

    def test_plain_instrument_labels_do_not_imply_soloist_billing(self):
        result = build_summary({'event_type': 'concert'}, [], [credit('Orchestra player', 'oboe')], [])
        self.assertEqual(result['soloists'], [])

    def test_same_artist_two_roles_preserves_both_role_relationships(self):
        chars = list(REVIEWED_PRINCIPAL_ROLES[ARABELLA_WORK]['characters'])
        result = build_summary({'event_type': 'opera'}, PROG, [credit('Same Artist', character='One', char_id=chars[0]), credit('Same Artist', character='Two', char_id=chars[1])], [])
        self.assertEqual(len(result['principal_cast']), 2)

    def test_partial_programme_is_not_invented_from_title(self):
        event = {'event_id': 'wiener_konzerthaus:pdf:53779919bb8487728696ebec', 'title': 'Symphonien Nr. 1, 2 & 3', 'event_type': 'concert'}
        result = build_summary(event, [], [], [{'title': 'Symphony No. 3'}])
        self.assertEqual(result['programme_status'], 'partial')
        self.assertEqual(len(result['programme']), 1)
        self.assertEqual(build_summary({'event_type': 'concert'}, [], [], [])['programme_status'], 'unknown')

class SummaryReadContractTests(unittest.TestCase):
    @patch('api.index._schedule_summary_relations')
    @patch('api.index._schedule_events_payload')
    @patch('api.index._schedule_owned', side_effect=PermissionError('not owner'))
    @patch('api.index.authenticated_user', return_value={'id': 'signed-in-user'})
    def test_no_cross_user_metadata_reads(self, auth, owned, events, relations):
        with self.assertRaises(PermissionError): api.get_schedule_summary({}, 'someone-elses-schedule')
        events.assert_not_called(); relations.assert_not_called()
        owned.assert_called_once_with('signed-in-user', 'someone-elses-schedule')

    @patch('api.index._cached_supabase_get')
    def test_server_cap_smaller_than_requested_limit_is_fully_read(self, get):
        get.side_effect = [[{'id': 'one'}], [{'id': 'two'}], []]
        rows = api._schedule_summary_relations('/rest/v1/event_credits', ['owned-event'], 'id', 'id.asc')
        self.assertEqual(len(rows), 2)
        self.assertEqual([c.args[1]['offset'] for c in get.call_args_list], ['0', '1', '2'])
        self.assertTrue(all(c.args[1]['event_id'] == 'in.(owned-event)' for c in get.call_args_list))

    @patch('api.index._cached_supabase_get', return_value=[])
    def test_batches_remain_scoped_with_no_global_scan(self, get):
        api._schedule_summary_relations('/rest/v1/event_programme', [str(i) for i in range(201)], 'id', 'id.asc')
        self.assertEqual(get.call_count, 3)
        self.assertTrue(all(len(c.args[1]['event_id'].split(',')) <= 100 for c in get.call_args_list))
        get.reset_mock();self.assertEqual(api._schedule_summary_relations('/rest/v1/event_programme', [], 'id', 'id.asc'), [])
        get.assert_not_called()

    @patch('api.index._schedule_summary_relations')
    @patch('api.index._schedule_events_payload')
    @patch('api.index._schedule_owned', return_value={'id': 'schedule'})
    @patch('api.index.authenticated_user', return_value={'id': 'owner'})
    def test_summaries_are_grouped_by_performance_not_production(self, auth, owned, members, relations):
        members.return_value = [{'id': 'entry1', 'event_id': 'day1', 'event': {'event_type': 'opera'}}, {'id': 'entry2', 'event_id': 'day2', 'event': {'event_type': 'opera'}}]
        relations.side_effect = [[], [{'event_id': 'day1', **credit('First', 'conductor')}, {'event_id': 'day2', **credit('Second', 'conductor')}]]
        response = api.get_schedule_summary({}, 'schedule')
        self.assertEqual([r['event']['summary']['conductors'][0]['artist_name'] for r in response['events']], ['First', 'Second'])
        self.assertEqual([r['id'] for r in response['events']], ['entry1','entry2'])

if __name__ == '__main__': unittest.main()
