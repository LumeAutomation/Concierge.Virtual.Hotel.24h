import unittest,json
from unittest.mock import Mock
import test_app
import app,operating_mode as mode,policy_review as review,knowledge_engine as kb,hotel_profile,conversation_state as state

class ProductionModeTests(unittest.TestCase):
    setUp=test_app.ConciergeTests.setUp
    tearDown=test_app.ConciergeTests.tearDown
    def switch(self,target='production'):
        return mode.save(app.connection,dict(mode=target,revision=mode.get()['revision']),'admin')
    def ask(self,text,rid='prod-query-0001',session='local-demo'):
        return app.handle_message(dict(message=text,request_id=rid,session_id=session))
    def publish(self,pid='POL-08',text='O café da manhã funciona das 07h às 10h.'):
        current=next(r for r in review.catalog(app.connection,app.POLICIES) if r['id']==pid)
        draft={**current['draft'],'content':text}
        saved=review.change(app.connection,app.POLICIES,dict(id=pid,action='save',revision=current['revision'],draft=draft,actor='admin'))
        review.change(app.connection,app.POLICIES,dict(id=pid,action='approve',revision=saved['revision'],actor='admin'))
        return saved['revision']
    def approve(self,pid,revision):return mode.approve(app.connection,dict(id=pid,published_revision=revision,confirm_real_content=True),'admin')
    def test_fresh_production_has_no_demo_answers(self):
        self.switch();self.assertEqual(kb.load_base()[0],{})
        for i,q in enumerate(['oi','Qual horario do cafe da manha?','e aos domingos?','Qual horario da piscina?']):
            r=self.ask(q,f'prod-empty-{i:04}')
            self.assertEqual(r['route'],'HUMAN_HANDOFF');self.assertEqual(r['sources'],[])
            for forbidden in ('06h30','07h','Hotel Aura','.example','R$'):self.assertNotIn(forbidden,r['reply'])
    def test_publication_alone_not_production_approval(self):
        self.publish();self.switch();self.assertEqual(kb.load_base()[0],{})
    def test_validated_revision_only(self):
        revision=self.publish();self.approve('POL-08',revision);self.switch()
        self.assertEqual(set(kb.load_base()[0]),{'POL-08'})
        self.assertIn('07h',self.ask('Qual horario do cafe da manha?')['reply'])
        self.publish(text='O café da manhã funciona das 08h às 11h.')
        self.assertEqual(kb.load_base()[0],{})
    def test_draft_keeps_previously_validated_publication(self):
        revision=self.publish();self.approve('POL-08',revision);self.switch()
        draft={k:app.POLICIES['POL-08'][k] for k in review.FIELDS};draft['content']='NOVO RASCUNHO'
        review.change(app.connection,app.POLICIES,dict(id='POL-08',action='save',revision=revision,draft=draft,actor='admin'))
        self.assertIn('07h',self.ask('Qual horario do cafe da manha?')['reply'])
    def test_demo_markers_cannot_be_validated(self):
        revision=self.publish(text='Restaurante fictício das 07h às 10h.')
        with self.assertRaises(ValueError):self.approve('POL-08',revision)
    def test_pending_demo_delivery_is_blocked(self):
        sid='waha_5500000000000_c_us';self.ask('Qual horario da piscina?',session=sid)
        self.switch();transport=Mock()
        result=state.deliver(app.connection,'prod-query-0001',sid,transport)
        self.assertEqual(result['delivery_status'],'blocked');transport.assert_not_called()
        self.assertTrue(self.ask('Qual horario da piscina?',session=sid)['suppress_response'])
    def test_identity_neutral_until_validated(self):
        self.switch();profile=hotel_profile.guest_profile()
        self.assertEqual(profile['hotel_name'],'Hotel');self.assertEqual(profile['website'],'')
        with self.assertRaises(mode.Conflict):mode.save(app.connection,dict(mode='production',revision=mode.get()['revision'],confirm_identity=True,identity_revision=0),'admin')
    def test_empty_base_does_not_break_emergency_or_sensitive(self):
        self.switch();self.assertEqual(self.ask('Socorro fogo')['priority'],'urgent')
        self.assertEqual(self.ask('minha senha','prod-sensitive-01')['route'],'SAFE_REPLY')
    def test_mode_is_persisted_and_revision_guarded(self):
        current=mode.get();self.switch();app.init_db();self.assertTrue(mode.production())
        with self.assertRaises(mode.Conflict):mode.save(app.connection,dict(mode='demonstration',revision=current['revision']),'admin')
        self.switch('demonstration');self.assertEqual(len(kb.load_base()[0]),101)
    def test_imported_drafts_never_enter_production(self):
        package=hotel_profile.export_template(app.connection,app.POLICIES);hotel_profile.import_new(app.connection,package,'setup')
        self.switch();self.assertEqual(kb.load_base()[0],{})

    def test_identity_edit_requires_revalidation(self):
        current=hotel_profile.get(app.connection)
        profile={**current['profile'],'hotel_name':'Hotel Real','tagline':'Hospitalidade','address':'Rua Principal, 1','contact_email':'recepcao@hotel.test','website':'https://hotel.test','reception_contact':'Recepção presencial','demo_notice':'Consulte as condições da reserva.'}
        hotel_profile.save(app.connection,dict(revision=0,profile=profile),'admin')
        mode.save(app.connection,dict(mode='production',revision=0,confirm_identity=True,identity_revision=1),'admin')
        self.assertEqual(hotel_profile.guest_profile()['hotel_name'],'Hotel Real')
        hotel_profile.save(app.connection,dict(revision=1,profile={**profile,'hotel_name':'Hotel Novo'}),'admin')
        self.assertEqual(hotel_profile.guest_profile()['hotel_name'],'Hotel')

    def test_production_welcome_requires_approved_policy(self):
        import reservations
        record=reservations.change(app.connection,dict(external_id='PROD-TEST',guest_name='Pessoa Teste',phone='5511000000000',cpf='52998224725',room='101',arrival='2026-10-01',departure='2026-10-03'),'admin')['reservation']
        self.switch();transport=Mock()
        with self.assertRaises(ValueError):reservations.change(app.connection,dict(id=record['id'],version=record['version'],action='welcome'),'admin',transport)
        transport.assert_not_called()
        with app.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM reservation_invitations').fetchone()[0],0)

    def test_policy_change_blocks_pending_production_delivery(self):
        revision=self.publish();self.approve('POL-08',revision);self.switch()
        sid='waha_5500000000000_c_us';self.ask('Qual horario do cafe da manha?',session=sid)
        self.publish(text='O café da manhã funciona das 08h às 11h.')
        transport=Mock();result=state.deliver(app.connection,'prod-query-0001',sid,transport)
        self.assertEqual(result['delivery_status'],'blocked');transport.assert_not_called()

if __name__=='__main__':unittest.main()
