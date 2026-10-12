# Isolated Pi and OpenCode runtime trials

Four profiles provide native Claude Console and OmniRoute routes:
`ns-pi-claude`, `ns-pi-gpt`, `ns-opencode-claude`, `ns-opencode-gpt`.
All remain **trial** until the preregistered comparison selects them.

The renderer in `tools/adoption/runtime_profiles.py` reuses the canonical
Claude MCP renderer and the existing new-WSL wiring map. It installs unchanged
RTK hooks with RTK0.51.0 and Superpowers7.0.0 at its pinned vendor ref. Pi's
package bootstrap re-exposes all15 skills after package filtering; the CC
accepted package-level role scope and requires listing-size measurement.
The CC's B1 ruling explicitly authorizes OpenCode's native read-only skill
loader. Each agent's `permission.skill` grants the27 managed names, its own
role's vendor set and its canonical preloads; the wildcard remains denied.
Security-reviewer preloads security-best-practices and isolated-builder
preloads Context Mode through native file references. Native direct-path Read permissions grant
selected vendor skill directories under the private profile; canonical
managed skills use the named native loader without opening the host directory.
Unselected vendor skill names and direct external-directory permissions are denied.
The cache layout comes from OpenCode53d1eabb `core/src/global.ts:12`,
`core/src/npm.ts:45-50,87,133` and `plugin/shared.ts:207-212`; the Superpowers
skills directory comes from bb92a777 `.opencode/plugins/superpowers.js:25,223`.
Tier1 uses CNP's13-slot input by path, validates its27managed names against
the manifest and preserves its open gaps. Tier2 uses the pinned Skills1.7.0
CLI's unchanged `skills find` path; unset SKILLS_API_URL means skills.sh today.
The future local index can replace that URL through the vendor's documented
seam. A selected skill installs pinned through the existing installer into
the fresh worktree; interactive find installs from a default branch and do
not qualify as pinned Tier2 intake. No copy of CNP's derived input is published.

Existing NAS role texts are translated to native tool grants; review roles
retain their shell/write restrictions. Pi's missing builtin WebSearch remains
an explicit capability omission.

`ns-run <profile> <builder|reviewer|auditor|researcher> <brief.md>` fetches main,
creates a fresh Worktrunk worktree from origin/main, and runs the native client
headlessly. It writes private native events, derived invocation/usage receipts
and a CC handoff. Scratch worktrees are created under `/var/tmp` using the
invocation-local Worktrunk path override. After receipts are written, native
`git worktree remove` removes clean inactive worktrees without force; dirty,
ignored-file or active worktrees remain with a derived cleanup receipt and
their retained path. Interactive launchers create fresh worktrees too; native Pi
session files and transient OpenCode exports feed the existing tracker. Counts
represent prompted or unclassified native calls, never organic-use rates.
The tracker includes the pinned Superpowers15-name and Context Mode inventory
and attributes completed native loader/read calls to those sources. Configured
preloads are recorded separately and never counted as completed tool calls.

OpenCode binds the fresh worktree with both child `PWD` and headless `--dir`:
the pinned run CLI otherwise uses the caller's PWD instead of subprocess cwd.
Its last-loaded native
`OPENCODE_CONFIG_CONTENT` narrows each role's filesystem read patterns and
external-directory rules to that worktree plus selected profile skill dirs;
project config/agents/plugins are disabled so a deep-merged named grant cannot
widen the role tool fence. The worktree's root AGENTS.md is supplied through
native absolute `instructions` in that overlay (OpenCode53d1eabb
`src/session/instruction.ts:135-150`); root-rule prompt loading is measured.
Automatic subtree AGENTS.md discovery is disabled and remains a capability
omission pending its own qualified instruction-loading test.
The pinned evaluator tests direct lexical permissions and role tool grants.
The CC's 16:37:44Z scope ruling retains private profile state and role grants
as this PR's acceptance properties. **PARKED: filesystem read fencing through
aliases.** No current alias-containment guarantee or acceptance claim is made.
Earlier mechanism observations in the receipts are historical fixture results
only and are superseded as readiness claims by this scope ruling. Pi has no
filesystem read fence. Broad read containment needs its own qualification.

