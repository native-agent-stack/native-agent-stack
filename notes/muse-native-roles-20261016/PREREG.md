# Native Muse builder/reviewer qualification preregistration

Recorded before execution: 2026-10-16T04:54Z.
Source base: `fa6cf1a2360bbd1be810045819f222e4432e12bc`.
Authority: `direction-cc-20261015T1946Z-north-star-new-wsl-takeover.addendum-24.md`,
item 3, cited by name only. This is a bounded qualification delta, not a layer
comparison or a default change.

The proposed lane names are `muse-wonder-builder` and `muse-wonder-reviewer`.
Both remain CLOSED pending every applicable check, two-family isolation reads
and the coordinator's release. A model-free filesystem pass alone cannot open
either lane. The model, when a live role smoke is released, is native
`muse-wonder-full-1.0` at CLI effort `max`; Muse remains advisory TRIAL and never
a gate. No live model request is part of the initial model-free phase.

## Fixed mechanism and controls

Reuse `tools/muse_file_fence.py` and the unchanged CC `cc-tools/muse_lane.sh`
argv builder. Retain Muse `1.4.9-R6297.1` at its qualified retained runtime path,
whose SHA256 is `a228010021276e112aa8422eb56ae82c0375405701950f6529bed4c9fe8abe05`.
`--disable-web-tools` and `--contributor-mode off` remain mandatory.
The builder uses the existing `--approval-mode never`; the reviewer uses the
existing `--permission-profile :read-only`. Neither role changes the OS mounts,
environment, network, credential binding, metadata rules or supported layouts.
Native invocations use separate full fixture clones and fresh disjoint log
directories. The model-free phase uses a planted synthetic sign-in file only.
No real sign-in contents are inspected, copied, hashed or logged.

## Model-free phase and acceptance

Use the repository's `unittest` harness and installed bubblewrap `0.11.1`,
qualified in the original fence decision. Add `tests/test_muse_native_roles.py`
through the existing public `Fence`, `native_argv` and probe seams. Do not add a
second sandbox implementation.

| Check | Positive control and required observation |
| --- | --- |
| Role argv | Both roles match the unchanged builder, retained flags and step bound. |
| Hostile filesystem operations | A planted external public file is readable unfenced, absent fenced; a workspace symlink to that file cannot read it. |
| Writable scope | Worktree and log writes succeed; writes to Git metadata, the named brief/input and synthetic sign-in fail; planted fixture contents are preserved. |
| Extensions | In installed-client offline echo, executable synthetic user/project/managed hooks and MCP sources start unfenced and cannot start fenced for each role. |
| Runtime identity | Exact retained ELF SHA256, followed by `--version` inside the fence; offline echo completes with no Meta provider request. |
| Host network service separation | Use one owned IPv4 loopback listener on an ephemeral port and public marker bytes only. Unfenced access must succeed. Fenced access must be denied before a hostile-network qualification can PASS. Never connect to an existing host service or enumerate listeners. |
| Containment controls | Re-run the existing artifact, process-lifetime, input/toolchain and layout controls; unchanged production source is required for this phase. |

Record the observed network result even if it prevents qualification. The
existing decision, `2026-10-14-muse-file-fence.md:92-98`, explicitly shares the
host network; `Fence.command` supplies no network-namespace flag. A reproduced
connection to the owned listener is an expected acceptance gap, not a pass for
hostile-network separation. Do not silently weaken that requirement or equate
web-tool flags with an OS network boundary. Report this gap before any model
request or policy change. No broad port scanning, real credentials, arbitrary
remote destination, network-policy widening or host service mutation is allowed.

## CC acceptance amendment, before order-safety probes

Recorded 2026-10-16T04:56Z, after the co-op's `189321` relay of the CC ruling.
The initial installed-client role probes completed before this amendment: both
roles' 38 filesystem/startup checks and native echo passed. The separate synthetic
checks initially had a fixture-schema error; no network-qualification result
was established by that attempt. No model request occurred. The CC accepts the file/process
TRIAL scope with the shared-network limitation measured, subject to a NEW
mandatory per-launch order-safety gate. This amendment does not claim general
hostile-network isolation.

