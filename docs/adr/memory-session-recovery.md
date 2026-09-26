# Memory termination and recovery policy (#67)

Status: **Proposed**, 2026-09-27; founder decision required before trial release.
This specifies future #11/#19 behavior. It does not implement or unblock them.

## Decision supported by measurements

Do not promise session survival at the sandbox memory boundary. A per-process
RLIMIT_AS can preserve the sandbox for a controlled allocator, but is not an
aggregate memory quota, and 96 MiB is incompatible with the measured Node startup.
runsc RLIMIT_DATA did not stop this allocation path before host OOM. Four separately
AS-limited allocators still OOM the whole runsc sandbox. These results justify a
recovery contract instead of continuing until every exhaustion scenario survives.

Evidence: `docs/research/gvisor-m0-memory-results-20260927.md`. Historical E08
remains a resource-enforcement pass; this ADR does not relabel it as session survival.

## 1. Detection

Persist container ID/generation, runtime, timestamp and cgroup memory-event baseline
before starting work. Observe task-exit/OOM events and reconcile Docker State with
the same generation. Classify `memory_limit_terminated` only when the container is
actually stopped, exit 137 and OOMKilled=true; correlate oom_kill delta/kernel or
runtime event if available. Exit 137 alone is not sufficient. Counter loss is
explicitly recorded, never silently treated as zero. Running+OOMKilled=true can
mean an individual child was killed (observed in runc); do not restart that live
sandbox solely because of the flag. Unknown deaths stay unknown and raise an incident.

Keep PID failure separate: stopped/exit 2/non-OOM with matching clone-panic log.
Freeze further exec and preserve attribution before any restart. Capacity is
released only after confirming the old instance stopped/fenced (#19), not because
a client connection failed.

## 2. Notification

Emit a durable control-plane event with reason, generation and recovery state.
Show: 「沙盒因記憶體上限被終止。執行中的工作與終端 session 已中斷；已落盤的指定檔案仍保留，請檢查後重新啟動。」
Only after a verified healthy restart, update to 「沙盒已重新啟動，原本的程序與
tmux session 不會自動復原。」 Failed restart must remain visibly failed, never
appear as normal reconnect or silently rerun the task.

## 3. Files

Keep the same owned workspace and approved home volumes across stop/restart;
never destroy them during recovery. Save volume identity in control-plane metadata
before launch. Preserve already committed/fsynced files; do not promise data still
in application buffers, partial writes, atomicity across files or live process
state. This VM test read two pre-pressure fsynced markers after restart. It did
not test power loss, arbitrary database durability or a backup restore.

Do not rely on an OOM-time save hook: the Sentry may already be dead. Applications
need ordinary checkpoints during healthy operation. Protect credentials separately
from approved persisted data; no blanket promise to back up all of home. Key
reprovisioning follows the existing credential lifecycle, not a volume copy.

## 4. Restart and repeated failure

Trial default proposed: explicit user-triggered restart, no automatic workload
replay. Verify old generation is stopped, retain the same volumes, recreate/start
with the same validated resource policy, and require a bounded exec health check
before marking ready. Do not automatically increase quota or invoke a paid model.

Rate-limit restart attempts to one per 60 seconds; three failures within ten
minutes place the sandbox in a visible recovery-blocked state requiring operator
review. These are proposed control-plane values, not implemented behavior or
measured production guarantees. An auto-restart option requires a separate explicit
product decision and must retain fencing, bounded retries and visible notification.

Claude session-ID reconnection is **unverified** until paid E05/E10. Keeping files
does not prove a Claude process resumes. New tmux/session must be created after
restart; the previous tmux was absent in every terminated runsc case.

## Trial decision

Founder must accept the loss of in-flight processes and the four recovery behaviors,
or keep trial release on hold/reconsider isolation. Implementation and end-to-end
acceptance of these behaviors are still required under #11/#19/G01/G05. #8 remains
open; #10/#11 remain blocked by the M0 release decision. This research package does
not send any notification to invitees or start feature work.
