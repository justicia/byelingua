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

if __name__=='__main__':unittest.main()
