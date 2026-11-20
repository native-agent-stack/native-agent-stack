# ADR-0040: `v3.10.11` Landscape Terminal Convergence, Dec 6 `23/5` SIP Pre-Cutover Readiness Contract & Dual-Pool Compute Standard

- **Status:** Accepted
- **Date:** 2026-11-19
- **Layer:** Organization Umbrella (`L1`): sibling-commit pins, the promotion-track non-interference boundary as an umbrella invariant, the `23/5` SIP cutover readiness contract, and multi-account compute governance
- **Evidence Grade:** E3 (reproducible contract evidence, re-derived on `2026-11-19` at the four pinned commits: every pinned SHA equals its repository's remote `main`; sibling ADR counts `17` / `26` / `61` / `35`; the shelf taxonomy block SHA-256 recomputed from the pinned catalog; the cutover drill re-run offline from the pinned workflows commit at `33/33`; UTP Vendor Alert `#2026-24` re-read at the source; `40/40` umbrella ADRs. Deliberately below `E4`: the `2026-12-06` cutover has not happened, so its readiness contract carries no runtime evidence, and the dual-pool standard is a governance contract with no keybank artifact in any repository at seal time)
- **GitHub Evidence:** https://github.com/native-agent-stack/sota-upstream-shelf-lock/commit/546cdef91ba72c7679969a8bd879058c51e70ec0, https://github.com/native-agent-stack/sota-compounding-lab/commit/69c86acf8701979d47b03eb173796e97bfd46160, https://github.com/native-agent-stack/sota-mover-ranker/commit/a58c1b8dc29fcb4fcae9867ef37890d45479d3f5, https://github.com/native-agent-stack/sota-multi-model-workflows/commit/fbd6fdb7d43da5ed001ef0f995d05da28a136889, https://github.com/native-agent-stack/sota-upstream-shelf-lock/blob/546cdef91ba72c7679969a8bd879058c51e70ec0/docs/adr/ADR-0017-terminal-platform-taxonomy-and-provenance-governance.md, https://github.com/native-agent-stack/sota-compounding-lab/blob/69c86acf8701979d47b03eb173796e97bfd46160/docs/adr/ADR-0026-closed-loop-tca-collar-recalibration-temporal-firewall-and-trial104.md, https://github.com/native-agent-stack/sota-multi-model-workflows/blob/fbd6fdb7d43da5ed001ef0f995d05da28a136889/src/sota_mmw/boats_23x5_cutover_drill.py, https://github.com/native-agent-stack/sota-harness-foundation/blob/8b2ce5352018d377e32b3e234d7106a843d68285/docs/adr/ADR-0017-native-agent-stack-org-public-private-governance-and-ci.md
- **Revisit Trigger:** `2026-12-06` (the scheduled `21:00 ET` consolidated SIP open; every open item of the readiness contract is re-verified on or after that date and the result lands as a successor ADR). Earlier on any reschedule notice from the SIP operating committees, any Trial `#104` pre-registration, or the first commit that implements `sota-anthropic-keybank.v1`

## Context and Problem Statement

The `v3.10.11` wave landed four sibling changes, each on its own repository's `origin/main` after that repository's own cross-vendor audit: a terminal and platform taxonomy on the upstream shelf, a closed-loop paper collar recalibration contract in the compounding lab, four harvested cockpit upgrades in the mover ranker, and a hardening of the `23/5` cutover drill in the multi-model workflows. The umbrella lock still described `v3.10.10`, and four questions had no single owner:

1. **No umbrella pin.** Until the umbrella records the four commits, the ecosystem monitor reports manifest drift and no downstream seal can cite one consistent set.
2. **A new artifact class with zero decision authority.** The cockpit overlays are visual. Each sibling states its own side of the rule that keeps them out of order decisions, but the charter (one owner per layer, no duplicated ownership) needs the cross-repository invariant stated once.
3. **A cutover that has not happened.** The consolidated SIP is scheduled to begin `23/5` operation on `2026-12-06`, seventeen days after this decision. Sealing it as active would be false. Saying nothing would leave three different clocks (the SIP, the Blue Ocean ATS venue, and the IBKR overnight order expiry) easy to conflate; the drill oracle itself conflated two of them before the pinned workflows commit corrected it.
4. **No written rule for which credential pool pays for which work.** Interactive Orca workers and unattended SDK, batch and CI calls had no stated separation, and there was no custody rule for an Anthropic API key.

**Numbering note.** Shelf `ADR-0017` and the phase-one specification refer to this pointer as "umbrella `ADR-0039`". That number was taken by the `v3.10.10` firewall seal, which landed first, so those references resolve to this `ADR-0040`. Nothing in `ADR-0039` or any earlier seal block is changed here.

## Decision Outcome

### 1. Pin the four landed sibling commits, as pointers only

Each row is owned by its repository. The umbrella records the commit and a small number of scalar facts; it restates no sibling table, formula or threshold.

| Repository | Owner decision | Pinned `origin/main` commit | ADRs |
| --- | --- | --- | --- |
| `sota-upstream-shelf-lock` | `ADR-0017`, terminal and platform taxonomy | `546cdef91ba72c7679969a8bd879058c51e70ec0` | `17` |
| `sota-compounding-lab` | `ADR-0026`, collar recalibration, temporal firewall and Trial `#104` rules (plus the Wave B6 quote-size unit fix) | `69c86acf8701979d47b03eb173796e97bfd46160` | `26` |
| `sota-mover-ranker` | `ADR-0061`, harvested cockpit upgrades | `a58c1b8dc29fcb4fcae9867ef37890d45479d3f5` | `61` |
| `sota-multi-model-workflows` | Wave B3 hardening of the `23/5` cutover drill (code and tests, no new ADR) | `fbd6fdb7d43da5ed001ef0f995d05da28a136889` | `35` |

- **Shelf.** `sota-upstream-shelf-lock` is the only owner of the `terminalPlatformTaxonomy` block (schema `sota-terminal-platform-taxonomy.v1`): `4` classes and `14` named surfaces, with the `18` immutable core pins untouched. The umbrella carries the owner, the two counts and the SHA-256 of the canonical block, `2c81665b9dba2590db3649f00dae309bf5c33704d641faa19160741c54b8c61d`. It carries no class name and no surface row.
- **Lab.** `sota-compounding-lab` owns `sota.collar-recalibration.v1`. The umbrella records two properties of it and nothing else: a recommendation never loosens a collar beyond its pre-wall prior, and it is advisory on paper lanes, which are never gated by it. The lab also owns the exclusive study boundary `2026-10-16T04:00:00Z` and the statement that Trial `#104` was not consumed.
- **Ranker.** `sota-mover-ranker` owns four harvested cockpit upgrades, each default off, their six non-interference barriers, the two recorded Lightweight Charts versions (`5.0.8` deployed asset, `5.3.0` shelf pin), the Wave B4+B5+B7 hardening precondition for enabling any Wave C flag, and the sequencing that places the deferred GAP-0 work at ranker `ADR-0062`.
- **Workflows.** `sota-multi-model-workflows` owns the cutover drill (`sota-boats-23x5-cutover-drill.v1`) and its session, broker and port checks. Section 3 cites its schedule; it does not copy its scenario list.

### 2. Promotion-Track Non-Interference Boundary (umbrella invariant)

`VISUAL_TELEMETRY_OR_GOVERNANCE` is a decision-authority class recorded on each cockpit artifact. It sits under the existing `PROTECTIVE_FILTER_OR_GOVERNANCE` promotion kind and is not a third promotion kind.

| Class | Authority over an order decision | May do | Entry requirement |
| --- | --- | --- | --- |
| `VISUAL_TELEMETRY_OR_GOVERNANCE` | None | Render and log | `DECISION_AUTHORITY = "NONE"` and `STANDALONE_ALPHA_CLAIM = False` recorded on the artifact |
| `PROTECTIVE_FILTER_OR_GOVERNANCE` | Subtractive | Validate a staged ticket; veto, delay, tighten or shrink an order. Never originate or enlarge one | The governance-kind checks of the workflows promotion verifier |
| `ALPHA_STRATEGY_MINOR` | Additive | Originate entries and size | The alpha-kind checks of the same verifier, a minor or major version bump (`v3.11.0` at the earliest), and a pre-registered Trial `#104` cleared at `t*(104) = 4.2063` on pre-wall data |

**The invariant.** Let `D` be the function that produces every order intent in every lane (entry, exit, size, price, stop, cancel), and let `V` be the outputs of every artifact classed visual. For any two values of `V`, `D` returns identical intents on identical market and account inputs.

- Paper lanes are never gated by policy, so the invariant is not "nothing unvalidated may trade on paper". It is that a visual artifact has no path into `D`, and that nothing reaches a higher class without that class's entry requirement.
- `v3.10.10` to `v3.10.11` is a patch bump. No alpha can be elevated in this wave; `alphaPromotionRequiresMinorBumpAndPreregisteredTrial` is `true` in the lock.
- The peer-bus ledger holds `103` registered trials: `102` resolved and `1` pre-registered. The next candidate is therefore evaluated at `104`, where `t*(104) = 4.2063`. The lock field `hlzTrialsCompleted: 103` keeps the name used by earlier seal blocks and counts ledger registrations. `trial104Consumed` is `false`: no part of this wave spent it.
- The only route from visual to anything higher: freeze the feature definition at a commit, pre-register on the peer bus through the power gate, spend the trial, test on pre-wall data only, clear the target class's entry requirement, and land a new ADR in the owning repository with an approved compounding version record and a version bump of the required size. Live paper observation never counts as discovery evidence.
- The mechanisms that enforce the invariant are tests owned by ranker `ADR-0061`. A visual artifact may not be bound to an alert or webhook; shelf `ADR-0017` owns that rule.

### 3. Dec 6, 2026 `23/5` SIP Pre-Cutover Readiness Contract (`PRE_CUTOVER_READINESS_CONTRACT`, not active)

The lock records `sip23x5CutoverDateEt: "2026-12-06"` and `sip23x5CutoverStatus: "PRE_CUTOVER_READINESS_CONTRACT"`. This ADR flips no flag, switches no feed and changes no lane. The status may change only through a successor ADR that carries runtime evidence gathered on or after the cutover.

Three clocks, kept separate:

| Clock | Event | Eastern time |
| --- | --- | --- |
| Consolidated SIP (UTP Vendor Alert `#2026-24`, SEC Release `34-105780`) | First `23/5` open | Sunday `2026-12-06` `21:00 ET` |
| Consolidated SIP | Maintenance fence, Monday to Thursday | `20:00–21:00 ET` |
| Consolidated SIP | Weekly close | Friday `20:00 ET` |
| Alpaca Blue Ocean ATS (BOATS) | Sunday venue open, a separate venue and feed event | Sunday `20:00 ET` |
| IBKR paper `:4002` | An overnight DAY limit order expires | `03:50 ET` |

An explicit BOATS selection never substitutes for the SIP, and the reverse holds too. Between `03:50 ET` and `04:00 ET` an IBKR overnight order is expired even though the SIP and the BOATS venue continue.

Open until re-verified on or after `2026-12-06`. None of these is claimed as done:

1. **Schedule.** Re-read the SIP operating committees' notices before the date; a reschedule reopens this ADR.
2. **Drill.** Re-run the workflows drill at the then-current `main` and re-pin the commit.
3. **Consumer agreement.** Every session classifier in the cockpit and protection repositories returns the same segment as the drill at the cutover-night instants (Sunday `19:59`, `20:00`, `20:59`, `21:00` and across ET midnight), with one overnight trade-date key held across midnight.
4. **`DF10` overnight relative volume.** A 20-session baseline cannot exist for a new overnight SIP session until about 20 sessions after the cutover. During that cold-start window overnight relative-volume values are to present as unavailable, never as a number. This is an inference from the feed definition and stays open until the `DF10` owner confirms it.
5. **Unchanged invariants.** The cutover moves no hard invariant: the pre-wall study cutoff, the `ADR-0022` stop cap of `2.00%`, the paper-port allowlist `{4002, 8787, 8797, 8799}` and the refusal of every live route (the drill refuses `:8796`) all stand.

**Separate from `v3.11.0`.** The owner-registered `v3.11.0` blueprint (GAP-0 to GAP-6, ranker `ADR-0062` onward) is deferred work. `v3.10.11` consumes none of it, and nothing here pre-approves any of it.

### 4. Dual-Pool Multi-Account Orca OAuth & Banked Anthropic API Token-Efficiency Standard (`sota-anthropic-keybank.v1`)

Two pools, never mixed.

**Pool 1: interactive and heavy Orca CLI workers.** These run only on Orca-managed OAuth subscription accounts, so they burn zero API credit. The account is chosen when a worker is launched: read `orca account list --json`, then `orca account select` the account with the lowest weekly and Fable usage or with reset credits. Selection applies to new launches and is a deliberate, visible step. It is not failover: the standing owner rule is no automated account rotation, and on a rate limit a worker slows down. No agent reads, copies or moves an Orca credential.

**Pool 2: banked Anthropic API credit, for SDK calls, asynchronous batch jobs, the advisor tool and public-repository CI only.**

- **Custody.** Key material is encrypted at rest only through OS-native DPAPI in `CurrentUser` scope, which only the same Windows user can decrypt. Zero plaintext on disk; zero keys in repositories, logs or any global, machine or persistent user environment. Because DPAPI is Windows-only, custody is bound to the stationary Win32 host; this standard defines no store for the WSL2 guest or the portable Mac, and neither may hold Pool 2 key material until a successor ADR names an equivalent OS-native store.
- **Prompt caching is mandatory.** Stable content goes first and the cache hit is verified from the usage counters. The planning target is a `50–90%` input-cost reduction on repeated prefixes; the documented ceiling is cache reads billed at about one tenth of base input, with a write premium of about `1.25x`.
- **Batch API is mandatory for asynchronous bulk audits and evals,** at `50%` of standard cost. It is not for latency-sensitive calls.
- **Advisor tool.** A `claude-sonnet-5-5` executor consults `claude-fable-5-2` or `claude-opus-5-5` (tool type `advisor_20260301`, beta `advisor-tool-2026-03-01`, first-party Claude API only). No claim is made that it combines with the Batch API.
- **Code-intelligence pre-filtering before any Pool 2 call:** `rtk`, `context-mode`, `codebase-memory-mcp`, `ast-grep`, `qmd`. Send the excerpt, not the tree.
- **Public-repository-only CI allowlist.** A Pool 2 secret may be configured only in the `9` repositories of `publicUnlimitedActionsTier`. All `9` `PRIVATE` repositories are hard-refused, and the `4` cold-archived repositories stay actions-disabled. The secret lives only in the platform's encrypted secret store, never in workflow text or logs, and never reaches a run triggered from a fork. Owners of the underlying rule: `sota-harness-foundation` `ADR-0017` and umbrella `ADR-0002`, enforced by the hard invariant `private_github_actions_enabled: false`.
- **Models.** Only models on the active roster; no retired model is added to either pool.

**What this section is.** A governance contract. `dualPoolComputeGovernanceSchema` names the standard and `publicCiOnlyApiSecretFirewall: true` is a policy flag, not a measurement. No keybank code exists in any repository at seal time, and this ADR created, read and moved no key. Provisioning a Pool 2 key is an owner action. The first implementation needs its own ADR and a red-team pass in the repository that owns it.

### 5. Lock, tests, catalog and README

- `ECOSYSTEM_CONVERGENCE_LOCK.json`: `schemaVersion` moves from `3.10.10` to `3.10.11`, and one block is appended, `v31011LandscapeTerminalConvergenceAndDec6ReadinessSeal`. Every earlier seal block, the tier sizes `9` / `9` / `4`, the layer map and the hard invariants are byte-identical.
- `tests/test_umbrella_convergence.py`: the version assertion moves to `3.10.11`; a focused test asserts every field of the new block.
- `docs/adr/CATALOG.md` and `README.md`: version `v3.10.11`; ADR counts umbrella `40`, shelf `17`, lab `26`, ranker `61`.
- `pyproject.toml` (`3.0.0`) and `uv.lock` are untouched.

## Alternatives Considered

- **Copy the sibling tables into the umbrella lock.** Rejected: two copies drift, and the charter forbids duplicated ownership. The lock holds a commit, a hash and counts.
- **Seal the cutover as active, or grade this ADR `E4`.** Rejected: an ADR can be accepted as a decision about a future event, but it cannot carry runtime evidence for something that has not happened.
- **Add `VISUAL_TELEMETRY_OR_GOVERNANCE` as a third promotion kind now.** Rejected: the workflows verifier accepts two kinds, and widening it is a code change outside this wave. It is scheduled as `v3.11.0` work.
- **Fold the `v3.11.0` blueprint into this seal.** Rejected: that work is deferred and has its own numbering.
- **One credential pool for everything.** Rejected: API credit spent on interactive workers is waste the subscription already covers, and a subscription login is the wrong credential for unattended SDK, batch and CI calls.
- **A plaintext key file or a global environment variable.** Rejected: both put a secret where any process, log or backup can read it.
- **Rotate Orca accounts automatically on a rate limit.** Rejected: the owner rule is no automated rotation or failover.

## Consequences

- Good: one commit set for the wave, so the organization seal that follows can pin all five repositories without drift.
- Good: the boundary between rendering and deciding is stated once, with its enforcement left to tests in the owning repository.
- Good: the three cutover clocks are written down before the night they matter.
- Cost: the lock now carries a status that must be revisited. Until the successor ADR lands, `PRE_CUTOVER_READINESS_CONTRACT` is a statement of intent.
- Cost: Pool 2 has a rule and no implementation. Anyone who needs the keybank before its implementing ADR lands has no sanctioned way to hold a key.

## Verification Witness

Re-derived on `2026-11-19`:

- Each pinned SHA equals the repository's remote `main` (GitHub commits API), and each tree at that SHA holds `17`, `26`, `61` and `35` ADR files.
- SHA-256 of the `terminalPlatformTaxonomy` block of `STARRED_CONVERGENCE_CATALOG.json` at the pinned shelf commit, serialized as JSON with sorted keys and compact separators in UTF-8, equals the value in the lock. The block reports `4` classes and `14` named surfaces.
- The cutover drill, run offline from an archived copy of the pinned workflows commit: `33/33` scenarios pass.
- UTP Vendor Alert `#2026-24`, read at https://www.nasdaqtrader.com/TraderNews.aspx?id=UTP2026-24: from `2026-12-06` the UTP SIP runs from Sunday `21:00 ET` to Friday `20:00 ET` with a maintenance window of about `20:00–21:00 ET` each evening.
- Ledger count from the peer bus: `103` trials, next hurdle `4.2063`.
- Lock comparison against the previous commit: all `42` earlier top-level keys present; only `schemaVersion` differs.
- `uv run python scripts/architecture_catalog.py --check` (`40/40` MADR 4.0 ADRs), `uv run python scripts/merge_gate.py` (zero-leak scan, `umbrella --check`, `ruff check`, `ruff format --check`, `ty check`, `pytest -q`), and `gitleaks protect --staged --redact` (`0` leaks).

Carried, not re-derived here:

- SEC Release `34-105780` (https://www.sec.gov/files/rules/sro/nms/2026/34-105780.pdf) could not be fetched in this session. It is cited through the pinned workflows commit.
- The sibling audits and the sibling test suites, other than the drill above.
- The ranker's six barrier tests are acceptance criteria of its Wave C flags and do not exist yet, as ranker `ADR-0061` states.
- Anthropic cache and batch pricing and the advisor pairing come from the vendor's API reference as cached on `2026-11-03` (https://platform.claude.com/docs/en/build-with-claude/prompt-caching, https://platform.claude.com/docs/en/build-with-claude/batch-processing). The DPAPI scope is from https://learn.microsoft.com/dotnet/api/system.security.cryptography.protecteddata.protect, read `2026-11-19`.
- `orca account list` and `orca account select` were confirmed to exist from the command help only. Neither was run.

## Rollback

Revert this single commit, then re-seal any downstream pointer in reverse landing order. The block is additive and no sibling reads it, so nothing upstream breaks. Reverting does not undo a sibling commit.