Installed Bubblewrap0.11.1 uses its documented `--ro-bind`, `--bind`,
`--unshare-pid`, `--proc`, `--dev` and `--chdir` mechanism; no vendor Read
implementation or runtime plugin is replaced. Its fresh proc/device mounts are
explicit process dependencies, and the network namespace stays native.
Full live Git/MCP consumers still need separate qualification. Keeping this
mechanism is implementation detail, not an alias-read admission gate or a
permission to run W6 arms.
Source: containers/bubblewrap@124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe
`bwrap.xml:135,218,293-317,401-409`, checked with `GIT_NO_LAZY_FETCH=1` and
`git show 124c4cdf:bwrap.xml` in the containers/bubblewrap mirror. The mirror
was synchronized to v0.11.1 at13:51:01Z; the earlier URL check is superseded.

The recorded mechanism exception applies to these command profiles.
At anthropics/sandbox-runtime@d9aac2098351ca17f3743fbaf6ecbd0051b7e00e,
`src/sandbox/sandbox-config.ts:1138` requires network configuration and
`:743-748` requires its allowedDomains array. The supported CLI config therefore
always activates network restriction/proxy (`src/sandbox/sandbox-manager.ts:1919-1930`)
and Linux `--unshare-net` (`src/sandbox/linux-sandbox-utils.ts:3370-3382`). It
has no CLI setting for this filesystem boundary while retaining the original
network namespace/native loopback route. The broader question of whether a supported srt proxy arrangement
could carry these loopback requests is UNTESTED; failed request attempts do not
establish that no such arrangement exists. Closing test is planned as
`test_runtime_profile_consumers.NativeNamespaceConsumerTests.test_srt_proxy_loopback_route`
(not yet implemented/run): use the identical native client and rejecting
loopback stub through srt's documented proxy configuration and require request
capture plus a separately preregistered containment qualification. All cited srt bytes were read from the v0.0.79
mirror with lazy fetch disabled; this is not a blanket proxy limitation claim.

Untested boundary: live Git and the actual committed MCP consumers inside
the new dependency-limited namespace are not qualified. Closing test is planned
as `test_runtime_profile_consumers.NativeNamespaceConsumerTests.test_git_and_committed_mcp_consumers`
(not yet implemented or run): create an origin/main Worktrunk worktree, build
each real OpenCode route command, and require native Git head/status plus every
admitted committed MCP connection and a bounded harmless tool call to succeed
inside the identical wrapper. Record exact tool counts, exits and tracker
observations without copying auth or native session state. Missing Git metadata,
consumer dependencies or disconnected MCP must fail this test. The PARKED
read-fencing question needs a separate qualification before it is claimed. Until it
passes there is no new full-profile acceptance or readiness promotion.

The isolation layer's recorded winner is unchanged. The co-op's research queue
has "srt against direct Bubblewrap for runtime-profile isolation", added at
13:52:29Z with readiness input #1033 LANDED; this comparison decides any later
winner change. This PR does not decide that research row.

Each profile and role owns `CLAUDE_CONFIG_DIR`, `CONTEXT_MODE_DATA_DIR` and
`CONTEXT_MODE_DIR`; the token layer has the actual Pi/OpenCode platform and a
private MCP-child HOME/cwd. Context Mode1.0.169 installs unchanged through
native npm under the profile with `--ignore-scripts`, because its postinstall
repairs HOME/.claude independently of platform. A named native
`npm rebuild better-sqlite3` then enables only its SQLite dependency's installer,
with private npm/header/temp caches. Clean-prefix SQLite execution and the
native boot regression verify that skipping the parent hook keeps stores usable.
The runtime's HOME stays native
for canonical Agent Skills discovery. OpenCode disables Claude prompt fallback
with `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT`; AGENTS.md remains native context.
The hermetic native MCP boot test verifies all4 profiles preserve every writable
fixture entry outside their profile, including the original HOME's settings.
It mounts no host config and leaves /tmp unmounted. The vendor's hardcoded
ephemeral `/tmp/context-mode-mcp-ready-<pid>` sentinel is therefore outside the
production-wide claim: TMPDIR does not redirect it. Persistent host-store
isolation is fixed; no production-wide zero-ephemeral-write claim is made.

