import unittest
from schedule_summary_data import build_summary

WORK='5f65922a-184b-4485-9562-37d9bd688bd3'
def credit(name,role,character=None):
    return {'artist_id':name,'artists':{'artist_name':name},'role':role,'character':character}
class SharedSummaryConsistencyTests(unittest.TestCase):
    def test_voice_credit_is_visible_without_claiming_solo_billing(self):
        result=build_summary({'event_type':'concert'},[],[credit('Voice','soprano'),credit('Player','oboe'),credit('Choir','chorus')],[])
        self.assertEqual([r['artist_name']for r in result['vocalists']],['Voice'])
        self.assertEqual(result['soloists'],[])
        self.assertEqual(result['principal_cast'],[])

    def test_voice_summary_applies_to_all_venues_and_does_not_flatten_dates(self):
        for venue in ['Vienna','Paris','Amsterdam','New venue']:
            with self.subTest(venue=venue):
                one=build_summary({'event_type':'concert','venue':venue,'date':'2027-03-26'},[],[credit('First','tenor')],[])
                two=build_summary({'event_type':'concert','venue':venue,'date':'2027-03-27'},[],[credit('Second','alto')],[])
                self.assertEqual([r['artist_name']for r in one['vocalists']],['First'])
                self.assertEqual([r['artist_name']for r in two['vocalists']],['Second'])

    def test_opera_voice_does_not_become_a_principal_or_concert_vocalist(self):
        result=build_summary({'event_type':'opera'},[],[credit('Voice','tenor')],[])
        self.assertEqual(result['vocalists'],[])
        self.assertEqual(result['principal_cast'],[])

    def test_explicit_soloist_is_not_repeated_as_vocalist_regardless_of_row_order(self):
        for rows in [[credit('Same','tenor'),credit('Same','soloist')],[credit('Same','soloist'),credit('Same','tenor')]]:
            result=build_summary({'event_type':'concert'},[],rows,[])
            self.assertEqual(len(result['soloists']),1)
            self.assertEqual(result['vocalists'],[])

    def test_selected_macbeth_roles_require_the_performed_work_and_matching_source_label(self):
        roles=['Katerina Lvovna Ismaïlova','Sergueï','Boris Timofeevitch Ismaïlov','Zinovy Borisovitch Ismaïlov','Un officier']
        credits=[credit(str(i),'performer',label)for i,label in enumerate(roles)]
        for venue in ['Paris','Different venue']:
            result=build_summary({'event_type':'opera','venue':venue},[{'works':{'id':WORK}}],credits,[])
            self.assertEqual([r['display_order']for r in result['principal_cast']],[1,2,3,4])
            self.assertTrue(all(r['character_id']is None for r in result['principal_cast']))
        wrong=build_summary({'event_type':'opera'},[{'works':{'id':'different-work'}}],credits,[])
        self.assertEqual(wrong['principal_cast'],[])

class GlobalRecordedOperaVoicesTests(unittest.TestCase):
    def programme(self, **extra):
        return [{'works': {'id': 'any-reviewed-work', 'normalization_status': 'verified', 'work_kind': 'work', **extra}}]

    def test_explicit_voices_are_not_lost_for_unlisted_works_or_other_venues(self):
        for venue in ['Palau', 'Les Arts', 'New venue']:
            for kind, raw in [('opera', 'opera'), ('opera', 'opera_en_concert'), ('operetta', 'zarzuela'), ('other', 'performance')]:
                event = {'event_type': kind, 'raw_event_type': raw, 'venue': venue}
                one = build_summary(event, self.programme(), [credit('First date', 'soprano'), credit('Player', 'piano'), credit('Director', 'director')], [])
                two = build_summary(event, self.programme(), [credit('Next date', 'tenor')], [])
                self.assertEqual([r['artist_name'] for r in one['vocalists']], ['First date'])
                self.assertEqual([r['artist_name'] for r in two['vocalists']], ['Next date'])
                self.assertEqual(one['principal_cast'], [])
                self.assertEqual(one['soloists'], [])

    def test_unresolved_identity_and_nonperformance_types_do_not_get_opera_fallback(self):
        for event, programme in [({'event_type': 'opera'}, self.programme(normalization_status='needs_review')),
                                 ({'event_type': 'opera'}, self.programme(work_kind='programme_component')),
                                 ({'event_type': 'ballet'}, self.programme()),
                                 ({'event_type': 'other', 'raw_event_type': 'workshop'}, self.programme()),
                                 ({'event_type': 'other', 'raw_event_type': 'talk'}, self.programme())]:
            self.assertEqual(build_summary(event, programme, [credit('Voice', 'soprano')], [])['vocalists'], [])

    def test_uncertain_cast_and_instruments_never_become_vocalists(self):
        rows = [credit('Named dramatic role', 'singer', 'Unknown role'), credit('Unspecified performer', 'performer'), credit('Spoken actor', 'actor'), credit('Player', 'flute')]
        result = build_summary({'event_type': 'opera'}, self.programme(), rows, [])
        self.assertEqual(result['vocalists'], [])
        self.assertEqual(result['principal_cast'], [])

    def test_principal_singer_is_not_repeated_as_unassigned_voice(self):
        work = [{'works': {'id': WORK, 'normalization_status': 'verified', 'work_kind': 'work'}}]
        for rows in [[credit('Same singer', 'soprano'), credit('Same singer', 'performer', 'Sergueï')],
                     [credit('Same singer', 'performer', 'Sergueï'), credit('Same singer', 'soprano')]]:
            result = build_summary({'event_type': 'opera'}, work, rows, [])
            self.assertEqual(len(result['principal_cast']), 1)
            self.assertEqual(result['vocalists'], [])


