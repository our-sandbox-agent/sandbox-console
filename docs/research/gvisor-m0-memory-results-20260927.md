# #67 memory session survival and recovery evidence

**Conclusion: limited allocator survival is possible, general sandbox session
survival is not established. Propose explicit recovery behavior for trial review.**
AS=96 MiB stops a single allocator with ENOMEM before a 256 MiB host cap. It fails
as an aggregate guarantee and prevents the measured Node startup. DATA=96 MiB does
not protect this runsc allocation path. See [recovery proposal](../adr/memory-session-recovery.md).

## Measured matrix

Same dedicated VM and immutable image as #70/#63. Kernel 6.8.0-142-generic, Docker
29.8.1, runsc release-20260921.0/systrap. All cases: 2 CPU, 256 MiB memory/no swap,
host PID cap 512, non-root UID1000, cap-drop ALL, no-new-privileges. Guest limits
are set in the allocator child, not the Sentry or a container-wide sum. Each child
touches at most 512 MiB in 8 MiB steps. tmux runs a pre-existing heartbeat; a shell
client is already open. Dedicated owned workspace/home volumes contain only tests.

| Runtime / allocator | Guest result | Container after pressure | Session / recovery |
| --- | --- | --- | --- |
| runsc / AS 96 MiB | ENOMEM after 72 MiB | running, no OOM | shell/heartbeat/tmux/new exec survive; child reaped |
| runsc / DATA 96 MiB | reaches 216 MiB; no guest refusal observed | stopped, exit137, OOMKilled | session lost; restart succeeds |
| runsc / unlimited | reaches 184 MiB | stopped, exit137, OOMKilled | session lost; restart succeeds |
| runc / AS 96 MiB | ENOMEM after 80 MiB | running, no OOM | session/recovery survive; child reaped |
| runc / DATA 96 MiB | ENOMEM after 88 MiB | running, no OOM | session/recovery survive; child reaped |
| runc / unlimited | allocator SIGKILL after 240 MiB | still running; OOMKilled flag true | parent reaps -9; session/recovery survive |
| runsc / four AS-limited children | aggregate host exhaustion | stopped, exit137, OOMKilled | session lost; restart succeeds |
| runc / four AS-limited children | one child SIGKILL; other three ENOMEM | still running; OOMKilled flag true | children reaped; session/recovery survive |

Amounts are last successful probe allocations, not total sandbox RSS. In every
host-OOM case, the event watcher records oom_kill increasing to 1. In ENOMEM-only
cases it remains 0. A 1 ms sampler plus POLLPRI/event-file observations addresses
the old E08 missed-counter limitation; both raw streams and kernel/Docker journal
are included. This does not guarantee that every future short-lived cgroup event
will be captured, so recovery policy still handles missing attribution.

All surviving cases return exit 0 and exactly `RECOVERY_EXEC_OK`, advance the
existing heartbeat, respond through the existing shell, retain tmux and reap
allocation children. All three terminated runsc cases fail the pre-restart
recovery check. Manual Docker start then succeeds with `RESTART_EXEC_OK`; tmux
is absent. Both pre-pressure fsynced volume markers are readable after all eight
cases. That verifies these files, not buffered data or automatic recovery.

The AS=96 MiB Node smoke fails in both runtimes: runsc rejects exec with ENOMEM
(wrapper exit1), runc exits139. Thus the low address-space cap cannot be promoted
to a Node/Claude product setting just because a Python allocator survives. The
four-child AS case also disproves treating per-process limits as aggregate memory
protection. No claim is made that all possible AS settings or allocation mechanisms
have been exhausted; the bounded decision is to require the recovery contract.

## Scope and decisions

RLIMIT_DATA behavior here is specific to libc's measured malloc allocation path
and this runtime version; this does not establish that DATA is ignored for every
brk/mmap operation. No swap or ballooning tuning, privileged mount, company data,
host Docker socket or real key is used. No Claude model task is run. Reconnection
by Claude session ID and production notification/fencing remain untested.

#67's acceptable output is now concrete: an AS-limited worker can survive, but a
general-purpose sandbox needs detection, notification, preserved volumes and
bounded restart behavior. These are specified as Proposed in the ADR and trial
disclosure. Founder acceptance and #11/#19 implementation are not assumed. E08's
old resource-enforcement result and evidence remain unchanged; #8 and #10/#11 gates
stay blocked.

## Reproduction and published evidence

```sh
sudo python3 scripts/gvisor-m0-memory.py --image "$IMAGE" --output /private/raw-67-base
sudo python3 scripts/gvisor-m0-memory.py --image "$IMAGE" --modes as-multi --output /private/raw-67-multi
python3 scripts/gvisor-publish-evidence.py --raw /private/raw-67-base --out /private/published-67-base
```

IMAGE is `sha256:1728145d39d1e09111580fcd3a8a4931d0d0ebc0429caeb16ff295c86108e5cf`.
Use fresh paths. Configure temporary runsc debug logs only on the idle authorized
VM and restore the original configuration afterward as in #63. The base six cases
ran before adding the four-child/Node supplemental mode; measured source snapshots
are included as text beside hashes. Final sources preserve the same base behavior.

`evidence/2026-09-27-m0-memory/` has two independently published bundles (112 and 49
text files plus hash manifests), no opaque files or detected credential-pattern
hits. Raw material stays on the VM outside repo. Runtime logs are selected by
container IDs. `memory-policy.json` supersedes the shared harness defaults.

The gvisor-report.py initialization/check workflow is also included as a **scope
guard**: the E01–E10 template remains unexecuted, checker exit2/incomplete and
runtime_go=false. #67 measurements are in the dedicated results/ADR, not relabeled
as a complete #8 run. This deliberately incomplete template is not the verdict on
the eight measured memory cases and does not alter historical E08.

All eight owned containers and sixteen named volumes were removed after ownership
checks; persisted test markers were read before removal. The final host has no
test containers, daemon arguments are restored to systrap-only, versions are
recorded after execution. Memory checks stayed confined to bounded test containers.
