# #8 PID cap failure investigation

Status: **E09 remains FAIL; runtime go is blocked.** No paid model calls, credentials,
version changes, or route changes. This package is stacked on PR #61; that baseline
is unchanged. Evidence is in `evidence/2026-09-27-pid/`.

## Result

Same immutable image, `python3 /workspace/pid-pressure.py`, non-root UID 1000,
1 CPU, 1 GiB RAM, no swap, cap-drop ALL and no-new-privileges in all six cases.
The probe attempts at most 272 forks, stops on rejection, holds pressure for three
seconds, observes an existing worker and shell, then reaps its children.

| Runtime | PID cap | Last guest process count | Host pids.current peak | pids.events max delta | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| runsc | 64 | 19 | 63 | 1 | runtime panic, shell lost |
| runsc | 128 | 51 | 128 | 1 | runtime panic, shell lost |
| runsc | 256 | 115 | 256 | 1 | runtime panic, shell lost |
| runc | 64 | 64 | 64 | 1 | EAGAIN, existing shell/work survive, children reaped |
| runc | 128 | 128 | 128 | 1 | EAGAIN, existing shell/work survive, children reaped |
| runc | 256 | 256 | 256 | 1 | EAGAIN, existing shell/work survive, children reaped |

Guest counts are observations printed after each successful fork, not a claim that
the final failing fork completed. Host samples are every 10 ms; the 64 peak was
missed by one task, but pids.events and the kernel both record rejection. Host
cgroup tasks include threads and runtime overhead, unlike guest process counts;
these values must not be interpreted as a fixed sizing multiplier.

## Exit cause and evidence

All three runsc full `*-inspect.json` snapshots show container exit **2**, with
`OOMKilled=false`. Probe clients exit **128**, and the pre-existing shell reports
WaitPID EOF. PID 1 was `sleep infinity`; there was no requested guest shutdown.

The boot logs show:

- 64: `panic: Unknown syscall 56 error: createSysmsgThread: failed to get clone`
- 128 and 256: `panic: Unknown syscall 56 error: createStub: failed to get clone`
- 128 also reports `unable to create a stub process` and `resource temporarily unavailable`.

Each container ID has a matching `cgroup: fork rejected by pids controller` entry
in the kernel log. Together with pids.events increasing from 0 to 1, this supports
the cause: **the host PID controller rejects a runtime clone, and this runsc
systrap version panics instead of containing the failure in the guest.** The
guest has substantially fewer processes than the host task cap at failure.
This is not a conclusion about every gVisor version/platform or about all workloads.

There is a Docker state observation race in the raw `results.json` for runsc 256:
the first State query still says running/exit 0, while the immediately subsequent
full inspect records exited/2. The recovery exec also reports not running. Use the
full inspect plus boot panic and Docker task-delete event for the settled outcome;
do not interpret the early exit 0 as success. Raw evidence is preserved unchanged.

All six cases left at least **6604 MiB** host available memory. No timeout or
headroom guard fired; subsequent runc cases succeeded, Docker remained usable,
and the kernel log contains no host panic or OOM event during this run. This is
bounded host-stability evidence, not a long-duration soak test.

## Acceptance and next decision

A passing case must reach its configured cap, receive EAGAIN for a new process,
keep the pre-existing shell responsive using builtins, keep an existing worker's
heartbeat advancing, reap children, and accept a new exec after pressure releases.
Increasing the cap alone does not pass. All three runc cases meet this condition;
none of the runsc cases does.

Keep #8 open and #10/#11 waiting. Next, check whether a supported runsc configuration
or version handles host clone rejection, and rerun this exact pressure matrix at
the boundary. If introducing a separate guest process limit plus host runtime
headroom, verify both limits and failure paths; merely allocating more host PIDs
does not solve the demonstrated failure. A technical-route decision needs that
follow-up evidence. runc is only a control here, not an approved isolation replacement.

## Reproduction and provenance

- Ubuntu 24.04.5; kernel 6.8.0-142-generic; Docker 29.8.1; runsc release-20260921.0.
- Image `sha256:1728145d39d1e09111580fcd3a8a4931d0d0ebc0429caeb16ff295c86108e5cf`.
- Node v22.23.3, Claude 2.1.283, tmux 3.3a from the unchanged #61 image.
- Dedicated VM, systemd cgroup v2, systrap; runtime logging enabled for this matrix.

On the idle dedicated VM, save `/etc/docker/daemon.json`, create an empty root-owned
log directory, and append `--debug` and `--debug-log=/var/log/runsc-pid/` to the
existing runsc runtimeArgs while retaining `--platform=systrap`. Validate the JSON
and restart Docker. This changes logging, so the exact failure threshold may differ
from #61. It reproduced the same exit failure at 64 and extended it to 128/256.

```sh
sudo python3 scripts/gvisor-pid-investigation.py \
  --image sha256:1728145d39d1e09111580fcd3a8a4931d0d0ebc0429caeb16ff295c86108e5cf \
  --output /home/spike/pid-evidence-01
```

Use a fresh output and log directory on each rerun. Preserve runtime logs before
restoring the saved daemon configuration and restarting Docker. This run restored
the original systrap-only arguments (`daemon-restored.json`). All six owned
containers were removed with label verification (`cleanup.jsonl`, `manifest.json`);
no global prune was used. Images and evidence remain for diagnosis.

`setup.jsonl` records versions and daemon configuration; per-case JSONL records
commands and cgroup path; probe/shell text, samples, full inspect, `final.jsonl`
(kernel and Docker journal), runtime logs, source hashes, and the bundle checksum
preserve the evidence chain. These logs contain only dedicated VM test metadata.
The legacy shared harness `policy.json` describes #61 defaults; **pid-policy.json**
is the policy actually used by this focused runner. No full E01–E10 go claim is made.
