import unittest
from unittest.mock import patch

from api.index import _entity_rows, combined_entity_events, entity_options


class EntityOptionsTests(unittest.TestCase):
    @patch('api.index._cached_supabase_get')
    def test_pages_beyond_database_cap(self, fetch):
        fetch.side_effect = [[{'id': str(i)} for i in range(1000)], [{'id': 'last'}]]
        self.assertEqual(len(_entity_rows('works', 'id')), 1001)
        self.assertEqual(fetch.call_args.args[1]['offset'], '1000')

    @patch('api.index._cached_supabase_get', return_value=[])
    @patch('api.index._entity_rows')
    def test_canonical_composer_alias_and_character_work(self, rows, _fetch):
        tables = {
            'works': [{'id': 'w1', 'title': 'Die Walküre', 'composer': 'R. Wagner'}],
            'composers': [{'id': 'c1', 'canonical_name': 'Richard Wagner'}],
            'composer_aliases': [{'composer_id': 'c1', 'alias': '瓦格纳'}],
            'work_characters': [{'id': 'r1', 'work_id': 'w1', 'canonical_name': 'Wotan'}],
        }
        rows.side_effect = lambda table, *args: tables.get(table, [])
        result = entity_options('瓦格纳')
        self.assertEqual(result['composers'][0]['label'], 'Richard Wagner')
        self.assertEqual(result['composers'][0]['id'], 'c1')
        self.assertEqual(result['works'], [])
        self.assertEqual(entity_options('Wotan')['characters'][0]['work_title'], 'Die Walküre')
        self.assertEqual(entity_options('Wagner')['works'], [])

    @patch('api.index.work_events')
    def test_composer_and_work_intersect(self, events):
        events.side_effect = [{'events': [{'event_id': 'a'}, {'event_id': 'b'}]}, {'events': [{'event_id': 'b'}]}]
        result = combined_entity_events({'composer_id': 'c1', 'work_id': '22222222-2222-4222-8222-222222222222'})
        self.assertEqual([r['event_id'] for r in result['events']], ['b'])
        self.assertNotIn('work_id', events.call_args_list[0].args[0])
        self.assertNotIn('composer_id', events.call_args_list[1].args[0])


if __name__ == '__main__':
    unittest.main()
