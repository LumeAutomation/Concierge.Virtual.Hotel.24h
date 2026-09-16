import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch
import psutil

spec=importlib.util.spec_from_file_location('aura_supervisor',Path(__file__).resolve().parents[1]/'scripts/supervise.py')
supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)

class SupervisorTests(unittest.TestCase):
    def setUp(self):
        supervisor.children.clear();supervisor.last_attempt.clear()

    def test_existing_starting_process_prevents_duplicate_without_powershell(self):
        process=Mock();process.info={'name':'node.exe'};process.cmdline.return_value=['node.exe',str(supervisor.N8N),'start']
        with patch.object(supervisor,'listening',return_value=False),patch('psutil.process_iter',return_value=[process]),patch('subprocess.Popen') as spawn:
            supervisor.start('n8n',5678,['node.exe',supervisor.N8N,'start'])
            spawn.assert_not_called()

    def test_unknown_process_ownership_does_not_spawn_duplicate(self):
        process=Mock();process.info={'name':'python.exe'};process.cmdline.side_effect=psutil.AccessDenied(123)
        with patch.object(supervisor,'listening',return_value=False),patch('psutil.process_iter',return_value=[process]),patch('subprocess.Popen') as spawn:
            with self.assertRaises(psutil.AccessDenied):supervisor.start('aura',8787,['python.exe','app.py'])
            spawn.assert_not_called()

    def test_recovery_uses_local_directory_and_no_visible_console(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(supervisor.ops,'LOCAL',Path(tmp)),patch.object(supervisor,'listening',return_value=False),patch('psutil.process_iter',return_value=[]),patch('subprocess.Popen') as spawn:
            supervisor.start('aura',8787,['python.exe',supervisor.ROOT/'app.py'])
            self.assertEqual(spawn.call_args.kwargs['cwd'],Path(tmp))
            self.assertEqual(spawn.call_args.kwargs['creationflags'],subprocess.CREATE_NO_WINDOW)

    def test_n8n_limits_preserve_existing_module_settings(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(supervisor.ops,'LOCAL',Path(tmp)),patch.object(supervisor,'listening',return_value=False),patch('psutil.process_iter',return_value=[]),patch('subprocess.Popen') as spawn,patch.dict('os.environ',{'N8N_DISABLED_MODULES':'insights'}):
            supervisor.start('n8n',5678,['node.exe',supervisor.N8N,'start'])
            env=spawn.call_args.kwargs['env']
            self.assertEqual(env['N8N_CONCURRENCY_PRODUCTION_LIMIT'],'1')
            self.assertEqual(env['N8N_RUNNERS_MAX_CONCURRENCY'],'1')
            self.assertEqual(env['DB_SQLITE_POOL_SIZE'],'1')
            self.assertEqual(set(env['N8N_DISABLED_MODULES'].split(',')),{'insights','mcp-registry','community-packages'})

if __name__=='__main__':unittest.main()
