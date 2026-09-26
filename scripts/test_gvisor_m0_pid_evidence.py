import hashlib
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]/'docs/research/evidence/2026-09-27-m0-pid'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

class RemainingPidEvidenceTests(unittest.TestCase):
    def test_integrity(self):
        hashes = read(BASE/'bundle-sha256.json')
        self.assertEqual(set(hashes),{p.relative_to(BASE).as_posix() for p in BASE.rglob('*') if p.is_file() and p.name!='bundle-sha256.json'})
        for path,digest in hashes.items():
            self.assertEqual(hashlib.sha256((BASE/path).read_bytes()).hexdigest(),digest,path)

    def test_matrix_rejection_recovery_and_explicit_full_shell_failure(self):
        rows = read(BASE/'results.json')
        self.assertEqual({(r['cpu'],r['guest'],r['kind']) for r in rows},
                         {(c,n,k) for c in [2,4] for n in [64,128] for k in ['threads','fork']})
        for row in rows:
            with self.subTest(cpu=row['cpu'],guest=row['guest'],kind=row['kind']):
                self.assertNotIn('error',row)
                name=f"cpu{row['cpu']}-n{row['guest']}-{row['kind']}"
                events=[json.loads(line) for line in (BASE/(name+'-probe.txt')).read_text().splitlines()]
                limit=next(e for e in events if e['event']=='at_limit')
                self.assertEqual(limit['tasks'],row['guest'])
                self.assertIsNotNone(limit['failure'])
                negative=next(e for e in events if e['event']=='negative')['results']
                self.assertTrue(all(isinstance(v,dict) for v in negative.values()))
                self.assertEqual(negative['uid_root']['errno'],1)
                self.assertEqual(negative['uid_other']['errno'],1)
                before=next(e['value'] for e in events if e['event']=='heartbeat_before')
                after=next(e['value'] for e in events if e['event']=='heartbeat_full')
                self.assertGreater(int(after),int(before))
                self.assertEqual(row['npm_exit'],0)
                self.assertEqual(row['probe_exit'],0)
                self.assertEqual(row['tmux_after'],0)
                self.assertEqual(row['recovery']['exit'],0)
                self.assertEqual(row['recovery']['stdout'],'RECOVERY_EXEC_OK')
                self.assertEqual(len(row['full_exec']),4)
                for result in row['full_exec']:
                    self.assertNotEqual(result['exit'],0)
                    self.assertIn('try again',result['stdout']+result['stderr'])
                shell=(BASE/(name+'-shell.txt')).read_text()
                self.assertIn('SHELL_FORK_BEFORE=0',shell)
                self.assertIn('SHELL_FORK_AFTER=0',shell)
                self.assertIn('fork: Resource temporarily unavailable',shell)
                self.assertNotIn('SHELL_FORK_FULL=0',shell)
                samples=read(BASE/(name+'-samples.json'))
                self.assertEqual({s['pids.events'] for s in samples},{'max 0'})
