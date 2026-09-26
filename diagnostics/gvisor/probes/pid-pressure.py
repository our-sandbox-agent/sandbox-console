"""Bounded pressure; identical command at every cap. No model/network access."""
import errno
import json
import os
from pathlib import Path
import signal
import time

children = []
failure = None
heartbeat = Path('/workspace/heartbeat')
worker = os.fork()
if worker == 0:
    for tick in range(600):
        heartbeat.write_text(str(tick))
        time.sleep(.1)
    os._exit(0)
children.append(worker)
try:
    for index in range(272):
        try:
            pid = os.fork()
        except OSError as error:
            failure = {'errno': error.errno, 'message': str(error)}
            break
        if pid == 0:
            time.sleep(30)
            os._exit(0)
        children.append(pid)
        print(json.dumps({'event': 'fork', 'children': len(children),
                          'guest_processes': len([p for p in os.listdir('/proc') if p.isdigit()])}), flush=True)
        time.sleep(.01)
    before = heartbeat.read_text() if heartbeat.exists() else None
    print(json.dumps({'event': 'at_limit', 'failure': failure, 'children': len(children),
                      'guest_processes': len([p for p in os.listdir('/proc') if p.isdigit()])}), flush=True)
    time.sleep(3)
    after = heartbeat.read_text() if heartbeat.exists() else None
    print(json.dumps({'event': 'existing_work', 'before': before, 'after': after,
                      'progress': before is not None and before != after}), flush=True)
finally:
    for pid in children:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for pid in children:
        os.waitpid(pid, 0)
print(json.dumps({'event': 'reaped', 'rejected_eagain': failure is not None and failure['errno'] == errno.EAGAIN}), flush=True)
