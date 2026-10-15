# Native Muse Code file-access fence

Status: CC addendum-01 layout narrowing implemented, GPT verdict folded in;
resulting-head CC DELTA and GPT fix5 delta pending.
The single native reader smoke is a dated prior measurement. No default promotion.

Muse Code 1.4.7's own shell sandbox permits filesystem reads outside a workspace,
and its MCP servers and hooks execute outside that sandbox. A reader role alone
does not protect other home files. Put the native process, including startup
configuration and extension discovery, inside bubblewrap before it starts.

The wrapper uses the unchanged CC `muse_lane.sh --dry-run` as its argv builder.
It parses the shell-escaped plan without shell evaluation and compares the whole
array against the accepted contract, refusing drift. It uses the exact installed
`muse-bin-1.4.7-R6101.1` ELF instead of the updating shell shim. Roles, model,
reasoning, workspace, contributor mode and disabled web tools match the native
argv. Runtime version is checked inside the fence. No CC-owned file is edited.

The reference is the co-op's `rankedfeeds_fence.sh`,
`fence_checks_rankedfeeds.sh` and `fence_probe_rankedfeeds.sh` in its
`work-20261012/muse-rankedfeeds-20261014` kit. This keeps its named read-only
binds, private home, writable run area and named model-free checks. Unlike that
Claude/OmniRoute arm, native Muse needs Meta endpoints, so its network namespace
is shared. The new root starts empty rather than binding the host root.

## Mount and configuration policy

- Writable persistent host paths: one dedicated worktree and one fresh log
  directory, both canonical, disjoint children of `/var/tmp`. Existing logs are
  refused. Temporary files, data, sessions, state and cache live in the log tree.
  `/tmp` binds the log tree's `tmp` directory before named input overmounts;
  this supports read-only briefs/inputs under `/tmp` while temporary writes
  persist only in the log tree. Undeclared host `/tmp` files remain absent.
  Git administrative metadata is read-only within the writable worktree. Host
  artifacts have read-only path mounts within the writable log tree; native
  stdout/stderr use the explicitly supplied handles.
- Read-only: `/usr`, merged system executable/library paths, named resolver,
  NSS, identity and timezone files, `/etc/ssl/certs`, the exact runtime ELF,
  the brief and explicitly named input files. Input directories are refused.
  Brief/input files inside the worktree get read-only overmounts.
- Home is a synthetic read-only tree with only the runtime file, projected Muse
  settings and the sign-in file. The original home, other repositories, SSH,
  Codex/Claude/hcom roots, private state, co-op/CC roots, host filesystem sockets and
  Windows mounts are absent. Binding a named brief exposes only that file and
  synthetic ancestors, not its host parent directory.
- A fenced settings copy retains only `schema_version`, the boolean contributor
  disclosure acknowledgement if present, and forced contributor mode off.
  Both `mcpServers` and legacy `mcp_servers`, `hooks`, managed hook/plugin/skill
  paths, plugins and unknown future extension keys are removed. No host settings
  are modified. A private host staging directory supplies the immutable copy;
  its source is outside all visible writable binds.
  When the CLI's default settings file is absent, the copy uses inert defaults.
  An explicitly supplied missing, malformed, symlinked or non-file settings
  path remains an error; existing default files are validated normally.
- Only the specific sign-in file is bound, read-only, at the documented default
  location. The wrapper never opens, hashes, copies or logs its contents. This
  single file remains readable by the native process and its same-UID tools;
  it is an explicit exception, not a claim of same-process secret separation.
  Token refresh that needs a write fails rather than altering the sign-in.
- Project `.muse` is empty and read-only, masking trusted project hooks even
  though the native argv retains `--trust-workspace`. `.mcp.json` is also masked.
  Symlink paths/config mount targets are refused. No user data/plugins or
  enterprise config directories are bound. Missing mountpoints may leave empty
  `.muse`/`.mcp.json` placeholders in the dedicated worktree.
- The root tmpfs is explicitly remounted read-only; the documented operation
  preserves nested writable worktree/log binds. Fresh proc/device filesystems
  provide process discovery and standard devices; these are virtual kernel
  interfaces, not additional writable host directories.

