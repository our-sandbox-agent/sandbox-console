# #8 Guest process limit and host PID headroom

**Partial mitigation demonstrated; E09 remains blocked.** Non-root guest
RLIMIT_NPROC can reject forks while the sandbox stays usable. Reaching the host
PID cap still crashes this runsc version. Neither result authorizes #10/#11.

## Measured results

Same diagnostic image and probe as #62, with an added limit/readback check.
Node v22.23.3 / Claude 2.1.283 / tmux 3.3a; no API calls or credentials.
Ubuntu kernel 6.8.0-142-generic, Docker 29.8.1, runsc release-20260921.0, systrap.
Each case has 1 CPU, 1 GiB memory, no swap, UID 1000, cap-drop ALL and
no-new-privileges. No company files or Docker socket are mounted into containers.

| Guest soft/hard NPROC | Host pids.max | Peak host tasks | Host pids.events | Outcome |
| ---: | ---: | ---: | ---: | --- |
| 32/32 | 128 | 92 | 0 | guest EAGAIN at 32 processes; shell/work/recovery pass |
| 64/64 | 256 | 155 | 0 | guest EAGAIN at 64 processes; shell/work/recovery pass |
| unlimited | 128 | 128 | +1 | runsc panic; container exit 2, not OOM |
| unlimited | 256 | 256 | +1 | runsc panic; container exit 2, not OOM |

For guest-limited cases, the probe reads back both limits and attempts to raise
the hard limit. Raising it is rejected. An already-running shell executes builtins
while the children are held, an existing worker's heartbeat advances, and all
children are reaped. A fresh recovery exec must return exit 0 and exactly
`RECOVERY_EXEC_OK`; both cases meet the corrected #62 acceptance condition.
Host rejection counters remain zero, distinguishing guest rejection from host
exhaustion. Limits are applied at container creation via `--ulimit nproc=N:N`,
not by a cooperative application setting its own soft limit.

For host-boundary cases, guest NPROC is unlimited while the same bounded probe
hits host caps 128 and 256. Full inspect, pids.events, kernel logs and boot panic
agree: systrap cannot clone a runtime executor, and the sandbox exits 2. This
separate path demonstrates that reserving more host tasks **has not repaired the
panic**. The larger cap merely changes where it happens.

## Scope and remaining checks

These two headroom settings are measured examples, not a production sizing rule.
The probe uses single-threaded forks under one UID. Thread-heavy workloads,
multiple identities, concurrent execs and longer tasks can require different
headroom. RLIMIT_NPROC is a per-user task limit, not interchangeable with a
sandbox-wide host PID cap. Capabilities and identity policy remain part of the
configuration; this test does not demonstrate resistance to every possible
guest identity or namespace change.

Keep the host hard cap. Next, exercise thread pressure and concurrent exec under
the candidate guest policy, and separately investigate graceful host-clone
failure handling upstream. A guest-limit pass cannot turn the known host panic
into a pass. #8 stays open; #10/#11 and paid Claude tests remain waiting.

## Reproduce and inspect evidence

Use the idle dedicated VM with the #62 debug-log procedure, retaining
`--platform=systrap` and a fresh `/var/log/runsc-guest-pid/` directory. Same image:
`sha256:1728145d39d1e09111580fcd3a8a4931d0d0ebc0429caeb16ff295c86108e5cf`.

```sh
sudo python3 scripts/gvisor-pid-investigation.py --image "$IMAGE" \
  --guest-limit 32 --caps 128 --runtimes runsc --output /home/spike/guest-pid-32
sudo python3 scripts/gvisor-pid-investigation.py --image "$IMAGE" \
  --guest-limit 64 --caps 256 --runtimes runsc --output /home/spike/guest-pid-64
sudo python3 scripts/gvisor-pid-investigation.py --image "$IMAGE" \
  --caps 128 256 --runtimes runsc --output /home/spike/guest-pid-host
```

`evidence/2026-09-27-guest-pid/` contains three run directories plus common runtime
logs and post-run version/configuration observations. Per-run `pid-policy.json`
is authoritative (the shared harness's `policy.json` contains old defaults).
`pid-source.json` and `source-manifest.json` record actual script/probe hashes.
`results.json` now includes recovery exit/stdout/stderr; raw per-case inspect,
10 ms samples, guest/shell output and kernel/Docker journals remain available.
The common log filenames and container IDs correlate each runtime panic.

All four owned containers were removed with label checks. The original
systrap-only daemon configuration was restored and Docker restarted;
`guest-pid-common/containers-after.txt` is empty. Images and evidence remain.
No timeout/headroom guard fired. Evidence hashes cover all published raw files.
This is a new VM runtime experiment, not a reinterpretation of #61/#62 evidence.
