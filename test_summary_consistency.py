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

if __name__=='__main__':unittest.main()
