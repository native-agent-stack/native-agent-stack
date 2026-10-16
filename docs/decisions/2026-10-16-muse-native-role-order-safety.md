# Native Muse role qualification and launch refusal

Status: proposed for two-family isolation review; builder and reviewer CLOSED.
Base: `fa6cf1a2360bbd1be810045819f222e4432e12bc`.

This is item 3 of
`direction-cc-20261015T1946Z-north-star-new-wsl-takeover.addendum-24.md`, cited by
name only. The co-op's subsequent CC acceptance, final SAFE-allowlist erratum
and first-receipt disposition are retained by name in the lane coordination
record. They authorize the bounded mechanism and a refusal receipt, not a native
builder/reviewer model smoke. The existing reader qualification remains
controlling; neither sealed fence decision nor the 1.4.9 addendum is edited.

## Decision and measured state

Add one host-side order-safety check to the existing launcher for the two
shell-capable roles, before native startup and again after the model-free probe.
Use the PR-owned [SAFE policy](../../tools/policies/muse_native_safe_loopback.json).
Its initial inventory is empty. Every loopback TCP listener must match a reviewed
SAFE entry with port, process identity, reasoned public purpose and primary-source
reference. No launch option supplies an alternative policy. Unknown, inaccessible,
malformed, ambiguous or changed information refuses the run and produces a derived
decision in the existing descriptor-retained probe artifact.

`tools/muse_order_safety.py` uses Linux listener/process metadata and upstream
`ss`, followed by a payload-free TCP check only for an approved public service.
The complete inventory is classified before contacting any socket. Process
ownership, instance identity and the listener set are checked again before
acceptance. The policy must remain outside the fenced writable paths. An
order-capable, credential-bearing or unqualified service cannot become SAFE by
its process name or by an inference that paper trading is inactive. Gateway,
database and agent-control services have no SAFE entries here.

The first [sanitized canary receipt](../../notes/muse-native-roles-20261016/first-canary.json)
at 2026-10-16T05:09:31Z records 139 loopback TCP listeners and REFUSED for
`muse-wonder-builder` and `muse-wonder-reviewer`. Listener records publish only
port and process name. Zero TCP contacts and zero model requests occurred.
The constructor was instrumented to fail if contacted during refusal capture.
This is a conservative metadata refusal; it does not claim a successful broker
connection or an application-level observation. No service was stopped or changed.

After the coordinator reported an independently handled service change, the
[second sanitized canary](../../notes/muse-native-roles-20261016/second-canary.json)
at 05:17:45Z still recorded 139 listeners and REFUSED. The specifically reported
protected ports were absent, but unreviewed listeners remained. This lane made
zero TCP contacts and zero model requests in that recheck. The first receipt is
retained unchanged; neither observation opens a role lane.

## Qualification boundary

The [preregistration](../../notes/muse-native-roles-20261016/PREREG.md) predates
execution and retains its amendments. Both roles passed the installed 1.4.9
offline startup checks: 38 named checks, echo exit 0, 14 events and one completed
terminal per role. Synthetic filesystem/process controls passed through the same
OS fence. An owned public loopback control established the documented shared
network surface. These observations qualify those controls only. They do not
qualify a real builder edit, a real reviewer judgement or a general hostile-code
network boundary. The first receipt leaves both role lanes CLOSED.

The original flags `--disable-web-tools` and `--contributor-mode off`, native
model/effort argv, retained `1.4.9-R6297.1` hash, read-only sign-in exception,
extension masks, own-clone layout policy and Git metadata protection are unchanged.
The unchanged CC argv builder is reused. Tests use synthetic sign-in files;
no real sign-in contents are read, copied, hashed or published.

The check is a launch-time observation. It does not continuously police another
host process or create a network namespace. An unshared network plus a qualified
Meta allowlist proxy remains a separate PROPOSAL for hosts with protected
listeners. No network proxy, provider/account setting, order tool, broker API,
system unit or general model default is changed. Muse remains advisory TRIAL
and never a gate; any default still requires model-routes FINAL.

## Sources at a pin

- containers/bubblewrap `v0.11.1`, commit
  `124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe`,
  [bwrap.xml:139-160](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bwrap.xml#L139)
  and README, **Sandbox security**. No new bubblewrap flag is introduced; the
  original fence decision cites all retained flags.
- iproute2 `v6.19.0`, matching installed `ss utility, iproute2-6.19.0`,
  [man/man8/ss.8:24,33,43,82,162,374](https://github.com/iproute2/iproute2/blob/v6.19.0/man/man8/ss.8#L24):
  `-H`, `-n`, `-l`, `-e`, `-p`, `-t` select numeric TCP LISTEN metadata, inode and
  process names. No application protocol is invoked.
- Linux `v6.18`, matching the installed WSL kernel's 6.18 family,
  [Documentation/networking/proc_net_tcp.rst:7-46](https://github.com/torvalds/linux/blob/v6.18/Documentation/networking/proc_net_tcp.rst#L7)
  and [Documentation/filesystems/proc.rst](https://github.com/torvalds/linux/blob/v6.18/Documentation/filesystems/proc.rst),
  `/proc/PID/stat`, `comm`, `exe`, `fd` and socket-inode entries. The TCP tables
  remain available but upstream marks them deprecated in favor of `tcp_diag`;
  `ss` supplies the maintained diagnostic/process view alongside the bounded
  table check. No process environment or command line is inspected.
- CPython `v3.13.16`, matching installed Python,
  [Doc/library/socket.rst](https://github.com/python/cpython/blob/v3.13.16/Doc/library/socket.rst),
  `socket`, `settimeout`, `connect_ex`, and
  [Doc/library/os.rst](https://github.com/python/cpython/blob/v3.13.16/Doc/library/os.rst),
  `open`, `fstat`, `readlink`, `O_NOFOLLOW` and `O_CLOEXEC`: existing file/socket
  primitives, with `unittest` as the repository test harness.
- Meta [Muse permissions](https://dev.meta.ai/docs/muse-code/permissions), read
  2026-10-16, and installed Muse `1.4.9-R6297.1` offline controls. Runtime artifact
  provenance remains in `2026-10-15-muse-149-requalification.md`; no vendor script
  byte copies are added here.

The isolation retain verdict, `20260922` wave, latest retained isolation sweep
`landscape-sweep-20260929` and its manifest/returns remain the layer-resolution
inputs. Boxlite and microsandbox remain unresolved survivors. This item fills
the named native-role gap; no layer winner, survivor adjudication or general
default changes. Wider network isolation must follow its own reviewed upstream
mechanism and qualification rather than silently enlarging this claim.

## Verification and overturning evidence

The [qualification receipt](../../notes/muse-native-roles-20261016/qualification.json)
records the named tests, mutation controls and final
validation. Replacing the initial gate with an always-pass result makes the
before-start regression fail for both roles; omitting the second check makes
the newly appearing listener regression fail for both roles. The IPv4-mapped
normalization check failed before its corresponding prototype correction.
No production file is left in a mutant state.

Reopen the role acceptance only when every listener has a justified reviewed
SAFE disposition or a separately qualified stronger network mechanism is
available, and the coordinator releases the preregistered native role smokes.
Two-family reads remain required for this mechanism; no live qualification or
default can be inferred from model-free tests or from an exit code alone.
