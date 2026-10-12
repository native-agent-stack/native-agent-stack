# Runtime follow-ups after #1033

Base: `703d588c5660d698a87b622efe0e3bd8c22f7e29`. These changes close the
deferred environment, preparation, executable, startup and gateway findings.
They do not qualify alias-read containment, replace an isolation-layer winner,
or establish provider/MCP readiness for the frozen W6 profiles.

## Gateway installation contract first

The landscape stager and Codex profile select 21128. The general service now
requires an explicit `@OMNIROUTE_PORT@` substitution: 21128 for the current
deployment, 20128 to reproduce historical units. The SDK example and current
installation instructions use the same selected port. Historical receipts and
historical build/traffic observations remain dated and unchanged.

Primary source: `diegosouzapw/OmniRoute@7f3cbb046b3706bf0bbc047b7eaa0cbada8d9e50:
bin/cli/commands/serve.mjs:86,180-182` documents `--port` and derives API/dashboard
ports from that selection. The vendor default remains 20128. This is a
prospective installation contract, not an executed host migration. It must
land before another host is installed from the general template.

The regression stages the real lane and compares its default endpoint with a
21128-rendered service; an explicit 21128 override is also checked. At the base
the regression fails (exit 1); the changed template passes (exit 0). The existing
50 gateway-unit checks pass with historical 20128 explicitly rendered.

## Deferred runtime transitions

The native runtime, discovery and OpenCode collector receive an explicit
nonsecret environment allowlist plus generated profile settings. The Console
loader alone retains the host state locator; its supported ID-based injection
supplies the selected provider key. Unrelated inherited credentials and native
host config overrides are not enumerated or forwarded. Installation children
use the same allowlist. The existing loader remains the only credential reader.

Primary controls: Python 3.13's documented `subprocess.run(env=...)` replaces
inheritance (`https://docs.python.org/3.13/library/subprocess.html`);
`containers/bubblewrap@124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe:bwrap.xml:230`
documents the equivalent native clear-environment facility. The deliberate
subprocess environment applies before the namespace, including the Pi route.
Tests launch real Python children inside entirely synthetic fixture environments
and record only whether the unrelated fixture variable is present.

Preparation descriptors say `preparing` while supported npm installation,
SQLite rebuild, RTK init and Pi package installation run. Launch refuses that
state before creating a worktree. After all succeed, Python's supported
`os.replace` atomically promotes the descriptor to `trial`. `prepare --resume`
reuses only this generator's matching descriptor and binaries/pin; it reruns
the unchanged vendor installers and preserves unrelated files. A complete
matching descriptor is skipped, allowing a 20-descriptor prepare to resume.
Unknown roots or mismatched identities are refused and retained. A write failure
before a descriptor exists requires another state root; it is not adopted by
resume. No directory is force-cleaned. Atomic rename reference:
`https://docs.python.org/3.13/library/os.html#os.replace`.

The executable recorded in the descriptor is the absolute resolved file admitted
by the native version check. A synthetic qualified executable is prepared in
one directory and admitted by launch in another. Wrong and absent versions retain
their existing refusal tests. Pi's vendor package commands are unchanged:
`earendil-works/pi@04566631:packages/coding-agent/docs/packages.md:11-19,33-38`.
The separately parked npm-wrapper spelling issue is not qualified by this test.

Every post-worktree launch transition has exception recovery: bounded private
facts identify failure type/status and clean/inactive cleanup versus dirty/active
retention. Raw exception text, command lines and credentials are omitted. Receipt
or cleanup failure preserves the original exception; an unwritable store cannot
promise a persisted receipt. Tests cover actual missing-Bubblewrap admission and
unavailable-slot refusal, with clean, dirty and active cleanup outcomes.

After clean inactive worktree removal, only the generated runtime branch naming
contract is eligible for Git's supported `branch -d`. Unmerged commits, active or
dirty worktrees, unrelated branches and failed removals remain retained. The
installed `git branch -h` describes `-d` as deletion of a fully merged branch.
Real Git fixtures cover owned/other/dirty/active/unmerged branches; no force flag
is used. This is lifecycle cleanup of newly generated branches, not deletion of
other lanes' historical work.

All five transition regressions fail against unchanged `703d588c` and pass on
the follow-up implementation. These are synthetic/native-process and local-Git
controls, with vendor installation effects stubbed; they do not constitute
four-profile inference, MCP-consumer or live namespace qualification.

## Validation boundary

Gateway staging/unit checks are local integration without inference. Native
provider acceptance and a live service restart are outside this PR. No private
W6 configuration, authentication state, session output or failed-log digest is
published here.
