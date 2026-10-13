# Credential paths are denied to sandboxed workers by the native sandbox's read denial, 2026-10-13

Status: decided 2026-10-13 for headless and unattended workers; the sandbox stays the owner's opt-in and this change applies nothing to any host.
Scope: route B of the command center's ruling on the parked guard repair (the text guard gets no further pattern rounds; the vendor's mechanism is adopted, and any later relaxing of the guard happens on
measured evidence in its own pull request). Slot: `sandbox` of the Claude native practice (`reference/isolation.md`: "Hardened native Bash sandbox ... credential deny entries; owner opt-in").

## What the vendor supports (primary sources, fetched 2026-10-13T23:06Z; sizes and sha256 in `receipts/docs-excerpts.txt`)

- The default sandbox reads "most of the machine, including credential files such as `~/.ssh` and `~/.aws/credentials`"; the control is `sandbox.filesystem.denyRead` (`sandboxing.md` L32). A `denyRead` entry
  "doesn't stop the Read tool", which follows permission rules (L42): the Read tool needs the same paths as `Read` deny rules.
- Read rules overlap by the narrower path (L280-L285); array keys merge across the scopes a session loads (`settings-reference.md` L1779).
- A source excluded with `--setting-sources` has its `sandbox.filesystem` entries, its `Edit` permission rules and its `Read` deny rules ignored when the sandbox configuration is built (L274, v2.1.246 or later;
  `cli-reference.md` L129 for the flag).
- `failIfUnavailable` refuses to start when the sandbox cannot, instead of running unsandboxed (`settings-reference.md` L764 and its section).

## Measurement (Claude Code 2.1.296, the first host, bubblewrap 0.11.1; zero spend)

`tools/sandbox-probe/readdeny_probe.py` starts the installed client in a scratch HOME with 14 synthetic credential files at locations of the shared profile template's rules and a loopback stand-in for the
Messages API (`mock_messages_api.py`): no model, no credential, no network beyond 127.0.0.1. Each arm runs the same scripted tool calls, three repeats (`receipts/arms.json`, reduced to status words by
`summarize.py`; the research arms of the same method are `receipts/arms-research.json`):