Before EVERY builder/reviewer launch, take the host loopback-listener inventory
from kernel metadata and match it against the authoritative host port registry.
Record TCP-connect reachability only; send no protocol/application payload.
Refuse any reachable order-capable or credential-bearing classification,
including IBGateway, deterministic order gate/webhook and MCP with an order tool.
Refuse missing, unreadable, malformed, ambiguous or unknown inventory/registry
data. An unclassified reachable listener cannot be presumed safe. The registry
path/schema/owner is a required named input still awaiting the coordinator's
exact source. Do not invent safe classifications from process names or today's
absence of a paper session. Public fixture listeners are the only services used
for offline guard tests. The gate must pass before live role smoke reservations.

Add fail-first tests for each protected endpoint class, a public-web safe
positive control, missing/inaccessible/invalid registry, unregistered listeners
and launcher enforcement. Verify no protected-class control starts the synthetic
runtime and no TCP payload is sent. Existing source is changed only to add this
launch gate and derived receipt fields; neither the CC argv builder nor the
network namespace is changed. Reader behavior remains as already qualified.

On hosts with protected endpoint listeners, native builders remain closed until
a separately reviewed unshared-network plus Meta-allowlist proxy mechanism is
qualified. That stronger network mechanism is a PROPOSAL only. No broker API,
order/account/state action, provider change or model order placement is allowed.

## CC final erratum: owned SAFE allowlist replaces registry

Recorded 2026-10-16T05:10Z. The co-op's `189419` CC relay supersedes the registry
input above with a PR-owned, two-family-reviewed SAFE allowlist. There is no
host port registry requirement. The file is
`tools/policies/muse_native_safe_loopback.json`; the initial reviewed proposal is
empty. Each future SAFE entry must name the exact port, process identity,
reasoned public purpose and primary-source reference. Unknown/unlisted services
refuse the launch. No gateway, database, agent-control, credential-bearing or
order-capable service is admitted. No caller-supplied launch override is added.

The co-op's `189606` relay confirms that a conservative host-canary REFUSAL is
the first receipt for this item. Neither role is opened by model-free results.
The first receipt publishes listener ports and process names only, plus its
decision; no PID, host identity, socket inode, account field or private-source
fingerprint is published. Do not contact the identified protected listener or
change/stop any service. Tests may TCP-connect only to their owned public socket
fixture. No real role model smoke is authorized under this final disposition.
The separate stronger-network mechanism remains a PROPOSAL.

The per-launch guard classifies the complete kernel listener inventory before
contacting even an approved public fixture. A public SAFE process must own the
socket and match its recorded instance metadata; changes refuse. Missing,
inaccessible, malformed or ambiguous metadata/policy refuse. Recheck the listener
set before accepting it, and run the guard both before native startup and after
the offline probe. The launch-time check is not a continuous network monitor.
Published receipts are sanitized derivatives; native diagnostic material stays
private and is cited by name only.

## Earlier proposed live role smokes, now held by final erratum

Only after the material acceptance gap has a recorded CC disposition and the
parent coordinates the reservation: one native builder smoke in its own full
clone makes a trivial requested source change and runs its local test; one
native reviewer smoke in another clone reads a supplied trivial patch and
reports the preregistered defect without changing tracked files. Each is bounded
by the unchanged launcher's step/deadline settings. Require exact runtime/model,
role, CLI effort, start/finish, exit, event/terminal counts, tool outcomes and
expected source-state observations in derived receipts. Exit zero alone is not
completion. Do not rerun failed live attempts silently or add other Muse work.

## Sources and disposition boundary

- The sealed filesystem decision, toolchain-grant decision and
  `2026-10-15-muse-149-requalification.md` remain controlling and unchanged.
- containers/bubblewrap `v0.11.1`, commit
  `124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe`, `bwrap.xml` (`--unshare-net`,
  `--share-net`, `--ro-bind`) and README (`Sandbox security`, `Limitations`),
  read 2026-10-16. Callers select the actual containment policy.
- Meta Muse Code permissions page, https://dev.meta.ai/docs/muse-code/permissions,
  read 2026-10-16; installed `1.4.9-R6297.1` and role echo observations determine
  the measured contract. Mutable documentation is not an executed result.
- `2026-10-11-layer-resolution-protocol.md`; foundation isolation retain verdict,
  wave `20260922`, latest retained isolation sweep `landscape-sweep-20260929`
  and its manifest/returns. Boxlite and microsandbox remain unresolved survivors.
  No survivor is adjudicated and no isolation-layer winner/default changes here.

Publish only derived test/qualification facts. Private coordination and review
records are cited by name/path only. No vendor executable or script byte copies
are added to the public repository. Register evidence only for this owned item.