Claude slots are selected fill-first4/3/2 using the existing no-token health
probe. Only credential_run injects the credential. OpenCode XDG isolation is
applied **after** the loader resolves its normal host store, so no credentials
are copied into a profile. GPT uses `http://127.0.0.1:21128/v1`. The repository's
old20128 template binding is corrected with a fail-before regression.

Profiles bind committed MCP entries and pins. Headroom, Grafana and Hindsight
are excluded under the CC's current ruling. SocratiCode is **pending E1**:
fresh worktrees have no index; path-per-call or incremental indexing needs
measurement. JCodeMunch retains committed stdio. Live version drift is currency
work, not a profile pin promotion.

Pi OTLP comes from the unchanged native `@b1tank/pi-otel@0.5.0` package,
`b1tank/pi-otel@3cd674533a8d24c9b8a2a6a94072eec25466e128`. OpenCode has native
OTLP export and AI SDK span configuration. Both use the committed WSL collector
endpoint21318; all Pi content-capture flags are false before first extension
load. The Pi extension's upstream local-mock integration test passes on both
its locked dependencies and an explicitly recorded Pi1.1.0 dependency override.
This verifies local mock export/redaction, not complete host collector receipt.

The auxiliary trial prefix uses the existing vendor install paths for
Tavily0.1.8, agent-browser0.38.2 and OpenResearch0.2.15. Version/help invocations
prove execution only; browser automation, authenticated search and research
quality require separate receipts. No new model loop, MCP bridge or fork is
introduced.

Evidence stays within its measured scope:

- [Stage A](STAGE-A.md):35candidates,11documentedpassers,169pinnedreferences.
- [Vendor contracts](VENDOR-SOURCES.md): Pi1.1.0 at04566631 and OpenCode1.18.35
  at53d1eabb; current mirror4d9678a7 is2.0.26 and is distinct.
- [W6 registration](W6-PREREGISTRATION.md) and [replay ledger](REPLAY-SOURCES.md):
  no comparative execution or final selection.
- `receipts/`: sanitized derived facts. Private runtime/config/auth/session/lock
  roots are never copied, hashed or published. The historical private lock scan
  finding is resolved by the CC's vendor-source evidence boundary; raw
  historical artifacts stay untouched.

OmniRoute carries the CC label **"pass-through measured 2026-10-12 for the
reads' configuration (instructions present)"**, with these limits verbatim:

- A same-length rewrite is not detected.
- The output side is checked only by the echo canaries.
- Plugins or payload rules that preserve token counts and canaries are not detected.
- The ~8-token no-instruction default is not attributed (OmniRoute or the provider).
- The effort evidence is directional.
- The header evidence is self-reported by OmniRoute.
- The result holds for OmniRoute 3.8.51 and this route. A version or route change needs a re-run. The record is
  `$STACK_STATE/coordination/ns2604-coop/notes/omniroute-passthrough-20261012/README.md`;
  `probe2.py` and `probe4.py` are beside that external record, not in this repository.

The measurement used cx/gpt-6-astra; these profiles' GPT model is
cx/gpt-6.1-sol. It does not prove every model/route combination unchanged.