class ReviewedVocalWorkTests(unittest.TestCase):
    WORK = 'b9f4662d-4f24-47d0-8684-39833a840b0e'
    def programme(self, **extra):
        return [{'works': {'id': self.WORK, 'normalization_status': 'verified', 'work_kind': 'work', **extra}}]

    def test_reviewed_vocal_work_uses_each_performances_own_singer(self):
        for venue, name in [('Paris', 'First singer'), ('London', 'Second singer')]:
            result = build_summary({'event_type': 'opera', 'venue': venue}, self.programme(),
                                   [credit(name, 'singer'), credit('Instrumentalist', 'piano'),
                                    credit('Director', 'stage_director')], [])
            self.assertEqual([r['artist_name'] for r in result['vocalists']], [name])
            self.assertEqual(result['principal_cast'], [])
            self.assertEqual(result['soloists'], [])

    def test_reviewed_vocal_status_cannot_override_a_dramatic_character(self):
        result = build_summary({'event_type': 'opera'}, self.programme(),
                               [credit('Legacy uncertain character', 'singer', 'Josephine Baker')], [])
        self.assertEqual(result['vocalists'], [])
        self.assertEqual(result['principal_cast'], [])

    def test_source_instruments_do_not_turn_into_cast_for_reviewed_vocal_work(self):
        from work_cast_policy import credit_for_display
        from api.index import _serialize_event_credit
        instrument = credit('Flutist', 'performer', 'Flûte')
        display = credit_for_display({'event_type': 'opera'}, self.programme(), instrument)
        self.assertEqual(display['role'], 'flute')
        self.assertIsNone(display['character'])
        detail = _serialize_event_credit(instrument, event={'event_type': 'opera'}, programme_rows=self.programme())
        self.assertEqual(detail['role_type'], 'artistic_team')
        result = build_summary({'event_type': 'opera'}, self.programme(), [instrument, credit('Singer', 'singer')], [])
        self.assertEqual(result['cast_status'], 'not_available')
        self.assertEqual([r['artist_name'] for r in result['vocalists']], ['Singer'])
        self.assertEqual(instrument['character'], 'Flûte')
        linked = {**instrument, 'character_id': 'existing-character'}
        self.assertIs(credit_for_display({'event_type': 'opera'}, self.programme(), linked), linked)
        ordinary = [{'works': {'id': 'other-work', 'normalization_status': 'verified', 'work_kind': 'work'}}]
        self.assertIs(credit_for_display({'event_type': 'opera'}, ordinary, instrument), instrument)

    def test_vocal_work_requires_verified_full_work_and_appropriate_presentation(self):
        for event, programme in [({'event_type': 'opera'}, self.programme(normalization_status='needs_review')),
                                 ({'event_type': 'opera'}, self.programme(work_kind='programme_component')),
                                 ({'event_type': 'ballet'}, self.programme()),
                                 ({'event_type': 'talk'}, self.programme()),
                                 ({'event_type': 'other', 'raw_event_type': 'workshop'}, self.programme())]:
            self.assertEqual(build_summary(event, programme, [credit('Singer', 'singer')], [])['vocalists'], [])

class ReviewedFollowupCastTests(unittest.TestCase):
    def test_triptych_selects_each_role_only_from_its_own_work(self):
        work_ids = ['c09bcec5-45c9-5b3d-92d8-19459ff7f90f', '30cfc6c3-d9d9-5f53-b86c-10852a6fe4ba', 'b2e01ab5-56b5-59b8-921a-6a6fd7c29a49']
        progs = [{'works': {'id': wid, 'work_kind': 'work', 'normalization_status': 'verified'}} for wid in work_ids]
        rows = [credit('Tabarro singer', 'performer', 'Michele'), credit('Angelica singer', 'performer', 'Sister Angelica'),
                credit('Schicchi singer', 'performer', 'Lauretta'), credit('Chorus staff', 'performer', 'Chorus Director')]
        result = build_summary({'event_type': 'opera'}, progs, rows, [])
        pairs = {(r['work_id'], r['artist_name']) for r in result['principal_cast']}
        self.assertEqual(pairs, {(work_ids[0], 'Tabarro singer'), (work_ids[1], 'Angelica singer'), (work_ids[2], 'Schicchi singer')})
        self.assertEqual(build_summary({'event_type': 'opera'}, progs[:1], rows[1:3], [])['principal_cast'], [])

    def test_two_cycles_keep_distinct_work_and_performance_cast(self):
        work_ids = ['dd1f7478-d30e-5e24-90f3-bf1107b804a7', '089f35fc-b4f7-4895-8f48-d8d635f4ff86']
        progs = [{'works': {'id': wid, 'work_kind': 'work', 'normalization_status': 'verified'}} for wid in work_ids]
        for mary, ophelia in [('First Mary', 'First Ophelia'), ('Next Mary', 'Next Ophelia')]:
            result = build_summary({'event_type': 'opera'}, progs,
                                   [credit(mary, 'performer', 'Mary, Queen of Scots'), credit(ophelia, 'performer', 'Ophelia')], [])
            self.assertEqual({r['work_id']:r['artist_name'] for r in result['principal_cast']}, dict(zip(work_ids, [mary, ophelia])))


if __name__=='__main__':unittest.main()
