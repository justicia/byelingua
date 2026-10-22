import unittest
from unittest.mock import patch
import api.index as api

OLD = 'wiener_konzerthaus:fca41a07686f5f96449be2f4'
NEW = 'wiener_konzerthaus:pdf:53779919bb8487728696ebec'

class EventKeyResolutionTests(unittest.TestCase):
    def test_only_reviewed_keys_redirect(self):
        self.assertEqual(api.canonical_event_key(OLD), NEW)
        self.assertEqual(api.canonical_event_key('other:unchanged'), 'other:unchanged')
        self.assertFalse(set(api.REVIEWED_EVENT_KEY_REDIRECTS) & set(api.REVIEWED_EVENT_KEY_REDIRECTS.values()))

    @patch('api.index._cached_supabase_get')
    def test_empty_selection_does_not_query(self, get):
        self.assertEqual(api.resolve_event_keys([]), {'resolutions': []})
        get.assert_not_called()

    @patch('api.index._cached_supabase_get')
    def test_alias_and_canonical_share_one_scoped_lookup(self, get):
        get.return_value = [{'event_id': NEW, 'title': 'Symphonien Nr. 1, 2 & 3', 'event_type': 'concert'}]
        result = api.resolve_event_keys([OLD, NEW, OLD, 'missing:key'])['resolutions']
        self.assertEqual([r['requested_event_id'] for r in result], [OLD, NEW])
        self.assertTrue(all(r['event']['event_id'] == NEW for r in result))
        params = get.call_args.args[1]
        self.assertEqual(params['limit'], '2')
        self.assertNotIn(OLD, params['event_id'])
        self.assertIn('"missing:key"', params['event_id'])
        self.assertEqual(params['select'], api.EVENT_CATALOG_LIST_SELECT)

    @patch('api.index._cached_supabase_get', return_value=[])
    def test_missing_key_is_not_reported_as_deleted(self, get):
        self.assertEqual(api.resolve_event_keys(['unknown:key']), {'resolutions': []})

    @patch('api.index._cached_supabase_get', return_value=[])
    def test_quotes_and_commas_stay_inside_requested_key(self, get):
        api.resolve_event_keys(['odd:key,with"quote'])
        self.assertIn('"odd:key,with\\"quote"', get.call_args.args[1]['event_id'])

    @patch('api.index._cached_supabase_get')
    def test_input_bounds_before_query(self, get):
        for keys in ['not a list', list(range(201)), ['x' * 513]]:
            with self.assertRaises(ValueError): api.resolve_event_keys(keys)
        get.assert_not_called()

    @patch('api.index.supabase_service', return_value=[{'id': 'kept-internal-id'}])
    def test_old_key_add_and_intent_resolve_to_kept_id(self, service):
        self.assertEqual(api._event_internal_id(OLD), 'kept-internal-id')
        self.assertEqual(service.call_args.kwargs['params']['event_key'], 'eq.' + NEW)

    @patch('api.index.supabase_service', return_value=[])
    @patch('api.index._cached_supabase_get')
    def test_old_detail_link_reads_the_kept_event(self, get, service):
        get.return_value = [{'event_id': NEW, 'title': 'Symphonien Nr. 1, 2 & 3', 'event_type': 'concert'}]
        result = api.schedule_event_detail(OLD)
        self.assertEqual(result['event']['event_id'], NEW)
        self.assertEqual(get.call_args.args[1]['event_id'], 'eq.' + NEW)
        self.assertEqual(service.call_args.kwargs['params']['event_key'], 'eq.' + NEW)

if __name__ == '__main__': unittest.main()