The independent GPT implementation review at58a05d03 reproduced four P2s:
interactive Claude/OpenCode collection lost its XDG isolation after the loader;
the renderer added an ungranted native Skill helper; Unicode line separators
inside valid native JSON erased usage/handoff records; Pi MCP exit0 could mean
empty or disabled servers. The follow-up commit restores the isolated
collection environment, preserves imported grants, uses LF-only JSON framing
and requires each mandatory MCP name to be connected. Regression fixtures fail
at58a05d03 and pass with these fixes. Native historical smokes remain bound to
their original profile generation and main head, not relabeled as new runs.

Astra FIRST atc9597fbe confirmed those four repairs and reproduced a further
P2: the generic external-directory deny also blocked selected vendor skill
reads. The CC's read at7a09a808 widened it to zero native role-skill listings
and explicitly reversed the earlier no-Skill interpretation. Round2 repairs
B1 skill discovery/preloads, B2 persistent store and native read containment
plus worktree lifecycle, B3 vendor invocation attribution and B4 the external
measurement pointer. [Round2 receipt](receipts/round2-b1-b4-20261012.json) records
fail-before and final focused results; no new model calls or W6 arms ran.

Pinned mechanisms: anomalyco/opencode@53d1eabb `src/tool/read.ts:250-258`,
`src/config/config.ts:482-489`, `src/project/instance-store.ts:54-58`,
`src/permission/index.ts:28-38`; `src/config/variable.ts:33,61` for preload files;
earendil-works/pi@04566631 `packages/coding-agent/docs/cli.md:231` for preload
files; mksglu/context-mode@6f0cc684 `start.mjs:19-28,308-311,387-389`,
`scripts/postinstall.mjs:211-227`, `src/server.ts:167-180,4861`,
`src/adapters/base.ts:55` and `src/session/db.ts:28` for private stores.
OpenCode source paths above are under `packages/opencode/`.
Worktrunk invocation-local overrides use max-sixty/worktrunk@b49ca7eea9b03145791a5b94eccaf9c59412ed37,
`docs/src/content/docs/config.md:675-698`. Worktrunk and Context Mode references
were originally checked through pinned vendor URLs. Worktrunk's b49ca7ee object
is now present in the mirror; Context Mode's cited source remains unmirrored.
The dependency rebuild uses the installed npm11.19.0 command's supported
named-package form ([npm rebuild](https://docs.npmjs.com/cli/v11/commands/npm-rebuild)).

The earlier adjudicated mechanism remains in the implementation, with read
fencing now PARKED under the scope ruling. B-2 disables project configuration while retaining
root AGENTS.md through absolute native instructions and proves an injected
project shell grant is refused; B-3 updates claims/counts and the rebased base.
The isolation research row is preserved. Both families read the final head
once under the terminal rule. After landing, a fresh `prepare` into a new
private state root is required before comparisons or shadow reviews resume;
the historical v9 state lacks the newer generated directories.

Follow-ups remain: Pi discovery does not gate on auth readiness; interactive
Pi selects role tools without loading role text; inherited hostname references;
briefs >=128KiB hit the Linux per-argument limit with a generic error. The W6
comparison arms wait until B2 lands; historical inference receipts remain
bound to their original generation and heads.

Astra's d475ef81 delta confirms B1's 60 rendered role/profile combinations
and B3's attribution behavior. Its three remaining blockers concern the
publication record: hashes of unpublished failed logs, the synthetic fixture
email under the literal no-reply rule, and the displaced Sol constant locator.
The reopened correction omits all unpublished-output hashes, uses a synthetic
GitHub no-reply fixture identity and restores the current locator. Dedicated
regressions refuse an absent or mismatched published log preimage under these
notes, a non-no-reply fixture identity and a misplaced trial assignment citation.
Named captures remain coordination-side evidence; reviewer-unavailable bytes
do not become independently verified evidence through the receipt's public hash.

Additional P3 follow-ups from that delta: launch exceptions may bypass normal
receipts/cleanup; replaying native boot requires the intended already-qualified
private prefix, since generic installed package layouts may lack the sibling
SQLite dependency expected by the test; and pinned unmirrored source captures
plus a B4 fail-before regression were absent from the review packet. Pi auth,
interactive role text, inherited hostname hygiene and the oversized brief
remain in Follow-ups. W6 arms still wait for B2 landing and the CC cue.

The CC's d475ef81 micro additionally reproduced inherited-PWD session binding
and the loss of repository instructions when project configuration was disabled.
The native regression captures one request at a namespace-local rejecting
stub, with no key, outside network or inference. It requires the actual session
and working-directory markers to identify the fresh worktree, its AGENTS.md
marker to be present, and the primary marker absent. Native `debug agent` read
probes allow the assigned tree and selected vendor file while denying the
primary and unselected vendor files. The before-control loads d475ef81's real
launch code, retaining its inherited PWD; it never assumes the worktree is the
session base. Pin: anomalyco/opencode@53d1eabb `src/cli/cmd/run.ts:134,333-340`,
`src/session/instruction.ts:123-150`; fixture bodies are now byte-identical to
`src/util/wildcard.ts:3-19`, `src/permission/index.ts:28-38,178-214` and
`packages/core/src/npm.ts:45-50`. OpenCode src paths are under packages/opencode.

Store isolation applies specifically to Context Mode and generated profile
files. Launchers and Terminal fragments use their documented external locations;
ai-memory, qmd and SocratiCode retain configured shared stores, and OpenCode can
write its native project-id cache under the Git common directory. Pi has no
filesystem read fence. These boundaries must be carried into the W6 blindness
conditions before any comparison runs.

Other CC P3 follow-ups: canonical managed skills' supporting files remain
unreadable through OpenCode native Read (named skill-loader text still loads);
missing preload files reject the OpenCode config; native boot requires explicit
package qualification and otherwise skips in CI; ignored-only worktrees are
retained conservatively, runtime branches remain, and exception paths can miss
cleanup; the invocation inventory's returned source mapping is currently unused
by launch. These omissions do not become native readiness passes.
The native OpenCode and byte-provenance regressions skip in CI unless their
explicit binary/mirror inputs exist; CI's portable controls do not replace
those native runs. The output-hash regression covers one runtime notes subtree
and specific output-hash keys; the broader publication detector still excludes
notes. Historical flag-truthiness and #161 locator gaps remain named follow-ups.

The dependency selection mounts OpenCode/Node/uv executables as individual files, obtains
Python library paths through native sysconfig, and refuses a directory that
encompasses HOME, the primary checkout or unrelated private-state roots. An
opaque optional auxiliary prefix no longer grants that whole tree; its public
resource paths must be qualified separately. The host and standalone-layout
fixtures are exploratory mechanism evidence; they do not close the PARKED
read-fencing question or establish full runtime readiness.

Default `prepare` now creates every role-scoped descriptor required by the
installed launchers and ns-run; `--no-role-scoped` is an explicit unscoped
research mode, not the preparation contract for those launchers. Preparation
and launch verify native Pi1.1.0/OpenCode1.18.35 existence/version in a private
empty HOME without inherited credentials. Wrong/missing binaries refuse before
trial state is written or a fresh worktree is created. These releases remain
qualified until a separate supported-generation change is recorded.
Native version contracts: earendil-works/pi@04566631:
packages/coding-agent/docs/cli.md:245; anomalyco/opencode@53d1eabb:
packages/opencode/src/index.ts:51, read from their pinned mirrors.
Standalone uv installer layouts: astral-sh/uv@2ad97ed9:
docs/reference/installer.md:5-12 and docs/getting-started/installation.md:270.

Interactive OpenCode collection retains listing/export failures as unmeasured
failure receipts and returns their nonzero status. Partial successful exports
are labelled separately; missing data is never reported as measured zero use.
The session/worktree retry state is retained and cleanup is skipped until a
successful collection. Normal successful cleanup remains receipt-first.
The native baseline switch now selects its loaded baseline's wrapper, or no
wrapper if that baseline predates it; it no longer silently uses the head's
filesystem implementation. Historical captures remain unpublished and unhashed.
