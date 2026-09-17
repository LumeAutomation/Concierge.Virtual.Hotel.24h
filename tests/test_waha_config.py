import json
import tempfile
import unittest
from pathlib import Path
from waha_config import session_name


class WahaConfigTests(unittest.TestCase):
    def test_default_and_named_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(session_name(root),'default')
            (root/'runtime/waha').mkdir(parents=True)
            path=root/'runtime/waha/session.json'
            path.write_text(json.dumps({'name':'Lume'}))
            self.assertEqual(session_name(root),'Lume')
            path.write_text(json.dumps({'name':''}))
            with self.assertRaises(ValueError):session_name(root)
