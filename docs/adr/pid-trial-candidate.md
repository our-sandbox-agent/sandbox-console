# PID candidate and trial decision (#70)

Status: **Proposed**, 2026-09-27. No founder approval or runtime go implied.

## Decision proposed

Retain non-root UID 1000, cap-drop ALL, no-new-privileges, one guest UID and equal
soft/hard NPROC as candidate invariants. For the tested 2/4 CPU profiles, start
with host task backstop `H = 2 × N × (C + 1) + 64`, where N is guest NPROC and C
is sandbox CPU quota. This is a conservative tested envelope, not an empirical
law or a production capacity promise. Include the runtime's effective CPU/thread
settings in any future deployment review; fractional CPU/minimum GOMAXPROCS must
not be silently substituted into the formula.

Candidate profiles: N=64 or 128, C=2 or 4, memory=2 GiB, one simultaneous sandbox
on the existing 4-vCPU/8-GiB VM. Admission must also reserve memory and host tasks
for the VM/control plane; eight sequential test cases do not prove multi-sandbox
capacity. Real Claude task capacity remains unmeasured without E05/E10.

**NO-GO for trial release against the current complete #70 acceptance text.**
At a fully consumed per-UID task quota, an existing shell cannot fork a new
external command. Increasing host headroom cannot make that guest fork succeed.
An interactive shell can stay connected and recover after pressure is released;
this is a different guarantee. The issue explicitly asks to verify a forking
command before release, so this requirement must not be marked passed by substituting
a builtin. The measured rejection/recovery behavior can support a candidate only
if the product explicitly accepts temporary inability to start commands at full
quota. That policy decision is still open.

Per #70/#8's reversal condition, re-evaluate microVM isolation before opening a
trial rather than extending gVisor experiments indefinitely. This is a review
trigger, not a decision to implement a different runtime or a claim that microVMs
make a full guest PID quota disappear. Compare failure containment and management
access separately. The previously demonstrated runsc host-clone panic is still
unfixed; the present high-host-cap runs do not supersede that evidence.

#8 stays open. #10/#11 are not authorized to start. #67 and paid E05/E10 retain
their separate gates. The evidence report for this proposal is
`docs/research/gvisor-m0-pid-results-20260927.md`.