The environment is rebuilt, excluding credentials, proxies, loader injection,
user PATH entries, tracing, fail-open options, inherited XDG paths and arbitrary
Muse overrides. Fresh PID/IPC/UTS namespaces, session isolation and parent-death
cleanup contain child lifetime. A timeout sends TERM then KILL. Mount policy
contains file access; it does not defend against a hostile same-UID host process
racing paths before setup, kernel vulnerabilities, resource exhaustion or files
already deliberately included in the worktree/input set.

The bounded native process is a direct child of the launcher, using
`subprocess.Popen.wait` for its deadline and bubblewrap's documented
`--die-with-parent` handling. The deadline returns124 after TERM and, if needed,
KILL after10seconds. A synthetic lifetime test measures launcher termination;
there is no separate watchdog process. Host artifacts are exclusively opened
before any fenced execution, retained as descriptors and mounted read-only by
path. Host processing uses those retained descriptors and no-follow metadata
queries; source metadata needed for receipts is captured before execution.

## Network and execution boundaries

`--disable-web-tools` and `--contributor-mode off` are mandatory in the matched
native argv. Shared networking permits Meta endpoints, other outbound hosts and
host loopback services. There is no DNS/IP/domain egress allowlist. Credentials
reachable through a separate network service are outside this filesystem-only
claim. No proxy credentials are inherited. The scope is an owner-approved reader
smoke, not a hostile-code network qualification or builder/reviewer qualification.

Every role, including reader, refuses pointer-file Git layouts and symlinked
Git metadata before probe/log creation. Runs use their own clone with ordinary
local `.git` directory metadata kept read-only. The fence contains no Git
pointer-resolution path and makes no parity claim for pointer layouts.
Linked worktrees are therefore outside accepted layouts. This implements
`adjudication-pr1120-5cfb8346-20261015.addendum-01.md`, items1-3.

Hooks/MCP/plugins are absent from immutable startup sources. The native echo
probe demonstrates the planted extension sources do not start. This does not
claim arbitrary builder shell code cannot execute a program implementing MCP;
such a process would still live inside the OS fence. Reader smoke has native
shell and write tools disabled. Worktree contents are still model inputs.

## Acceptance and regression

Every launcher invocation first executes the model-free OS probe and upstream
echo provider, recording `fence-probe.json`; failure prevents a live call.
`--probe-only` stops after this gate. Probe-only drops the Meta model/effort
arguments because the installed echo provider refuses them. Live argv is not
modified. The log contains JSONL/stderr and a derived receipt with exit code,
model ids, event counts and terminal counts. Exit zero alone is not completion.
Raw native event logs remain private; published receipts contain derived facts.

The [acceptance receipt](../../notes/muse-file-fence-20261014/receipt.json)
records 31 passing named probe checks, native echo exit 0 with 14 events, and
the one reserved reader smoke at 22:57:44Z–22:57:58Z: exit 0, 39 events,
`muse-wonder-full-1.0`, one terminal-completed event, the exact assembled expected
reply and no tool results. The main model task and three reminder tasks are
counted separately. No additional live invocation was made; the co-op was
notified immediately on completion to release the route reservation.

`test_unfenced_launcher_canary_read_fenced_denial` runs the actual unchanged CC
launcher with a synthetic runtime: it reads a planted external file. The same
native exec argv inside the OS fence reports that file absent. This requires no
model and is the fail-first positive control. `test_named_masks_and_only_declared_writes`
checks the named masks and writes; it caught missing read-only root sealing.
`test_native_echo_cannot_start_extensions` first proves valid MCP/user/project/
managed hook fixtures execute their marker commands without the fence, then
proves the same markers absent after fenced native startup. Fixture sign-in is
empty synthetic JSON; real sign-in is never copied for tests.

Run the portable tests with `python3 -B -m unittest tests.test_muse_file_fence -v`.
The actual installed-client probes require explicit
`MUSE_FENCE_NATIVE_PROBE=1`; absent that opt-in they skip visibly. OS checks require
bubblewrap. CI synthetic controls are not substituted for native receipts.

