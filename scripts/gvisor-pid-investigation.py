#!/usr/bin/env python3
"""Six bounded PID cases on a dedicated Linux VM, no credentials or model calls.

Requires the diagnostic image and runsc debug logs configured by the operator.
Reuses resource ownership, command recording and cleanup from the #61 harness.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('matrix', ROOT / 'scripts/gvisor-no-key-matrix.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not args.image.startswith('sha256:'):
        parser.error('requires Linux root and immutable local image ID')
    m = module.Matrix(args)
    m.write('pid-policy.json', {'caps': [64, 128, 256], 'max_forks': 272,
        'hold_seconds': 3, 'case_timeout_seconds': 45, 'sample_seconds': .01,
        'model_requests': 0, 'acceptance': 'EAGAIN, existing shell and work responsive, reap, container alive, host headroom >= 2 GiB'})
    m.write('pid-source.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), ROOT / 'diagnostics/gvisor/probes/pid-pressure.py']})
    started = module.now()
    results = []
    try:
        m.command(['uname', '-a'])
        m.command(['docker', 'version'])
        m.command(['runsc', '--version'])
        m.command(['cat', '/etc/docker/daemon.json'])
        for runtime in ['runsc', 'runc']:
            for cap in [64, 128, 256]:
                m.label = f'{runtime}-{cap}'
                cid = m.create(m.label, pids=str(cap), runtime=runtime)
                cg = m.cgroup(cid)
                m.dock('cp', str(ROOT / 'diagnostics/gvisor/probes/pid-pressure.py'), cid + ':/workspace/pid-pressure.py')
                # This shell exists before pressure. Commands use only shell builtins.
                shell_cmd = m.docker + ['exec', '-i', cid, 'sh']
                shell_path = m.out / (m.label + '-shell.txt')
                with shell_path.open('w') as shell_out:
                    shell = subprocess.Popen(shell_cmd, stdin=subprocess.PIPE, stdout=shell_out, stderr=subprocess.STDOUT, text=True, env=m.env)
                    shell.stdin.write('printf "SHELL_READY\\n"\n')
                    shell.stdin.flush()
                    deadline = time.monotonic() + 5
                    while 'SHELL_READY' not in shell_path.read_text() and time.monotonic() < deadline:
                        time.sleep(.05)
                    if 'SHELL_READY' not in shell_path.read_text():
                        raise RuntimeError('existing shell was not ready')
                    probe_cmd = m.docker + ['exec', cid, 'python3', '/workspace/pid-pressure.py']
                    m.log({'shell_command': shell_cmd, 'probe_command': probe_cmd})
                    probe_path = m.out / (m.label + '-probe.txt')
                    stop = threading.Event()
                    samples = []
                    def sample():
                        while not stop.is_set():
                            samples.append(m.stats(cg))
                            time.sleep(.01)
                    sampler = threading.Thread(target=sample)
                    sampler.start()
                    limit_shell_sent = False
                    guard = None
                    try:
                        with probe_path.open('w') as probe_out:
                            probe = subprocess.Popen(probe_cmd, stdout=probe_out, stderr=subprocess.STDOUT, text=True, env=m.env)
                            deadline = time.monotonic() + 45
                            while probe.poll() is None:
                                if not limit_shell_sent and '"event": "at_limit"' in probe_path.read_text():
                                    try:
                                        shell.stdin.write('printf "SHELL_AT_LIMIT_OK\\n"\n')
                                        shell.stdin.flush()
                                        limit_shell_sent = True
                                    except BrokenPipeError:
                                        pass
                                if module.available_mib() < 2048 or time.monotonic() > deadline:
                                    guard = 'headroom or deadline'
                                    m.dock('stop', '-t', '1', cid, check=False)
                                    probe.kill()
                                    break
                                time.sleep(.02)
                            probe.wait(timeout=5)
                        state = m.inspect(cid, '.State')
                        m.write(m.label + '-inspect.json', m.inspect(cid, '.'))
                        m.dock('logs', cid, check=False)
                        if state['Running']:
                            m.execute(cid, 'sh', '-c', 'printf RECOVERY_EXEC_OK', check=False)
                        try:
                            shell.stdin.write('printf "SHELL_AFTER_OK\\n"\nexit\n')
                            shell.stdin.flush()
                        except BrokenPipeError:
                            pass
                        shell.wait(timeout=5)
                    finally:
                        stop.set()
                        sampler.join()
                        if shell.poll() is None:
                            shell.kill()
                            shell.wait()
                        m.write(m.label + '-samples.json', samples)
                    text = probe_path.read_text()
                    events = []
                    for line in text.splitlines():
                        try:
                            events.append(json.loads(line))
                        except ValueError:
                            pass
                    passed = (probe.returncode == 0 and state['Running'] and guard is None
                        and any(e.get('rejected_eagain') for e in events)
                        and any(e.get('progress') for e in events)
                        and 'SHELL_AT_LIMIT_OK' in shell_path.read_text()
                        and 'SHELL_AFTER_OK' in shell_path.read_text())
                    row = {'runtime': runtime, 'cap': cap, 'passed': passed, 'probe_exit': probe.returncode,
                           'container_state': state, 'guard': guard, 'events': events}
                    results.append(row)
                    m.write('results.json', results)
                # Keep inspectable until the shared ownership-checked cleanup.
                m.dock('stop', '-t', '1', cid, check=False)
        m.label = 'final'
        m.command(['journalctl', '-k', '--since', started, '--no-pager'], check=False)
        m.command(['journalctl', '-u', 'docker', '--since', started, '--no-pager'], check=False)
        m.command(['uname', '-a'])
        m.command(['runsc', '--version'])
    finally:
        m.cleanup()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
