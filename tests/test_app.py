import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app

class ConciergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = app.DB
        app.DB = Path(self.tmp.name) / "test.sqlite3"
        app.init_db()

    def tearDown(self):
        app.DB = self.old_db
        self.tmp.cleanup()

    def send(self, message, request_id="test-0001"):
        return app.handle_message({"message": message, "request_id": request_id})

    def test_whatsapp_retry_and_original_id(self):
        mid = 'wamid.' + 'Ab9+/' * 30 + '=='
        first = self.send('Quero toalhas', mid)
        self.assertEqual(first, self.send('Quero toalhas', mid))
        self.assertEqual(app.list_handoffs()[0]['id'], mid)
        self.assertEqual(len(app.list_handoffs()), 1)
        for invalid in ['wamid.', 'wamid.' + 'a' * 481, 'wamid.<script>']:
            with self.assertRaises(ValueError):
                self.send('Quero toalhas', invalid)

    def test_faq_source(self):
        r = self.send("Qual o horario do cafe da manha?")
        self.assertEqual(r["route"], "AUTO_REPLY")
        self.assertEqual(r["policy_ids"], ["POL-08"])
        self.assertIn("06h30", r["reply"])
        self.assertEqual(app.list_handoffs(), [])

    def test_reservation_not_answered_as_faq(self):
        r = self.send("Quero reservar cafe da manha")
        self.assertEqual(r["route"], "HUMAN_HANDOFF")
        self.assertEqual(len(app.list_handoffs()), 1)

    def test_emergency_precedes_faq_and_sensitive(self):
        r = self.send("Tem fogo na piscina, minha senha e teste")
        self.assertEqual(r["priority"], "urgent")
        self.assertIn("não aciona socorro real", r["reply"])

    def test_unknown_handoff(self):
        self.assertEqual(self.send("Qual a profundidade da piscina?")["route"], "HUMAN_HANDOFF")

    def test_sensitive_not_saved(self):
        self.send("Meu CVV e 123")
        with app.connection() as db:
            self.assertEqual(db.execute("select message from interactions").fetchone()[0], "[conteúdo sensível omitido]")

    def test_concurrent_retry_deduplicated(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.send("Quero toalhas"), range(4)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(len(app.list_handoffs()), 1)
        self.assertEqual(app.list_handoffs()[0]["department"], "governanca")

    def test_reused_id_different_message_rejected(self):
        self.send("Quero toalhas")
        with self.assertRaises(ValueError):
            self.send("Quero cancelar")

    def test_storage_failure_no_confirmation(self):
        with patch("app.sqlite3.connect", side_effect=sqlite3.OperationalError("disk")):
            with self.assertRaises(sqlite3.OperationalError):
                self.send("Quero toalhas")

    def test_invalid_inputs(self):
        for body in [[], {}, {"message": "x", "request_id": "../bad"}, {"message": " "*10, "request_id": "test-0001"}]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                app.handle_message(body)

    def test_status_persists_across_init(self):
        r = self.send("Preciso de atendente")
        with app.connection() as db:
            db.execute("update handoffs set status='in_progress' where id=?", (r["handoff_id"],))
        app.init_db()
        self.assertEqual(app.list_handoffs()[0]["status"], "in_progress")

if __name__ == "__main__":
    unittest.main()