Usage (existing worktree/brief, fresh log directory):

```text
python3 tools/muse_file_fence.py --probe-only /var/tmp/muse-work /var/tmp/muse-brief.md /var/tmp/muse-probe
python3 tools/muse_file_fence.py --role reader /var/tmp/muse-work /var/tmp/muse-brief.md /var/tmp/muse-smoke
```

Do not run additional live tasks on the strength of this change. The accepted
scope is exactly one reader-role smoke; adoption and future route reservation
remain separate decisions. Reviews use the GPT family: Astra and local review.

## Sources and alternatives

- [containers/bubblewrap v0.11.1](https://github.com/containers/bubblewrap/tree/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe),
  installed `0.11.1` (Ubuntu `0.11.1-1ubuntu0.3`). Its pinned
  [bwrap.xml](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bwrap.xml)
  documents every wrapper flag: `--ro-bind`, `--bind`, `--symlink`, `--proc`,
  `--dev`, `--unshare-pid`, `--unshare-ipc`, `--unshare-uts`, `--die-with-parent`,
  `--new-session`, `--cap-drop ALL`, `--clearenv`, `--setenv`, `--remount-ro` and
  `--chdir`. `--` ends option parsing. No `--unshare-net` is used. The pinned
  README explains that callers define the effective containment policy.
- Meta [headless execution](https://dev.meta.ai/docs/muse-code/extending#headless),
  [configuration](https://dev.meta.ai/docs/muse-code/configuration#settings-file),
  [hooks](https://dev.meta.ai/docs/muse-code/extending#hooks),
  [MCP](https://dev.meta.ai/docs/muse-code/extending#mcp),
  [permissions and sandbox](https://dev.meta.ai/docs/muse-code/permissions#sandbox),
  [approval modes](https://dev.meta.ai/docs/muse-code/permissions#choose-an-approval-mode),
  and [Muse Wonder](https://dev.meta.ai/models/muse-wonder), read 2026-10-14.
  Installed `1.4.7-R6101.1` help and native echo controls verify the relevant
  surface at the pin. The live docs name `mcp_servers`; the installed built-in
  MCP skill names `mcpServers` and its legacy alias. Both are removed.
- The retained CC install/smoke receipts for `muse-code` establish the motivating
  outside-worktree read and hooks/MCP boundary. They remain private provenance;
  their earlier 1.4.6 smokes do not qualify this 1.4.7 fence.

The layer-resolution protocol was read with the foundation isolation retain
verdict, wave catalog and latest retained isolation sweep
`landscape-sweep-20260929`. Boxlite/microsandbox survivors and earlier retained
failures remain unresolved. This bounded delta fills the explicitly approved
native Muse file-read gap using the named proven reference; it makes no general
isolation winner/default change. A worktree alone cannot enforce the required
reads; reimplementing a sandbox discards upstream namespace enforcement. A full
VM/container or network proxy is a different scope. Replace this wrapper when
native upstream provides equivalent whole-process containment and passes these
same canary/config tests, or a stronger boundary is required and measured.

## Fix round 1: local review at 604d905a

The local review identified three P2 defects, reproduced before changes with
three model-free OS regressions: the mandatory probe deleted an existing marker
file, a `/tmp` brief/input collided with the later `/tmp` symlink, and the
constructor rejected documented read-only worktree input overlays. The review
JSON has SHA256
`0b535fe89713acc0fa26b712a494f4343a85eedce0dea5866cffc71663897aee`.

The probe now uses exclusively created random temporary files and context
cleanup, including its expected-failure write checks. Existing filenames and
contents are preserved. The wrapper binds the writable log `tmp` directory at
`/tmp` before mounting named files read-only; there is no later symlink
collision. Runtime/sign-in files remain disjoint from both writable trees,
while declared inputs may be read-only overmounts inside the worktree. Inputs
inside logs remain refused.

Regression commands and results are retained in
`notes/muse-file-fence-20261014/fix-round-1.json`. Final tests include the native
echo extension controls; no additional live smoke or model call was made.
The original live smoke remains evidence at its recorded source state, not a
claim that another smoke was executed after this correction.

Mechanism sources: bubblewrap `0.11.1` at the pinned `bwrap.xml` above defines
`--bind` and `--ro-bind`, permitting ordered nested mounts. CPython
[`v3.13.16/Lib/tempfile.py`](https://github.com/python/cpython/blob/v3.13.16/Lib/tempfile.py),
`_bin_openflags`, `_mkstemp_inner`, `NamedTemporaryFile`, and `_TemporaryFileCloser`
define exclusive randomized creation and context-managed cleanup. These native
APIs supply the fixes; no custom mount or temporary-file mechanism is added.

## Fix round 2: privacy and input-layout boundaries

The Astra P1 and patched-runner local P2s at `d2c0c9fb` were reproduced with
three fail-before tests before this final bounded fix. The acceptance record
now names private native run artifacts using a task/time custody reference;
it publishes no content-derived commitment to their unpublished bytes.
Historical timestamps, model and event counts remain unchanged. Raw native
events, diagnostics and private receipts remain private. Versioned vendor,
launcher and reference-script source fingerprints are distinct from native
run content and remain in their named source fields.

The CLI now distinguishes an omitted settings option from an explicit path,
using `sanitized_settings(None)` only when the default file is absent. Native
Muse 1.4.7's optional user settings behavior motivated the correction; its
[configuration documentation](https://dev.meta.ai/docs/muse-code/configuration#settings-file)
describes defaults and the flat user settings layer. The regression exercises
the real parser, OS probe and synthetic echo runtime, and confirms explicit
invalid file choices still fail before any live execution.

At the round-2 source state, shell-enabled roles rejected linked Git worktrees
before accepting a native argv. This historical scope is superseded for every
role by the addendum-01 decision above.
Installed Git is `2.53.0`; upstream
[`v2.53.0/Documentation/git-worktree.adoc`](https://github.com/git/git/blob/v2.53.0/Documentation/git-worktree.adoc),
**DETAILS**, and
[`gitrepository-layout.adoc`](https://github.com/git/git/blob/v2.53.0/Documentation/gitrepository-layout.adoc),
**DESCRIPTION**, define the gitfile, private administrative directory and shared
common repository. The regression creates a real linked worktree, proves
unfenced Git works and its common metadata stays inaccessible in the fence,
then requires early rejection of builder/reviewer roles. No common-repository
bind or metadata copy is added. The reader role still permits this file layout.

The [fix receipt](../../notes/muse-file-fence-20261014/fix-round-2.json) records
the findings, fail-before/pass-after results and remaining P3 boundaries.
`test_notes_publish_no_private_run_commitments` covers the notes JSON publication
boundary. The existing general digest guard does not scan this notes directory;
its passing result cannot replace this scoped regression. No digest allowlist
or scanner exemption was added, and no live model call was repeated.

Final whole-tree validation returned rc 1 with only the same nine model-currency
age errors that the supplied Astra review classifies as an exempt CI-wide
incident. No other error was reported. This round does not change those records
or bypass validation; the prior round's rc 0 remains a dated prior result.

## CC ruled extra commit

Authority: `adjudication-pr1120-81008f54-20261015.md:13-23` and
`MICRO-81008f54.md:14-17`. Isolation-class details remain in those reviewed files.
The implemented scope is tracked by source locations and regression names:

| Reviewed item | Implementation | Regression |
| --- | --- | --- |
| `MICRO-81008f54.md:14,16` | `tools/muse_file_fence.py` at `5cfb8346:114`, `:277`, `:372`, `:436` | `test_probe_artifact_custody`, `test_live_artifact_custody` |
| `MICRO-81008f54.md:17` | `tools/muse_file_fence.py` at `5cfb8346:260` | `test_git_metadata_readonly` |
| `MICRO-81008f54.md:15` | `tools/muse_file_fence.py` at `5cfb8346:141` | `test_launcher_exit_stops_run`, `test_bounded_run_timeout_returns_124` |

Four required fail-first tests failed at81008f54 before implementation; the
deadline check is additional coverage. Model-free controls and the PR's own
tests are recorded in `notes/muse-file-fence-20261014/ruled-extra.json`. No new
live model call or smoke is claimed. The original historical receipt remains
unchanged. Follow-ups from `MICRO-81008f54.md:18-20` remain in the PR body.

Sources: openai/codex
[`rust-v0.162.1/codex-rs/protocol/src/permissions.rs:2347-2367`](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/protocol/src/permissions.rs#L2347)
defines the protected Git metadata under writable roots. The existing
bubblewrap pin's `bwrap.xml` defines read-only mounts; its
[`bubblewrap.c:380-388`](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bubblewrap.c#L380)
defines parent-death handling. CPython
[`v3.13.16/Doc/library/os.rst`](https://github.com/python/cpython/blob/v3.13.16/Doc/library/os.rst),
`open`, `fdopen`, `dir_fd`, `follow_symlinks` and the `O_*` flags, and
[`Doc/library/subprocess.rst`](https://github.com/python/cpython/blob/v3.13.16/Doc/library/subprocess.rst),
`Popen`, `wait`, `terminate` and `kill`, define the native interfaces used here.
No custom filesystem or process supervisor is introduced.

## CC upstream-parity completion (historical, superseded by addendum-01)

Authority: `adjudication-pr1120-5cfb8346-20261015.md`, items1-3 and loop stop;
`GPT-VERDICT-5cfb83462.md`, blocker1. Implementation is confined to
`tools/muse_file_fence.py:205` and `:249`, with regression
`test_reader_git_pointer_target_readonly` at
`tests/test_muse_file_fence.py:416`. Finding details remain in the cited sealed
records. This correction completes the already selected upstream policy;
no new runtime, grant, model call or candidate change is introduced.

Primary source: openai/codex `rust-v0.162.1`, commit
`092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`,
`codex-rs/protocol/src/permissions.rs:2360-2367,2573-2629`. These exact pinned
source sections were read. The required regression fails against exact
`5cfb8346` source and passes after this change. Ordinary-directory and shell-role
refusal controls remain green; unresolved-layout and scratch controls are
included in the PR's own fixture style. Results are appended to
`notes/muse-file-fence-20261014/ruled-extra.json` as a separately scoped ruling.

Three GPT P3s are retained in the PR body Follow-ups. CC DELTA and GPT delta are
required before any registry rebase. The sealed loop stop remains controlling;
this record does not authorize another fix round or wider accepted layouts.

## CC addendum-01: loop-stop layout decision

The complete sealed addendum-01 was read and its fingerprint checked before
work. Scope: `adjudication-pr1120-5cfb8346-20261015.addendum-01.md`, items1-4,
and `MICRO-delta-d8afbf04.md`, P2-a. Isolation-class details remain there.
The previous pointer-layout implementation is removed. No pointer file is
read or resolved by the fence. Every role requires its own clone and refuses
these layouts; ordinary directory metadata protection remains unchanged.

`test_reader_git_pointer_refused` replaces the prior accepted-layout test.
It fails against exact `d8afbf04` and passes with this decision. The ordinary
directory, prior shell-role and artifact/lifetime controls remain green.
Model-free tests do not qualify new live use. The full d8afbf04 GPT fix4 ACK
and local review were read after the explicit co-op relay. Their in-scope
disposition is included in this same commit; see
`pr1120-d8afbf04/review_output.json`, finding1/location288-293, and
`test_external_common_metadata_refused_for_every_role`. All accepted roles use
their own clone; ordinary-directory metadata controls remain green.
CC DELTA and GPT fix5 delta at max and fast are
required on the resulting head. After those reads, findings below P1 route
to Follow-ups under the sealed instruction. No rebase before both reads pass
and the CC registry cue.

`MICRO-delta-d8afbf04.md` P3-a/P3-b go to the PR body's Follow-ups. Removal of
pointer layouts is the CC's disposition for the linked-worktree class. The
ordinary-directory upstream source remains openai/codex `rust-v0.162.1`,
`permissions.rs:2347-2367`; no pointer-layout equivalence is claimed.
GPT fix4 FOLLOW-UPS1-3 are retained in the body. No other code scope is added.
