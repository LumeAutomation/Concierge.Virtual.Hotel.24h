from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import operations as ops

class OperationsTests(unittest.TestCase):
    def test_backup_consistent_restore_retention_and_no_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';destination=Path(tmp)/'backups';(root/'runtime').mkdir(parents=True)
            (root/'knowledge').mkdir();(root/'knowledge/policies.json').write_text('[{"id":"POL-01"}]')
            (root/'runtime/.env').write_text('SECRET=not-for-backup')
            with closing(sqlite3.connect(root/'runtime/aura.sqlite3')) as db:
                db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE sample(value)');db.execute("INSERT INTO sample VALUES ('saved')");db.commit()
                for _ in range(15):result=ops.backup(root,destination)
            self.assertEqual(len(list(destination.glob('*.zip'))),14)
            manifest=ops.verify_archive(Path(result['file']))
            self.assertEqual(set(manifest['sha256']),{'runtime/aura.sqlite3','knowledge/policies.json'})
            import zipfile
            with zipfile.ZipFile(result['file']) as z:
                restored=Path(tmp)/'restored.sqlite3';restored.write_bytes(z.read('runtime/aura.sqlite3'))
            with closing(sqlite3.connect(restored)) as db:self.assertEqual(db.execute('SELECT value FROM sample').fetchone()[0],'saved')
            self.assertFalse(list(destination.glob('*.partial')))

    def test_missing_database_is_not_reported_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(FileNotFoundError):ops.backup(root,root/'backups')
            self.assertFalse(list((root/'backups').glob('*.zip')))

    def test_snapshot_outage_is_visible_and_contains_no_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'runtime/waha').mkdir(parents=True);(root/'runtime/waha/.env').write_text('WAHA_API_KEY=SECRET_TEST_VALUE')
            with patch.object(ops,'ROOT',root),patch.object(ops,'STATE',root/'missing'),patch.object(ops,'BACKUP_STATE',root/'missing'),patch.object(ops,'get_json',side_effect=OSError()):
                data=ops.snapshot()
            self.assertEqual(data['services']['aura']['status'],'error')
            self.assertEqual(data['services']['whatsapp']['status'],'error')
            self.assertEqual(data['supervisor']['status'],'error')
            self.assertEqual(data['backup']['status'],'error')
            self.assertNotIn('SECRET_TEST_VALUE',json.dumps(data))