| Arm | Shell / Python read of the 14 files | Symlink, copy | Read tool on a credential | Ordinary commands |
| --- | --- | --- | --- | --- |
| no sandbox, the template's rules | 14 / 14 readable | readable, copied | refused (the template's rules) | work |
| sandbox on, nothing denied | 14 / 14 readable | readable, copied | **readable** | work |
| sandbox on, the template's rules in the user scope | denied | | refused | **fail**: `bwrap: Can't mkdir parents for /proc/<pid>/environ` in 4 to 5 calls of each repeat |
| the overlay's `denyRead` alone | 14 / 14 denied | denied, not copied | **readable** (`denyRead` does not stop it) | work |
| the overlay and the user scope loaded | denied | denied | refused | **fail**: the same error in 3 to 9 calls of each repeat |
| **the overlay under `--setting-sources project,local`** | **14 / 14 denied** | **denied, not copied** | **refused** | **work, zero tool errors in 3 of 3 repeats** |

The failure is the template's `Read(//proc/*/environ)` rule (the guard against the Read tool reading a process environment): the client adds every `Read` deny rule to the sandbox's read denial, and a path under
`/proc/<pid>/` cannot be created for the denial, so a sandboxed command that touches it exits 1. Measured research arms (`receipts/arms-research.json`, three repeats each): the template's rules without that one rule
work (zero errors); `allowRead` of `/proc` or of `/proc/*/environ` does not cure it (7 to 14 and 1 to 5 errors).

## Decision

1. **`adoption/templates/claude.sandbox-readdeny.settings.template.json` is the overlay of a sandboxed worker**, passed as `--settings` together with `--setting-sources project,local`. It enables the sandbox,
   fails closed (`failIfUnavailable`), forbids the unsandboxed retry (`allowUnsandboxedCommands: false`), denies the 24 credential locations to sandboxed commands (`sandbox.filesystem.denyRead`) and the same
   locations to the Read tool (`permissions.deny`). The launcher chooses the permission mode, the network allowlist and everything else.
2. **The locations are the shared profile template's own home-anchored `Read` rules** (24), as paths (a directory for `/**`, the parent directory for the `*.env` and `*.key` patterns); the test derives the list from
   the template and holds the overlay to it, so a new credential location is added to the template first and the test then fails until the overlay follows.
3. **The overlay carries no `/proc` rule, and a sandboxed worker does not load the user scope**: the shared template keeps its process-environment rule for interactive sessions (no sandbox), and
   `--setting-sources project,local` leaves it out when the sandbox is built, which the arms above measure. The Read tool's own protection of a process environment in a sandboxed worker is the text guard's
   (its hook is registered in the user scope, which this launch leaves out; not measured here): a worker whose Read tool must be fenced from `/proc` reads is launched with `--tools` that omit Read, or the gap is accepted; the record
   states it and the owner decides.
4. **Nothing else changes.** The text guard stays as it is; relaxing its refusals on this evidence is a separate reviewed pull request (the ruling). No host configuration is written.

## Alternatives

- **Enable the sandbox in the user scope with the template's rules**: measured to break sandboxed commands (the `/proc` error), in every repeat.
- **`allowRead` the `/proc` paths**: measured not to cure it.
- **An explicit `denyRead` list without Read rules**: measured to leave the Read tool able to read the credentials (`denyRead` does not stop it).
- **Read rules without an explicit `denyRead` list** (the client converts them): the template's rules without the `/proc` rule give 14 of 14 denied in the research arms; the explicit list is kept as well because it is the
  documented control for sandboxed commands and does not depend on the conversion.
- **The vendor's `credentials` setting** (environment variables and files with `mode: deny`): a different mechanism for secret variables; not part of this item.

## What is not covered

- **Interactive sessions**: they load the user scope, so the `/proc` rule and a sandbox cannot be combined (decision 3); the sandbox is the owner's opt-in there. The real-HOME check of the memory servers is the earlier condition.
- **What the sandbox does not bound**: the file tools other than Read, MCP servers, hooks and the status line stay outside it (`reference/isolation.md`). Write and Edit deny rules are the permission system's.
- **macOS and Windows** (Seatbelt, the native sandbox of those clients) were not run; only Linux with bubblewrap 0.11.1 was.
- **A host without bubblewrap or `socat`**: `failIfUnavailable` makes the worker refuse to start; that is the intended failure.
- **The measurement is one client version on one host with synthetic files**; the opt-in test (`NAS_NATIVE_SANDBOX_PROBE=1 python3 -m unittest tests.test_sandbox_readdeny.NativeProbeTests`) repeats it.

## Overturn conditions

- A client release that lets a `Read` deny rule of `/proc` coexist with the sandbox: the overlay can then load beside the user scope and decision 3's separation ends.
- A client release that applies `denyRead` to the Read tool, or stops converting `Read` rules: the overlay's second list is dropped or the first becomes enough.
- A change of `--setting-sources` semantics for the sandbox configuration (`sandboxing.md` L274): re-run the probe.

## Evidence

| Claim | Class | Receipt |
| --- | --- | --- |
| the default sandbox reads credential files; `denyRead` does not stop the Read tool; an excluded source's sandbox and Read rules are ignored | source_review | `receipts/docs-excerpts.txt` |
| the arms of the table, three repeats each | native_proven (client 2.1.296, one host, synthetic files) | `receipts/arms.json`, `receipts/arms-research.json`; `NativeProbeTests` |
| the overlay is the template's rules as paths, with the three flags and no `/proc` rule; the receipts say what this record says | local_integration | `tests/test_sandbox_readdeny.py` (11 tests, one opt-in); `receipts/mutants-18.txt` (18 of 18 killed) |
