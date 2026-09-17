import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
import test_app
import app,hotel_profile as hotel,knowledge_engine as kb,conversation_state as state,policy_review

class HotelProfileTests(unittest.TestCase):
    setUp=test_app.ConciergeTests.setUp
    tearDown=test_app.ConciergeTests.tearDown
    def save(self,**changes):
        current=hotel.get(app.connection)
        return hotel.save(app.connection,dict(revision=current['revision'],profile={**current['profile'],**changes}),'admin')
    def test_identity_applies_without_restart_and_source_unchanged(self):
        original=(app.ROOT/'knowledge/policies.json').read_bytes()
        self.save(hotel_name='Resort Encanto',assistant_name='Lia',address='Endereço fictício do Encanto')
        result=app.handle_message(dict(message='ola',request_id='profile-greeting-01'))
        self.assertIn('Lia',result['reply']);self.assertIn('Resort Encanto',result['reply'])
        self.assertNotIn('{{',result['reply'])
        self.assertIn('Endereço fictício do Encanto',kb.load_base()[0]['POL-01']['content'])
        self.assertEqual(original,(app.ROOT/'knowledge/policies.json').read_bytes())
    def test_brand_idempotent_and_waha_prefix(self):
        self.save(hotel_name='Hotel Aura Resort',assistant_name='Lia')
        text=state.display_text('Hostess do Hotel Aura')
        self.assertEqual(text,state.display_text(text))
        result=app.handle_message(dict(message='oi',request_id='profile-waha-0001',session_id='waha_5500000000000_c_us'))
        transport=Mock(return_value='fake-id');state.deliver(app.connection,result['request_id'],'waha_5500000000000_c_us',transport)
        self.assertTrue(transport.call_args.args[0]['text'].startswith('Lia do Hotel Aura Resort'))
        self.assertNotIn('Resort Resort',transport.call_args.args[0]['text'])
    def test_conflicting_save_rejected_and_audited(self):
        old=hotel.get(app.connection);self.save(hotel_name='Hotel Teste')
        with self.assertRaises(hotel.Conflict):hotel.save(app.connection,old,'other')
        with app.connection() as db:self.assertEqual(db.execute('SELECT actor,revision FROM hotel_profile_history').fetchone(),('admin',1))
    def test_invalid_profile_rejected(self):
        for change in [dict(primary_color='red;bad'),dict(hotel_name='<script>'),dict(website='javascript:alert(1)'),dict(website='https://secret:password@example.com'),dict(accommodation_count=True),dict(contact_email='invalid')]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.save(**change)
    def test_html_branding_does_not_modify_script(self):
        self.save(hotel_name='Mar & Sol',assistant_name='Lia')
        page=hotel.page('<html><head><title>Hotel Aura</title></head><body><h1>Hotel Aura</h1><script>const name="Hotel Aura";</script></body></html>')
        self.assertIn('<h1>Mar &amp; Sol</h1>',page)
        self.assertIn('const name="Hotel Aura"',page)
    def test_template_excludes_operational_data_and_drafts(self):
        app.handle_message(dict(message='Quero toalhas TESTE_PRIVADO',request_id='template-private-01'))
        policy=app.POLICIES['POL-08'];draft={k:policy[k] for k in policy_review.FIELDS};draft['content']='RASCUNHO_PRIVADO'
        policy_review.change(app.connection,app.POLICIES,dict(id='POL-08',action='save',actor='admin',revision=0,draft=draft))
        exported=hotel.export_template(app.connection,app.POLICIES);raw=json.dumps(exported)
        self.assertNotIn('TESTE_PRIVADO',raw);self.assertNotIn('RASCUNHO_PRIVADO',raw)
        self.assertEqual(len(exported['policies']),101);self.assertNotIn('users',exported)
    def test_import_fresh_only_and_keeps_policies_as_drafts(self):
        package=hotel.export_template(app.connection,app.POLICIES)
        result=hotel.import_new(app.connection,package,'setup')
        self.assertEqual(result['policies_imported'],101);self.assertFalse(result['published'])
        with app.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM policy_reviews WHERE published IS NOT NULL').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM reservations').fetchone()[0],0)
        with self.assertRaises(hotel.Conflict):hotel.import_new(app.connection,package,'setup')
    def test_import_refuses_existing_guest_data(self):
        app.handle_message(dict(message='oi',request_id='template-existing-01'))
        with self.assertRaises(hotel.Conflict):hotel.import_new(app.connection,hotel.export_template(app.connection,app.POLICIES),'setup')
    def test_bad_import_rolls_back(self):
        package=hotel.export_template(app.connection,app.POLICIES)
        package['policies'][-1]['audience']='guest'
        with self.assertRaises(ValueError):hotel.import_new(app.connection,package,'setup')
        self.assertEqual(hotel.get(app.connection)['revision'],0)
        with app.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM policy_reviews').fetchone()[0],0)
    def test_demo_consistency_and_placeholder_resolution(self):
        policies,_=kb.load_base()
        self.assertEqual(set(policies),{f'POL-{i:02}' for i in range(101)})
        self.assertNotIn('{{',json.dumps(policies,ensure_ascii=False))
        for pid in ('POL-08','POL-09','POL-65'):self.assertIn('Brisa',policies[pid]['content'])
        self.assertIn('R$ 15',policies['POL-11']['content']);self.assertIn('room service',policies['POL-65']['content'])

if __name__=='__main__':unittest.main()
