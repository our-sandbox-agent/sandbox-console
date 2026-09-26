import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/research/evidence/2026-09-27-m0-memory'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

class MemorySessionEvidenceTests(unittest.TestCase):
    def test_bundle_integrity(self):
        for bundle in BASE.iterdir():
            hashes=read(bundle/'bundle-sha256.json')
            self.assertEqual(set(hashes),{p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file() and p.name!='bundle-sha256.json'})
            for path,digest in hashes.items():
                self.assertEqual(hashlib.sha256((bundle/path).read_bytes()).hexdigest(),digest,path)

    def test_survival_oom_attribution_and_durable_markers(self):
        count=0
        for bundle in BASE.iterdir():
            for row in read(bundle/'results.json'):
                count+=1
                with self.subTest(runtime=row['runtime'],mode=row['mode']):
                    self.assertNotIn('error',row)
                    name=row['runtime']+'-'+row['mode']
                    state=row['inspect']['State']
                    terminated=row['runtime']=='runsc' and row['mode']!='as'
                    oom=row['mode'] in ['none','as-multi'] or (row['runtime']=='runsc' and row['mode']=='data')
                    self.assertEqual(state['Running'],not terminated)
                    self.assertEqual(state['OOMKilled'],oom)
                    counters=[]
                    for sample in read(bundle/(name+'-memory-events.json')):
                        values=dict(line.split() for line in sample.get('events','').splitlines())
                        if 'oom_kill' in values:
                            counters.append(int(values['oom_kill']))
                    self.assertEqual(max(counters),int(oom))
                    self.assertEqual(row['files_after'],'FSYNCED_BEFORE_PRESSURE\n'*2)
                    if terminated:
                        self.assertEqual(state['ExitCode'],137)
                        self.assertNotEqual(row['recovery']['exit'],0)
                        self.assertNotEqual(row['tmux_after'],0)
                        self.assertEqual(row['restart'],{'exit':0,'stdout':'RESTART_EXEC_OK'})
                        self.assertNotEqual(row['restart_tmux'],0)
                    else:
                        self.assertEqual(row['probe']['exit'],0)
                        self.assertIn('child_reaped',row['probe']['stdout'])
                        self.assertGreater(int(row['heartbeat_after']),int(row['heartbeat_before']))
                        self.assertIn('SHELL_AFTER',(bundle/(name+'-shell.txt')).read_text())
                        self.assertEqual(row['recovery']['exit'],0)
                        self.assertEqual(row['recovery']['stdout'],'RECOVERY_EXEC_OK')
                        self.assertEqual(row['tmux_after'],0)
                    if row['mode']=='as-multi':
                        self.assertNotEqual(row['node_as_smoke']['exit'],0)
        self.assertEqual(count,8)

    def test_scope_guard_never_becomes_runtime_go(self):
        spec=importlib.util.spec_from_file_location('report',ROOT/'scripts/gvisor-report.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root=BASE/'published-67-base'
        result,code=module.check(read(root/'matrix-report.json'),root)
        self.assertEqual(code,2)
        self.assertFalse(result['runtime_go'])
