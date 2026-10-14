# Native Muse Code file-access fence

Status: model-free acceptance and the single native reader smoke passed;
independent GPT-family reviews and landing pending. No default/runtime promotion.

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
- Read-only: `/usr`, merged system executable/library paths, named resolver,
  NSS, identity and timezone files, `/etc/ssl/certs`, the exact runtime ELF,
  the brief and explicitly named input files. Input directories are refused.
  Brief/input files inside the worktree get read-only overmounts.
- Home is a synthetic read-only tree with only the runtime file, projected Muse
  settings and the sign-in file. The original home, other repositories, SSH,
  Codex/Claude/hcom roots, private state, co-op/CC roots, host runtime sockets and
  Windows mounts are absent. Binding a named brief exposes only that file and
  synthetic ancestors, not its host parent directory.
- A fenced settings copy retains only `schema_version`, the boolean contributor
  disclosure acknowledgement if present, and forced contributor mode off.
  Both `mcpServers` and legacy `mcp_servers`, `hooks`, managed hook/plugin/skill
  paths, plugins and unknown future extension keys are removed. No host settings
  are modified. A private host staging directory supplies the immutable copy;
  its source is outside all visible writable binds.
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

## Network and execution boundaries

`--disable-web-tools` and `--contributor-mode off` are mandatory in the matched
native argv. Shared networking permits Meta endpoints, other outbound hosts and
host loopback services. There is no DNS/IP/domain egress allowlist. Credentials
reachable through a separate network service are outside this filesystem-only
claim. No proxy credentials are inherited. The scope is an owner-approved reader
smoke, not a hostile-code network qualification or builder/reviewer qualification.

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
