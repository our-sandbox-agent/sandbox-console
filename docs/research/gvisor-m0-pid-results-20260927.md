# #70 remaining PID matrix: decision and evidence

**Decision: candidate configurations measured; NO-GO against the complete current
trial gate.** Forking external commands at fully consumed guest quota fails even
from an existing shell. Rejection and recovery work, but that is a narrower
promise. See [proposed decision](../adr/pid-trial-candidate.md). #8/#10/#11 gates
are unchanged. No paid model or Claude task was executed.

## Final experiment

Eight sequential cases on the existing dedicated 4-vCPU/8-GiB VM. Each case uses
2 GiB memory, equal soft/hard NPROC, UID 1000, dropped capabilities and
no-new-privileges. Runtime/image/kernel remain the recorded #63 versions:
runsc release-20260921.0 / systrap, Docker 29.8.1, kernel 6.8.0-142-generic,
image `sha256:1728145d39d1e09111580fcd3a8a4931d0d0ebc0429caeb16ff295c86108e5cf`.
Versions, actual CPU/memory limits, cgroup observations and time boundaries are
recorded in the published bundle, not inferred from package holds.

| CPU | Guest tasks N | Host cap H | Thread-pressure host peak | Fork-pressure host peak |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 64 | 448 | 49 | 132 |
| 2 | 128 | 832 | 48 | 263 |
| 4 | 64 | 704 | 51 | 141 |
| 4 | 128 | 1344 | 48 | 269 |

Candidate formula is `H = 2 × N × (C + 1) + 64`: allow up to C+1 runtime executor
tasks per guest task, apply a factor of two, then add 64 fixed tasks. This is a
conservative allocation hypothesis supported only for these workloads/profiles,
not a derived exact ratio or a guarantee for all systrap paths. Samples show why
guest threads and forked address spaces cannot be assigned a single observed
host-task multiplier. Do not extrapolate to fractional CPUs or multi-sandbox
admission without accounting for runtime minimum CPU settings and host capacity.

All eight cases first start a tmux session with Node's eight Worker threads and
a continuously updated heartbeat, then complete `npm ci --ignore-scripts` using
the pinned repository lockfile. Guest baseline per-process task counts are saved.
The bounded Python pressure workload then creates threads or forked children
until the guest count reaches exactly N. Thread creation returns Python's
`can't start new thread`; fork returns errno 11/EAGAIN. The Node workers continue
during pressure. This is a mixed Node/npm/tmux workload, not a paid Claude task or
a representative large native build; npm lifecycle scripts are intentionally skipped.

At full quota all 32 concurrent exec attempts (four per case) return code 128
and explicit `try again` output. Host pids.events stays zero in all eight cases.
The pre-existing interactive bash reports fork rejection for `/bin/true`; it
can still run a builtin. After releasing pressure, all eight shells fork again,
all fresh execs return exit 0 and exactly `RECOVERY_EXEC_OK`, tmux remains present,
and the Node heartbeat has advanced while pressure was still held. Children/
threads are joined or reaped. No runtime panic, OOM, or timeout occurred.

Both soft-above-hard and hard-limit increases are rejected. Switching UID to 0
or 1001 fails with EPERM in every case. These test the deployed non-root/capability
policy; they are not a proof covering every user-namespace or kernel attack.

## Literal acceptance gap and decision

The existing-shell **fork at full quota** criterion fails in all eight cases.
It cannot be marked passed based on builtin responsiveness. If the product
accepts temporary refusal to start any task while the UID is full, these are
candidate rejection/recovery profiles; if shell commands must keep launching,
the current single-UID task policy does not provide that guarantee.

The evidence therefore does not release a trial. Per #70, trigger the microVM
route review before opening a trial. Changing isolation alone does not create
space under a full guest task limit, so that review must separately define the
management-session guarantee. The historical host-cap panic remains an independent
failure; reserving more host tasks is not its repair. No further open-ended PID
experiment series is proposed by this report.

## Reproduction and evidence boundary

```sh
sudo python3 scripts/gvisor-m0-pid.py --image "$IMAGE" --output /private/raw-70
python3 scripts/gvisor-publish-evidence.py --raw /private/raw-70 --out /private/published-70
```

Use the immutable image above and a fresh directory. The shared #63 debug-log
setup is enabled only on the idle dedicated VM, then restored. The runner uses
at most 272 allocation attempts, four concurrent exec clients, bounded command
timeouts, 2 GiB/container and sequential cases. It records raw results rather
than computing an automatic runtime go. `m0-policy.json` supersedes the shared
harness's old `policy.json` defaults.

Published bundle: `evidence/2026-09-27-m0-pid/` (262 redacted text files plus hash
manifest). Raw files remain outside the repository on the VM. Runtime logs were
selected by the final run's container IDs. Publisher reported no opaque files
or registered-secret leaks; a separate credential-pattern scan found no matches.
No key was supplied. Source hashes cover the runner, probes and npm fixture.

A preliminary eight-case run used non-interactive bash and attempted heartbeat
reads via Docker cp. Non-interactive bash exited after failed fork, and cp was
not reliable at full quota. Those observations were not used as final session
evidence. The final run uses interactive bash and has the already-running probe
read the heartbeat before releasing any resources. The preliminary raw logs are
retained privately. No runtime configuration was changed between those runs.

All eight final containers were removed after checking ownership labels. The
original systrap-only daemon configuration was restored. `host-after.json`
records an empty container list and post-run versions. Existing #61–#63 bundles
were not altered.
