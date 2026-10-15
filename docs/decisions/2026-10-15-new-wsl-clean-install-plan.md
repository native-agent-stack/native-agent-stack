# Decision: clean install plan for the next WSL distribution (2026-10-15)

**Status:** DRAFT for review. The command center (CC) accepted its division of labor and
boundary on 2026-10-15.

## Trigger and roles

The owner's directions of 2026-10-15, paraphrased:

- **17:23Z and 17:57Z, to this lane:** a clean Claude Code configuration converged on the best-practice sources, and a
  new WSL distribution built from a clean install plan, every layer decided by evidence through the layer-resolution
  protocol, the harness base included.
- **17:57Z, to this lane and the CC:**
  - the runtime workers the owner named (Jev, Muse, OpenCode, Pi) as clean workers focused on trading and the API data
    feed;
  - a clean memory layer, and possibly a new repository;
  - a new command center on the new distribution that takes over from the current one;
  - one paper lane kept on NativeStack2604 and everything else handed over (superseded at 19:46Z: every paper lane
    moves);
  - a plan to clean up disk Z and the processes occupying the CPU.
- **18:05Z and 18:07Z, to the CC:** account C stays on NativeStack2604 (superseded at 19:46Z, below). The new
  architecture should give the fastest reaction, with Jev and related repositories, instead of selection rounds of
  several minutes.
- **18:16Z, to the CC:** resolve and finalize the new WSL now, under the foundation harness rules. Nothing gates on the
  paper lanes. LEAN may be used, paid if needed, where the evidence shows it fits.
- **18:19Z, to this lane:** fully designed harness frameworks such as superpowers should power OpenCode, Pi and the other
  workers cleanly. The new WSL should carry the ecosystem's full clean stack.
- **18:22Z, to the CC:** the distribution's name (`NativeHorizonNY`), New York as its native time zone, and every layer
  of the two catalogs resolved, with no subset.
- **19:12Z, to the CC:** the harness comes first. The new distribution must not become a second trading system that
  cannot react fast or use its portfolio.
  - It needs the current converged practice in every layer: context engineering for each agent, sessions that launch
    seamlessly, the god view, the resolution practice, the CC practice with its evidence, the compounding manifest,
    GitHub automation and the current models.
  - The owner wants to see the installed skills of every agent and runtime worker.
- **19:19Z-19:20Z, to the CC:** superpowers goes into Pi, OpenCode and the other harnesses as runtime workers.
- **19:22Z, to the CC:** Claude sessions get their own full harness cycles too, with the converged frameworks
  installed, superpowers and beyond. The CC's addendum-02 records this and supersedes the 19:20Z exclusion of Claude Code.
- **19:46Z, to the CC:** the trading system on the current distribution has failed, and the new one must not repeat
  that.
  - Its trading system reacts fast on advanced data feeds, uses each paper lane's portfolio with automatic leverage,
    takes over every paper lane, and works only toward the north star.
  - The strategy shape: an extreme-mover lane that enters early; a research-driven long-term lane that compounds in
    companies of extreme potential; sizing moved into the symbols both lanes share when such a company's catalyst
    fires; and a fast position monitor, with trailing stops as protection only and re-entry always possible.
  - TradingView automation with in-app strategies and MCP control tied to the positions record, and a live account
    for real trading, which the CC's ruling keeps owner-gated.
  - The command center relaunches on the new distribution when it is ready. That distribution needs a stronger god view
    and orchestration practice, token saving with a maintained context lead, context engineering against context rot,
    the current CC practice, and the starred and Jev-related repositories.
- **19:59Z, to the CC:** not only superpowers: the full landscape of converged harness layers, installed and set up on
  the new distribution.
- **20:04Z, to the CC:** install that full landscape, but enable each framework only for the sessions and agents it
  suits, as context engineering.
- **20:09Z-20:18Z, to the CC:**
  - each model family's runtime workers get their own full-landscape stack, including the fully harnessed SDK and
    framework workers;
  - GitHub automation covers the whole lifecycle, with reviews from more than one model family;
  - a new private repository holds the new distribution's runtime ecosystem as code, with local-first enforcement
    (Decision 1).
- **20:41Z, to the CC:** full access at every layer on the new distribution, with GitHub automation at the highest
  quality (Decision 10).

The CC recorded these in its direction records of 2026-10-15 (18:09Z, 19:12Z and 19:46Z, each with its addenda) and its
handover set of the same day. These are private records, cited by name only.

| Role | Owner of it |
| --- | --- |
| The new-distribution build | this lane |
| Everything live on NativeStack2604 until the boundary | the CC |
| Moving every paper lane (accounts A, B and C, and IBKR paper) by per-lane move sheets with one writer per account; the north-star trading spec (Decision 4) | trading-cc |

The owner's lists of tools are leads under the protocol, not selections.

**Practice content needs a source at a pin.** The CC corrected its own rulings on 2026-10-15 at 20:48Z, with addenda at
20:51Z and 21:12Z. Owner directions are dated triggers and requirements, and their implementation is chosen by
convergence. In this record:
- every install, integration or sourcing names its upstream source at a pin (a repository path and line, a release note
  or an official document), or reads from the installed client itself;
- any practice content without such a source is labelled **PROPOSAL** and routed to the
  [layer-resolution protocol](2026-10-11-layer-resolution-protocol.md). This includes the CC's role-assignment matrix
  fields, the horizon enforcement design, and the trading mechanics until trading-cc's cited spec lands.

## Inputs consumed (layer-resolution protocol)

Per [the protocol](2026-10-11-layer-resolution-protocol.md), steps 1 to 3, at `origin/main` `8053f14e7`:

- **Verdicts.** `catalogs/landscape/final-stack.json` (checked 2026-10-11; `python3 scripts/final_stack.py --check` exit
  0):
  - 35 layers: 0 FINAL, 30 reopened, 3 unswept, 2 no-winner;
  - 66 winners, 59 of them with a run pin;
  - 28 winners whose run pin differs from the verdict pin (a report-only flag).
- **Latest sweeps** (`catalogs/saturation/ledger.json`):
  - `landscape-sweep-20260929`: the foundation layers;
  - `landscape-sweep-20260926`: the trading layers;
  - `landscape-sweep-20261009-pine`: the backtesting engine.
- **In flight, owned elsewhere and consumed as named inputs:**
  - run pins and E2E receipts for the winners (FINALIZE-ALL F1, a co-op lane);
  - the unswept model-routes layer (F5, a Codex lane);
  - the Claude Code 2.1.300 floor in the profiles (#1128);
  - practice-skill currency (#1171) and the gap-ledger rows (#1147, #1157, #1158, #1160, #1169);
  - the trading lane's fast-path work (the H1 stream hub, scanner v1) and its Jev feature path off the order path
    (Decision 4), in the trading repository.

**Delta only.** This record dispatches no new survey. Each change below is one of the protocol's delta kinds:

- an existing survivor to adjudicate;
- an upstream mechanism changed at its pin;
- a named evidence gap;
- a committed comparison.

## Every layer

Every layer of `catalogs/landscape/final-stack.json` at `8053f14e7`: the 20 foundation and 12 trading layers of the two
catalogs, plus `foundation/model-routes`, `us-equities/catalysts-sentiment` and `us-equities/judgment-features` (the
table below). The file also holds 13 skills layers (`coverage.skills`; `summary.skills_layers` 13, `skills_swept` 0),
listed after the table. No subset.

- None is FINAL.
- Each row's next action is the protocol's delta for that layer: adjudicate its carried survivors, close its FINAL
  conditions 2-4 (a run pin, an E2E receipt through the upstream's own path, invoke evidence), or, for an unswept layer,
  an initial sweep scoped to the gap.
- Generated with the stdlib over `final-stack.json` (`layers[].status`, `winners`, `survivors`, `open_gaps`), with
  per-layer overrides where this record or a named lane owns the next action. The three unswept layers have
  `open_gaps: null`, shown as "not assessed", not 0.

| Layer | Status | Winners | Carried survivors | Open gaps | Bounded next action |
| --- | --- | --- | ---: | ---: | --- |
| `foundation/agent-sdks` | reopened | codex | 2 | 14 | adjudicate 2 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/ci-supply-chain` | reopened | zizmor, syft, candidate:actions-attest | 6 | 14 | adjudicate 6 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/code-navigation` | reopened | serena | 3 | 5 | adjudicate 3 carried survivors; E2E and invoke evidence (FINAL 3-4) |
| `foundation/document-retrieval` | reopened | qmd, markitdown, poppler | 13 | 7 | adjudicate 13 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/durable-memory` | reopened | ai-memory | 8 | 13 | adjudicate the carried survivors; a colliding candidate only on measured evidence |
| `foundation/git-github-automation` | reopened | worktrunk, candidate:cli-cli, difftastic | 2 | 12 | adjudicate 2 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/hosting-services` | reopened | fastapi, nextjs, postgresql | 0 | 14 | run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/instructions-skills` | reopened | affaan-m/ECC, candidate:typesafe-ai-skills, candidate:openai-skills | 1 | 12 | ECC at its current head; superpowers TRIAL and the paired comparison (Decision 6) |
| `foundation/isolation` | reopened | worktrunk, sandbox-runtime | 2 | 19 | adjudicate 2 carried survivors; run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/mcp-surfaces` | reopened | mcporter, mcp-inspector | 0 | 14 | run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/model-routes` | unswept | none | 0 | not assessed | F5 (Codex lane) sweeps it; its output is a named input |
| `foundation/native-clients` | reopened | claude-code, codex | 0 | 14 | run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/observation-inference` | reopened | opentelemetry-collector-contrib, prometheus, loki | 6 | 11 | adjudicate 6 carried survivors; run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/quality-evaluation` | reopened | promptfoo, playwright-test | 2 | 11 | adjudicate 2 carried survivors; E2E and invoke evidence (FINAL 3-4) |
| `foundation/recovery-portability` | reopened | restic, candidate:astral-sh-uv | 1 | 12 | adjudicate 1 carried survivor; E2E and invoke evidence (FINAL 3-4) |
| `foundation/scheduling-supervision` | reopened | dagu, systemd | 4 | 13 | adjudicate 4 carried survivors; E2E and invoke evidence (FINAL 3-4) |
| `foundation/secrets-credentials` | reopened | gitleaks | 3 | 9 | adjudicate 3 carried survivors; E2E and invoke evidence (FINAL 3-4) |
| `foundation/semantic-rag` | reopened | socraticode, qdrant, vllm | 5 | 12 | adjudicate 5 carried survivors; run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/token-efficiency` | reopened | rtk, headroom, ccusage | 5 | 6 | adjudicate 5 carried survivors; run pins for 3 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/web-research` | reopened | tavily-cli, agent-browser, openresearch | 4 | 9 | adjudicate 4 carried survivors; run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `foundation/workers` | reopened | claude-code, worktrunk | 1 | 8 | adjudicate 1 carried survivor; run pins for 2 drifted winners (F1); E2E and invoke evidence (FINAL 3-4) |
| `us-equities/agents-models-workers` | reopened | codex-native-sdk, foundation-ai-memory, foundation-socraticode | 1 | 15 | adjudicate the carried survivor; runtime workers per Decision 5 |
| `us-equities/backtesting-engine` | reopened | nautilustrader, lean | 7 | 12 | OPEN: the co-op's engine comparison (LEAN, NautilusTrader IB, the native port) |
| `us-equities/catalysts-sentiment` | unswept | none | 0 | not assessed | initial sweep scoped to the gap |
| `us-equities/data-quality-orchestration` | reopened | dagu, data-pandera | 1 | 9 | adjudicate 1 carried survivor; E2E and invoke evidence (FINAL 3-4) |
| `us-equities/evaluation-experiments` | reopened | foundation-agent-retrieval-bench, inspect-ai, data-mlflow | 0 | 10 | E2E and invoke evidence (FINAL 3-4) |
| `us-equities/execution-broker` | no-winner | none | 9 | 1 | trading lane: adjudicate its survivors after the engine comparison |
| `us-equities/identity-provenance` | reopened | data-dvc | 2 | 5 | adjudicate 2 carried survivors; E2E and invoke evidence (FINAL 3-4) |
| `us-equities/judgment-features` | unswept | none | 0 | not assessed | initial sweep scoped to the gap |
| `us-equities/market-data-reference` | reopened | data-alpaca-py, data-edgartools, data-exchange-calendars | 4 | 17 | adjudicate 4 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `us-equities/observability-hosting` | no-winner | none | 1 | 1 | adjudicate its 1 carried survivor, or preregister its comparison |
| `us-equities/portfolio-risk` | reopened | skfolio | 1 | 13 | adjudicate 1 carried survivor; E2E and invoke evidence (FINAL 3-4) |
| `us-equities/research-factors-ml` | reopened | skfolio, data-edgartools | 5 | 16 | adjudicate 5 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `us-equities/security-supply-chain` | reopened | grype, syft, gitleaks | 7 | 16 | adjudicate 7 carried survivors; run pins for 1 drifted winner (F1); E2E and invoke evidence (FINAL 3-4) |
| `us-equities/storage-compute` | reopened | data-duckdb | 1 | 11 | adjudicate 1 carried survivor; E2E and invoke evidence (FINAL 3-4) |

**The 13 skills layers, all unswept:** `skills-agent-docs`, `skills-architecture`, `skills-browser`, `skills-ci-pr`,
`skills-debug`, `skills-design-intake`, `skills-implement`, `skills-mcp-build`, `skills-research`, `skills-review`,
`skills-security`, `skills-skill-lifecycle` and `skills-test`. Each is a GAP: its next action is an initial sweep scoped
to its lifecycle task.

The install plan installs each layer's current winners, as the plan's rows record them. A layer's next action changes
what the new distribution installs only when its result lands.

### Wave order (the owner's 19:12Z direction: the harness first)

- **T1, together:**
  - the trading-critical layers: `us-equities/execution-broker` and `backtesting-engine`, whose engine comparison
    decides;
  - the harness layers of the owner's areas below: `token-efficiency`, `durable-memory`, `code-navigation`,
    `semantic-rag`, `document-retrieval`, `instructions-skills`, `native-clients`, `workers`, `isolation`,
    `observation-inference`, `git-github-automation`, `ci-supply-chain`, `model-routes` and `agent-sdks`.
- **T2:** `us-equities/market-data-reference`.
- **T3:** every other layer, and the 13 skills layers.

### The owner's areas, mapped to layers and plan rows

| Owner's area | Catalog layers and records | Plan row |
| --- | --- | --- |
| Context engineering | token-efficiency, durable-memory, code-navigation, semantic-rag, document-retrieval, instructions-skills | Decisions 2 (stage C rows) and 6 |
| Seamless launch | native-clients, workers, isolation; the session relaunch (#1116 and its follow-ups) | Decision 8 (re-pin); the session relaunch has **no plan row yet**: a gap for stage F |
| God view | observation-inference, the session monitor | boundary condition 3; the observability rows wait for stage S |
| Resolution practice | `docs/decisions/2026-10-11-layer-resolution-protocol.md` | this record's inputs and wave order |
| CC practice and evidence | the claude-native-practice skill and its re-pin | Decision 8 |
| Compounding manifest | the `final-stack.json` generator, the evidence manifests | the lineage-gap check (Decision 2); the generated status page (#1175) |
| GitHub automation | git-github-automation, ci-supply-chain | stage C rows (worktrunk, gh, difftastic, zizmor, syft, actionlint); the full-lifecycle, multi-family review automation in horizon (Decision 1, the CC's addendum-05 ruling 2); GitHub access (stage G, Decision 10) |
| Models | model-routes (GAP, unswept), agent-sdks; Muse, OpenAI through OmniRoute, the Anthropic API | Decision 5; the `gpt-gateway` row (Decision 3); F5 sweeps model-routes |

The CC's 19:46Z ruling 4 adds to these areas. Each addition falls in T1's harness layers and enters by the protocol:

| Addition | Catalog layers and records | Plan row |
| --- | --- | --- |
| A stronger god view (every lane, unit, worker and order path) and agent-orchestration practice | observation-inference, the session monitor; the practice skill's orchestration rows | boundary condition 3; cc-native-practice's god-view and orchestration rows on 2.1.301, a named input |
| Token saving and a maintained context lead in each long session | token-efficiency, durable-memory | the stage C rows (rtk, headroom, ccusage). The context lead has **no plan row yet**. The CC withdrew its own definition of it (20:48Z), so it is resolved through the protocol over token-efficiency, durable-memory and instructions-skills, and cc-native-practice carries only the converged, cited row |
| Context engineering against context rot for runtime-worker sessions: compaction policy, fresh relaunch at boundaries, handoffs | workers, token-efficiency, durable-memory | Decision 5; the co-op's research dispatch, a named input |
| The current CC practice | native-clients; the claude-native-practice skill re-pinned to 2.1.301 | Decision 8 |
| The starred and Jev-related repositories, and beyond | every layer: `catalogs/convergence-practice/public-starred.json` and `tools/starred-maintenance/` (#978, #1016) | the co-op's dispatch into the manifest; a repository enters a layer only as a candidate under the protocol |

## Decision 1: the base is the repository's new-WSL path; the 10-07 kit is superseded as an installer base

| Property | Repository new-WSL path | agent-harness kit (private) |
| --- | --- | --- |
| Parts | recipe `adoption/platforms/linux-wsl2-new-distro.md`; profile `adoption/new-wsl-profile.json` (`new-wsl-clean-foundation`); install plan `evidence/artifacts/new-wsl-install-plan-20261002/`; client config `tools/adoption/new_wsl_client_config.py` with its closed-world map | `bootstrap`, `manifest.toml`, `config/`, one plugin, instruction files |
| Last change | profile and map through 2026-10-12, with open PRs on the map | last commit 2026-10-07; last push 2026-10-08 |
| Checks | `new_wsl_client_config.py --check` exit 0 (403 pieces); `check_plan.py` exit 0; `adoption-bootstrap.yml` on every PR and nightly, green at main on 2026-10-15 | CI exists: three runs, the last green on 2026-10-08 |
| Host use | the plan ran in a fresh throwaway distribution on 2026-10-02 and, as its 64-row revision, on NativeStack2604 the same day | never installed on any host |
| Owed | named per row in the plan's README | six checks in `docs/verification-owed.md`, none run, including the paired instruction-text evaluation that its own rollout rule requires |

- **Supersession.** The kit stops being a candidate installer base. Its records stay as history, and a dated status
  pointer goes into the kit's decision record by pull request.
- **Instruction text.** The kit's instruction files stay an alternative under the practice skill's `instruction-files`
  slot. They can replace the current files only by that slot's overturn rule, a paired same-task run. Its inputs are the
  kit text at its last commit, the current files at a pinned main commit, and a sealed task set.
- **Harvested as cited candidates:**
  - the always-loaded instruction budget check (8,192 bytes in total, 200 lines per file; the kit's last commit);
  - the checksummed guard-hook packaging (`plugin/hooks/SHA256SUMS`).
- **A new repository: superseded on 2026-10-15.** This decision first said "not now". The owner's directions of
  16:09-16:18 ET, recorded in the CC's addenda 05, 06, 07 (with erratum-01) and 08 to its 19:12Z direction, replace it:
  - horizon is the private home of NativeHorizonNY's runtime ecosystem as code. It was created as
    `native-agent-stack/horizon` and moves to `seathatflowsinourveins/horizon` when the transfer lands. A private
    repository can carry a ruleset only on GitHub Pro, Team or Enterprise Cloud (GitHub's "About rulesets", read
    2026-10-15T21:38Z). The CC measured the rest on 2026-10-15 (addendum-08): the organisation's free plan refuses a
    ruleset on a private repository, `gh api user` reports the owner's account on plan "pro", and the owner's
    private us-equities-trading repository carries an active ruleset (Decision 10). horizon covers host configuration and install
    stages, the per-family runtime stacks and worker profiles, the role-assignment matrix,
    the CC, co-op and god-view tooling, session relaunch, the multi-family GitHub automation, and the ecosystem's
    self-maintenance (sweeps, practice audits, currency and invoke-rate checks).
  - **Local-first enforcement: a PROPOSAL** (the CC's addenda 07 and 08), routed through api-actions'
    repository-topology decision record, which cites GitHub's documentation. The local gates are primary, and GitHub
    only refuses a merge that skipped them.
    - The CC lander is the only merge path. It requires both families' verdict files bound to the head and the local
      CI receipts at that head.
    - The lander posts those results as required statuses at the head SHA (local CI and each review family's
      verdict). A ruleset on main requires a pull request and those statuses, and blocks force-pushes and deletion.
      A merge queue stays out of reach: it needs an organisation repository, and a private one only on Enterprise
      Cloud (GitHub's "Managing a merge queue", read the same day). No hosted CI is required.
    - Agents are denied pushes to main, and a pre-push hook in every clone refuses them.
    - The self-maintenance audit alerts on any commit on main that the lander did not land.
    - GitHub Actions there are optional, never required.
  - **The split.** native-agent-stack stays the public source of research, catalogs, decisions and evidence;
    us-equities-trading stays the private trading code; ecosystem-records stays the private sealed history. horizon
    pins them by commit, copies nothing wholesale, and is seeded only from landed, converged pieces.
  - The route followed addendum-05 ruling 3: an audit of the existing private repositories (keep, fix or retire), a
    decision record, the owner's choice of name and visibility, then creation. api-actions created the repository on
    2026-10-15 and owns that route's records, its landing mode and the repository-topology decision record. This
    plan's stages still run from files on main until horizon's pieces land there.
  - The text it replaces, kept as history: not now, because every stage runs from files already on main and the kit,
    the last new-repository attempt, stalled before any host use. It was to be revisited only if the boundary run
    showed a host-private artifact, and private state went to the continuity design's private records remote.

## Decision 2: the plan binds to generated sources, not to a hand-written tool list

| Stage | Source | Check | Named inputs before it runs |
| --- | --- | --- | --- |
| R. Rehearsal | recipe R1 on a throwaway name, P1-P3, W1-W7 and F1-F3, then its removal | R1's proofs; the interop check after `--unregister` | the host isolation rules below |
| A. Windows side and first boot | recipe P1-P3, W1-W7 and F1-F8 for the real name; `adoption/templates/wsl/` | the recipe's proofs and the stage-1 receipt | R removed with every proof held |
| C. Stage 2: the install plan, the clients first (`install.sh` installs Claude Code and Codex by their native installers before the other rows) | recipe F9; `evidence/artifacts/new-wsl-install-plan-20261002/` (`install.sh`, `accept.sh`) | `check_plan.py`; the post-install stage of `accept.sh` | the slice caps below; a no-start install path in the living plan (below); the gateway's composition tarball (below); F1's run pins as they land |
| D. Client configuration | recipe F9: `tools/adoption/new_wsl_client_config.py --apply --host <host>` | `--check`; the apply receipt | the template-behind rows of the [reconciliation record](2026-10-15-claude-host-config-reconciliation.md); the memory-owner row (its executable); the per-row port change (the collector port, Decision 3) |
| H. Harness landscape (Decision 9); it follows stage C, and is listed after D because its client-level installs need D | the co-op's screen tables; each candidate's vendor install path | one check per candidate, its recorded inverse, invoke wiring and a FINAL or TRIAL label; the role-assignment matrix's per-role checks | stage C; for client-level installs, stage D; for a candidate that starts a service, the port and isolation rules (Decisions 2 and 3) |
| E. Sign-ins | recipe F9: `codex login`, then `claude`, by hand | the after-sign-in checks of `accept.sh` that read no service port | the owner: credentials and sign-ins are the owner's |
| S. Services | in order: activation (after the port and isolation proofs, each service starts by its recorded route: a user unit with `enable --now` where the install placed one, otherwise the foreground or daemon start the plan records, and Dagu by its installer's own service mode; Decision 3); the plan's service-health stage, which runs after the service starts (`evidence/artifacts/new-wsl-install-plan-20261002/README.md:41`); the gateway's provider sign-in (an owner act); then the after-sign-in checks that need a service | the activation receipt; `accept.sh --stage service_health`; `accept.sh --only <slot> --stage after_sign_in` for the nine rows whose check needs the gateway (`omniroute.service`): mcp-inspector, grafana, inspect-ai, promptfoo, cross-family-review, gpt-gateway, agent-runtime-worker, lm-program-optimization and research-harnesses | the per-row port gap below, closed for every listener and for the checks' own ports; the listener-ownership check (Decision 3) |
| G. GitHub access (Decision 10) | api-actions' access manifest in horizon: identities, scopes, repositories, token lifetimes and each repository's required checks, as names and scopes only | the manifest's checks, the hooks in every clone, and the access audit | the manifest landed in horizon; the owner's steps (Owner acts) |
| F. Records and lanes | GitHub clones; the continuity design's private records remote | the boundary receipt | stage G; the CC's handover index; trading-cc's move sheets |

- **Order.** The new distribution runs neither `adoption/bootstrap-linux.sh --profile` nor `--configure-full-profile`
  (recipe F9). The install plan's `install.sh` order is the install order. `scripts/new_host_grand_list.py --check` (exit
  0: 32 layers, 66 winners) and `scripts/final_stack.py` cross-check the winners and run pins; they do not install.
- **Rehearsal scope.** R1 asks for a rehearsal through F3, then a preregistered comparison of the 26.04.1 default with the
  24.04.5 rollback, extended through F9 "using the existing bootstrap". That comparison cannot run as written: F9 now
  retires the bootstrap routes it names, so it needs a new preregistration, not an execution.
  - The 24.04.5 arm exists only for a release-caused 26.04 failure. NativeStack2604 has run 26.04.1 since 2026-10-02.
  - This plan therefore runs the required rehearsal through F3 on a throwaway name and removes it.
  - The comparison is recorded as owed, with the reason above. This is a recipe deviation taken on that evidence.
  - Unregistering is low-risk on this release: the recipe records the interop registration surviving both unregisters of
    2026-10-02 on WSL 3.0.1 (microsoft/WSL PR #40621). The check after each `--unregister` still runs.
  - "Through F3" carries F3's return obligation. Its rootless-container proof needs an engine. When none is installed,
    the recipe records the check as owed, runs F4, F5 and the engine setup, then returns to the proof before F9 or R1's
    acceptance (`adoption/platforms/linux-wsl2-new-distro.md:954-961` at `8053f14e7`). An owed check is not a pass.
  - A failed proof takes the recipe's recovery order (`:707-710`): terminate only the new distribution, export its
    failed state, and unregister only that name. The time-zone pair is the one exception: a mismatch is recorded and
    stops the run for review, and that recovery does not run for it (`:705-707`).
- **Interim stage C.** Until the no-start mode and the per-row ports land (Decision 3), stage C runs
  `install.sh --only <slot>` in plan order and skips seven rows:
  - `memory-owner`: it starts ai-memory on 29374, NativeStack2604's live memory owner, and points Codex hooks at
    `127.0.0.1:29374` (`install.sh:453-472` at `8053f14e7`), which on the shared network would write into the live
    store. Unregistering the new distribution cannot undo such writes.
  - `local-model-server`: it enables Ollama for boot on 21434.
  - `dagu`: its installer runs with `--service yes`.
  - `gpt-gateway`: it needs the composition tarball.
  - `container-engine`: already installed at F3.
  - `embedding-model` and `local-generation-model`: named-only.
- **What the rows start (`install.sh` at `8053f14e7`).** The persistent starts are `enable --now` for ai-memory
  (`:467`), Ollama (`:739`) and Docker (`:852`), and Dagu's `--service yes` (`:830`). Skipping their rows does not hold
  them all, and the rows that ran are not all start-free:
  - **Docker through a dependency.** Selecting `harbor-containerized-agent-e2e-runner` or `docker-compose` sets
    `needs_docker` (`:1155`), and the installer then runs `run_slot container-engine` (`:1249-1250`) with no second
    selection check (`:1183-1186`). That path installs the engine's packages and runs
    `systemctl --user enable --now docker.service` (`:844-852`).
    - Both rows ran in interim stage C, and each log shows `container-engine | install | 0`.
    - The engine was already installed and active from F3, so the packages were already the newest and the user unit
      stayed active and enabled. Rootless Docker serves a Unix socket, and the guard recorded no new listener after
      either row.
    - Excluding `container-engine` therefore did not keep the engine path from running, so the no-start mode has to
      cover this dependency path too. Until it does, each of these two rows counts as a service-starting row under the
      rule below, with F3's rootless-container proof as the engine's isolation proof.
  - `mineru` starts the MinerU server for its own commands and stops it on exit (`:380`). It ran in interim stage C,
    and its log shows `Server started` and `Server stopped`. Measured afterwards with the installed MinerU 4.0.10 on
    both distributions, `mineru server status --json` reports the socket `~/.mineru/doclib.sock` and `tcp.enabled`
    false, so the server binds no TCP port. The row ran before that proof existed: a deviation, recorded here.
  - `command-output` starts `codex app-server` over stdio (`tools/adoption/apply_codex_lane.py:524`, `--listen
    stdio://`), which binds no port.
  - `agent-runtime-worker` installs a template unit and runs `daemon-reload` (`:951`); nothing starts.
  - Not run: `grafana` (measurement-only) enables and starts the research-progress timer (`:725`), and `gpt-gateway`
    installs its units without starting them (`:930`).
- **The guard is not the proof.** After each row, a guard reads the listeners owned by the new distribution's own
  processes (`sudo ss -ltnp`, lines with `users:`) and stops the run if one is still new 5 s after the row ends.
  - It sees only what listens at a row's end, so it missed the MinerU server, which had already stopped.
  - The first two driver runs used a guard without the owner filter. Each halted on a listener whose owner it did not
    record: `127.0.0.1:25112` after `claude-code` and `127.0.0.1:24756` after the Codex SDK row.
- **Rule from here.** No stage C row that starts a service, a transient start included, runs before its port and
  isolation proof, or before the no-start mode covers it.
- **Lineage gap.** The install plan's rows and the client-config map follow the 2026-10-01 definitive manifest and its
  later waves; neither reads `final-stack.json`. Once F1 lands, the proposed change is one check: it fails when an
  installed row's pin differs from its layer's landed run pin. Until then, the 28 report-only drift flags are the known
  difference.

## Decision 3: the distribution and host isolation

- **The distribution.**
  - Name `NativeHorizonNY` (host value file `nativehorizonny`); Ubuntu 26.04.1, the recipe's default image.
  - The image is already in `Z:\WSL\downloads`; W2 re-checks its signed hash before use.
  - The name is the owner's (2026-10-15, 18:22Z, through the CC): Native for the native agent stack, Horizon for the
    full landscape, NY for New York time.
  - It is a new production distribution beside NativeStack2604, not the continuity design's restore drill. The drill
    stays with the continuity lane under its own gates.
- **New York time.** The system time zone is America/New_York, by WSL's documented mechanism for this release:
  - the user-data writes `[time] useWindowsTimezone=true` (`adoption/templates/wsl/cloud-init.user-data.template:27-28`),
    and WSL sets `/etc/localtime` from the Windows zone at instance start (the recipe's W5 time-zone proof cites
    microsoft/WSL tag 3.0.1, `src/linux/init/timezone.cpp:22-110`);
  - the Windows zone reads `Eastern Standard Time` (`tzutil /g`, 2026-10-15), and NativeStack2604, built the same way,
    reads `America/New_York` with `date` printing EDT.
  - Acceptance: `timedatectl show -p Timezone --value` prints `America/New_York`, and `date` prints EDT or EST.
  - Records keep both clocks, UTC and ET. Time-sensitive code gets fail-first tests under `TZ=America/New_York` across
    both DST transitions, with `calendar.timegm` for UTC conversions (`time.mktime` minus the zone offset is 3600 s early
    under DST).
- **Shared network.** WSL 2 distributions share one network namespace, and `.wslconfig` sets mirrored networking
  (recipe, host-wide rules; `adoption/platforms/linux-wsl2.md`, "Listeners and ports"). Both distributions run side by
  side until the boundary and the CC's cleanup after it, and for all that time every listener competes for the same
  ports.
  - Measured on 2026-10-15 (`ss -ltnH` on NativeStack2604, 156 listening TCP ports): 14 of the 15 ports that the install
    plan's rows and the F8 host template name are already bound. They are 21080 (dagu), 21090 (prometheus), 21093
    (alerting), 21128 (gpt-gateway), 21300 and 21396 (loki), 21301 (grafana), 21318, 21333 and 21888 (the collector),
    21808 (session-analytics), 29374 (memory-owner) and the host template's 21633 and 28231. Only 21434 (the model
    server) is free.
  - A row can bind more than one port. A second measurement on 2026-10-15 compared every port named in the plan's
    `config/`, `install.sh` and `accept.sh` (at `8053f14e7`) with NativeStack2604's listeners. Four more are bound there:
    - the gateway's WebSocket listeners 21129 and 21131 (`config/omniroute.service:22-23`, beside its 21128);
    - the collector's OTLP receiver 21317 and its telemetry endpoint 21889 (`config/otel.yaml:9` and `:464`).
    - So every listener a service row binds gets its own per-row port, not only the row's main port, and the stage-S
      ownership check covers each one.
  - F8 picks the host file's ports outside the workstation's set (done: memory 23374, Qdrant 23633, embedder 23231).
  - The collector's 21318 is the recipe's exception, a conflict to resolve before F9
    (`adoption/platforms/linux-wsl2-new-distro.md:1068-1072` at `8053f14e7`): the client-configuration tool renders it
    into both clients.
    - Stage D therefore waits for the per-row port change, which gives NativeHorizonNY its own collector port.
    - Until then nothing on NativeHorizonNY exports telemetry to 21318.
  - `observability/backends/configure.py --port-overrides` is not the route for this plan: it renders the separate
    `ecosystem-*` stack, while the plan's observability files come from its own renderer
    (`evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py`).
  - **Named gap on the living plan, part 1: ports.** The services' ports are fixed in the plan's configuration and its
    renderer, and also in the checks, helpers and readers that dial them (at `8053f14e7`):
    - ai-memory 29374: `accept.sh:630`;
    - the collector 21333: `accept.sh:986`;
    - Prometheus 21090 and Alertmanager 21093: `accept.sh:1001-1006`, `:1038` and `:1091-1110` (the last raises a
      `severity=page` alert);
    - Loki 21300 and Grafana 21301: `accept.sh:1149`, `:1166-1176` and `:1213`;
    - Dagu 21080: `accept.sh:1543`;
    - the gateway 21128: `accept.sh:1302-1311`, `:1427-1430`, `:2055`, `:2087-2088`, `:2294`, `:2438` and `:2641`;
      `tools/research/gpt_researcher.sh:31`; `tools/adoption/runtime_profiles.py:44`, which `:308-309` and `:321-322`
      use for the Pi and OpenCode GPT profiles; the installed `config/deer-flow-config.yaml:10` and
      `config/openhands-job.json:4`;
    - stage D's reader, `tools/adoption/new_wsl_client_config.py:379-388`, which takes the collector and gateway ports
      from the plan's rows and writes the gateway port into Codex's `omniroute` base URL
      (`adoption/new-wsl/client-config-map.json:814-818`).
    - The model server's 21434 (`accept.sh:459`, `:1239-1279`) is free on NativeStack2604 today; the ownership check
      covers it like the rest.
    - Special cases:
      - the MCP Inspector probe's temporary listener on 16399 (`inspector-client-probe.sh:28`, `:40`, `:48`; its
        cleanup is checked at `accept.sh:2249`) gets a per-row port and is verified like the rest;
      - the alerting fixture's 21997 must stay closed (`accept.sh:1081-1082`, `:1096`: a failed connection and no
        listener), so it keeps its own closed-port predicate instead of the ownership check;
      - Grafana's optional gRPC address 21302 (`config/grafana.ini:13-16`) is listed explicitly: Grafana is
        measurement-only, and its activation receipt states whether that endpoint is active;
      - codebase-memory's UI port 9749 (`DeusData/codebase-memory-mcp` `v0.11.0`, `src/ui/config.h:4` and `:13`;
        `README.md:139-142`). NativeStack2604's codebase-memory daemon binds it (measured on 2026-10-15), and upstream
        describes the UI as owned by one shared coordination daemon. So the UI stays disabled on NativeHorizonNY
        (`ui_enabled` in that home's `~/.cache/codebase-memory-mcp/config.json`) until it has its own per-row port and
        an ownership proof;
      - session analytics binds 127.0.0.1:8080 from its archive configuration (`README.md:442`). That port is free on
        NativeStack2604 today, and the ownership check covers it.
    - On the shared network these reach NativeStack2604's live services, against the CC's rule that its services and
      ports are left alone (18:09Z direction, addendum-01, ruling 1). A check would pass against the wrong
      distribution, the research-harnesses check (`accept.sh:2446-2474`, both clients) would route the new
      distribution's research runs through NativeStack2604's gateway, and the alerting check could page through its
      Alertmanager.
    - The proposed change is one port parameter per listener of each service row (the gateway has three), read from
      the host value file, rendered by the plan's own renderer and read by those checks and helpers too.
    - **Listener-ownership check (stage S), keyed on the dialled port.** Before a check, helper or run dials a port,
      it confirms that a process of the new distribution owns the listener on that same port. The check is
      `sudo ss -ltnpH`, a line with `users:`: iproute2 6.19.0's `ss` (`-p, --processes`: show the process using the
      socket). Measured on 2026-10-15, NativeHorizonNY sees NativeStack2604's listeners with no `users:` field.
      Otherwise the check fails: an answer from NativeStack2604 is never a pass.
    - Until both land, nothing on NativeHorizonNY dials a service port, at stage E or later. Stage D waits for the
      gateway's port as well as the collector's, since its reader writes both.
  - **Named gap, part 2: a no-start path.** The installer starts services as it installs: `systemctl --user enable
    --now` for ai-memory (`install.sh:466-467` at `8053f14e7`, port 29374, which is bound), Ollama (`:739`), Docker
    (`:852`) and Grafana's research-progress timer (`:725`), and Dagu's installer runs with `--service yes`. MinerU's
    row starts its server for the row's own commands (Decision 2's inventory). The installer has no option to install
    without starting.
    - The proposed change is a no-start mode of `install.sh`. Units are installed and reloaded but neither enabled nor
      started; enabling alone would start them at the next boot through linger. Dagu's installer gets its no-service
      mode. The change is covered by `check_plan.py` and a fail-first test.
    - **Activation is its own step, at stage S.** Installing without starting leaves every service down, and the
      service-health stage runs only after a service starts (`README.md:41`). So stage S opens with an activation
      step, after the port and isolation proofs and before any health check:
      - each service starts by its recorded route, on its per-row ports:
        - where the install placed a user unit (ai-memory, Ollama, the gateway, and Docker and Dagu through their
          installers): `systemctl --user enable --now <unit>` (systemd `v259` `man/systemctl.xml`, `enable` with
          `--now`);
        - otherwise the foreground or daemon start that the install plan records. The install places no unit for the
          collector or Alertmanager, and for Prometheus it only copies a `.service.example` under `$config_root`
          (`install.sh:661`). So the collector (`otelcol-contrib`), Prometheus and Alertmanager use
          `evidence/artifacts/new-wsl-install-plan-20261002/SOURCES.md:179-190` (Loki and Grafana there are
          measurement-only), and session analytics uses `agentsview daemon start` (`README.md:442`);
      - Dagu gets its installer's own service mode. Upstream offers `--service` only at install time
        (`dagucloud/dagu` `v2.18.2`, `scripts/installer.sh:113-114` and `:919`, read at the tag through GitHub's API),
        so the pinned installer reruns with `--service yes --service-scope user`, plus the install's own
        `--host 127.0.0.1` and `--port`, set to Dagu's per-row port instead of `install.sh:830`'s 21080.
        - Dagu also runs a second listener, its coordinator. It is enabled by default and binds
          `coordinator.port` 50055 (`internal/cmd/flags.go:234-237` and `internal/cmd/startall.go:45` at `v2.18.2`;
          `SOURCES.md:190`).
        - Its activation therefore either sets a separate per-row coordinator port or disables the coordinator
          (`coordinator.enabled=false`), and the ownership check covers the coordinator port too.
      - The activation receipt lists each unit's state and the listeners it opened, with each listener's owner.
    - Parts 1 and 2 are one dispatched Codex lane (install-nostart). Its landing closes the CC read's P1-1 and the
      local review's P1-2.
    - Until both parts land, a stage C row that starts a service, transiently or not, runs only after its port and
      isolation proof (Decision 2's inventory); the other service rows wait.
  - **Gateway input.** The default `gpt-gateway` row needs the prebuilt composition tarball with its recorded size and
    digest (`OMNIROUTE_COMPOSITION_TARBALL`, `install.sh:928` at `8053f14e7`). Neither the checkout nor an earlier stage supplies it.
    Before that row runs, the tarball is copied from NativeStack2604's handover staging and its digest is checked;
    without it, the row waits.
  - Which services each lane needs comes from trading-cc's move sheet for that lane.
- **Lanes.** NativeHorizonNY takes over every paper lane, accounts A, B and C and IBKR paper, each when the new trading
  stack passes its gates (the CC's 19:46Z ruling 2, which supersedes keeping account C on NativeStack2604). Until then
  no paper lane trades, and trading on NativeStack2604 is closed (ruling 1).
  - Each lane moves under trading-cc's move sheet for it, with a STOP-HERE receipt on NativeStack2604 before it starts
    on the new distribution, so every paper account has one writer.
- **CPU and memory.** WSL 3.0.1 and later give each distribution its own cgroup namespace (recipe; host WSL 3.0.3.0).
  - Idle class inside the new distribution yields only to its own processes, not to NativeStack2604's sessions and
    services, which carry all live work until the boundary.
  - A scope around the invoking command does not contain the work the service manager or the Docker daemon starts: the
    installer's user services, and the containers that rootless Docker runs (Harbor's `harbor run --force-build`, for
    example).
  - A command launched through `wsl.exe` lands in `/non-systemd`, outside every systemd slice. A `systemd-run --user
    --scope` command lands under `user.slice/user-1000.slice/user@1000.service/app.slice` (measured on NativeHorizonNY,
    2026-10-15, `/proc/self/cgroup`; the root's `cgroup.subtree_control` lists `cpu memory pids`).
  - So the absolute limits go on the slices that contain all of that work, inside the new distribution:
    `sudo systemctl set-property --runtime user.slice CPUQuota=<n>% MemoryMax=<n>G`, and the same on `system.slice`
    for the system units that packages start.
    - `user.slice` holds the user manager, its services, rootless Docker and its containers.
    - Every heavy command runs inside `systemd-run --user --scope`, so it lands under `user.slice` too. Nothing heavy is
      launched straight from `wsl.exe`.
  - The values are set from the load measured at the time, with headroom kept for NativeStack2604.
  - Before a heavy step, both slices' `cpu.max` and `memory.max` are read back from `/sys/fs/cgroup/`, along with the
    step's own `/proc/<pid>/cgroup`.
  - NativeStack2604's `/sys/fs/cgroup/cpu.stat` and `cpu.pressure` are read before and after the first heavy step, so a
    claim that the step did not take from NativeStack2604 has a measurement.
- **Disks.** No command touches NativeStack2604's disk (`Z:\WSL\NativeStack2604\ext4.vhdx`), the swap disk
  (`Z:\wsl-swap\swap.vhdx`) or NativeStack2604's state roots.
  - The recipe's host-wide rules apply: no `.wslconfig` change, no `wsl --update`, never `wsl --shutdown`, and no change
    to the default distribution.
- **Inverse.** `wsl --terminate NativeHorizonNY`, then `wsl --unregister NativeHorizonNY`, which deletes the new disk,
  followed by the recipe's interop proof on NativeStack2604. Any export happens before the unregister.
- **Credentials.** None move. The owner re-enters keys on the new distribution. Broker credentials appear there only
  when a lane moves.

## Decision 4: the north-star trading system on NativeHorizonNY

The CC's 19:46Z rulings 1-3 set the target. trading-cc's north-star trading spec, still to come, is this section's named
input and owns the design. This section records the target, its gates and what installs; it designs no strategy. The
owner's requirements below are fixed. The mechanics the CC wrote around them (catalyst overlap, sizing and leverage,
the position monitor, the positions manifest) are PROPOSALS until trading-cc's spec cites their primary sources.

- **NativeStack2604 trading is closed** (ruling 1). No paper session runs there. Four P1 lessons from the CC's row
  record of that trading become hot-path requirements on NativeHorizonNY:
  - the quote's own source time;
  - an exit owner that outlives the trader;
  - exits sized only from a fresh deterministic reply;
  - pinned helpers.
- **The target** (ruling 3):
  - fast reaction: the H1 market-data stream and the seconds-level deterministic scanner feed every lane;
  - an extreme-mover lane, entering early on deterministic rules over fresh quotes;
  - a long-term compounding lane: a research-driven watchlist of companies with extreme potential, with its own
    evidence record;
  - catalyst overlap: when a compounding-lane company's catalyst fires and the company is also in the mover set, the
    deterministic sizer shifts exposure into the overlap symbols, up to the lane's configured maximum leverage under the
    deterministic risk governor. Caps are code, never prompts;
  - portfolio use: automatic leverage per paper lane, with utilization and trades per minute measured and reported;
  - a position monitor and exit owner: a deterministic watcher bound to the owned order ids that survives any session,
    broker-native trailing stops as protection, fast exits, and re-entry allowed;
  - a positions manifest: one deterministic record per lane of positions, orders and fills, with its evidence chain.
    MCP control and every report read from it;
  - TradingView automation (in-app strategies, alerts and webhooks, MCP control, strategy templates and their
    fine-tuning) enters by the layer-resolution protocol: a research sweep, then a TRIAL, never a default on one angle.
- **LIVE trading is owner-gated; this plan designs it only.** The architecture keeps a live adapter behind its own
  gates. No live order path is enabled until the owner opens it, with written limits and live credentials that the
  owner enters, and after paper evidence under the same code.
- **The later refinements, routed.** The CC's addenda 02 to 05 to its 19:46Z direction add owner requirements, each
  dated and paraphrased, and CC mechanics around them. Under the CC's correction of 20:48Z, the mechanics are PROPOSALS.
  Each row names its responsible artifact and its acceptance receipt; this plan selects no strategy.

  | Addendum (owner time) | Owner requirement | CC mechanics (PROPOSAL) | Responsible artifact | Acceptance receipt |
  | --- | --- | --- | --- | --- |
  | 02 (15:54 ET) | compound the practice as a harness; a fine-tuned handbook per paper lane; live uses only practices that paper proved; runtime workers with full harnesses build PRs; the CC's local HTML pages as the owner channel | one loop per change; handbook changes under the preregistration standard; live inherits paper's code and handbook; worker routes per family | trading-cc's spec and each lane's handbook; horizon for the worker PR loop; the CC's generated pages (Decision 8) | one handbook PR per change with its receipt; each worker PR's invoke receipt; the pages' contrast and layout checks |
  | 03 (16:03 ET) | sell fast from our own end in every session, 24/5, and buy back when needed; capital in the highest-potential names with automatic leverage; written into the lanes' instruction files | our own exit as primary protection; re-entry; concentration; halt-aware rules (no added exposure in a halt, a per-symbol cap, a staged exit at the reopen) | trading-cc's spec; the trading lanes' instruction files and handbooks on NativeHorizonNY, by a reviewed PR | the spec's citations of the exchange halt rules and the broker's order-type and session documentation at a date; paper receipts |
  | 04 (16:20 ET) | different strategies per trading session, none forbidden by default, timed by evidence; catalyst overlaps traded in the session they land | a strategy set per session; session-aware leverage in the risk governor; catalyst overlap in any session | trading-cc's spec; each lane's handbook | the broker's margin and buying-power documentation cited at a date in the spec; per-session paper receipts |
  | 05 (16:23 ET) | factors tuned on historical data with compounding learning; each lane with its reason to exist; lanes for end-to-end and A/B tests, such as a fast-reaction Jev evaluation | the charter fields; test-role lanes; historical replay first, then paper confirmation; one historical store | each lane's handbook (its charter); trading-cc's move sheets; the backtesting engine the engine comparison picks | preregistered study receipts with held-out periods; one handbook PR per confirmed or failed change |
- **No order waits on a model inference** (the 18:09Z rule, as the CC's addendum-01 to its 19:46Z direction clarifies
  it at 19:52Z). The order path is:
  1. the live stream (the H1 hub);
  2. the seconds-level deterministic scanner;
  3. deterministic sizing and risk admission;
  4. the broker adapter.
- **Jev runs off the order path.** Jev is a model: TypeSafe's first System One model, which returns typed answers and
  probabilities (`typesafe-ai/skills` `65a39f39` (v0.5.7), `skills/typesafe-ai/SKILL.md:19-23`). A typed output fixes the
  interface; it does not make the classifier deterministic code. The CC's three earlier rulings listed Jev inside the
  fast path, and the addendum supersedes that wording:
  - **An off-path producer.** Jev, like any model, publishes completed, validated, immutable feature artifacts ahead of
    time. Each carries its source identity, `input_as_of`, `available_at`, `expires_at`, model, prompt and schema
    versions, a content hash and its validation receipt. `available_at` cannot precede the input's readiness, the
    answer, validation or publication. Jev goes live only after its three receipts.
  - **A frozen-artifact read.** At its frozen decision cutoff, the deterministic scanner or sizer reads an admitted
    artifact only when `available_at <= cutoff < expires_at`. It never calls, awaits, retries or polls Jev.
    - A missing, expired or invalid artifact takes the lane's deterministic no-feature rule, so no decision blocks on
      one.
    - A later artifact never applies backward.
    - Jev's latency (about 90 ms) then affects feature freshness, not order latency.
  - **Ownership.** The feature's acceptance belongs to `us-equities/judgment-features` (point-in-time judgments with
    `available_at`, `catalogs/landscape/planned-layers.json:25-27`). `agents-models-workers` only hosts the producer
    runtime and does not count as a second layer win.
  - **Conformance is unproved** until one named receipt, JEV-OFFPATH-FEATURE-ACCEPTANCE, exists. It must bind a numeric
    freshness and expiry policy (none is chosen yet) and the producer and reader pins. It must also show that features
    freeze before use, that a stale or failed producer cannot stall a decision, and that nothing leaks backward. The
    existing synthetic Jev receipts are plumbing only. Whether the features improve decisions stays OPEN under the
    preregistration standard, and the candidate keeps every gate. The co-op's RQ7 record of 2026-10-15 holds the full
    contract.
- **Where models work.** Models research and classify off this path. This restates the standing trading rule that models
  stay in research and deterministic code owns numeric, risk and order state (`blueprints/us-equities/AGENTS.md`, trading
  north star), and the trading repository's Authority section.
- **Why.** The CC's measured causes on 2026-10-15: utilization of 6.0% (A) and 8.1% (C), 0.18 to 0.21 orders a minute,
  and selection rounds of 6 to 10 minutes.
- **Engine row: OPEN.** On 2026-10-15 (18:16Z) the owner, through the CC, ended the paper lanes' gating role and allowed
  LEAN, paid if needed, where the evidence shows it fits an agent-seamless workflow.
  - The CC reopened the trading-engine row. The co-op runs a bounded first-hand comparison: LEAN with its IBKR and Alpaca
    brokerages, against NautilusTrader's official IB adapter and the current native port.
  - Its dimensions: a paired same-task agent run, adapter maintenance at pins, backtest-to-paper parity, IBKR-lane
    latency, and cost, QuantConnect's tiers included.
  - Its verdict is a named input. This row stays open until it lands.
  - No engine or trading profile installs before the verdict. The grand list's `research-runtime` profile (which adds
    LEAN) and `trading-nautilus` are bootstrap profiles, which recipe F9 retires on this distribution, and neither is an
    `install.sh` slot.
  - The verdict names the engine's install route (the trading lane's own environment), and only then does it install.
- **Brokers.**
  - IBKR: the high-frequency lane, today on NautilusTrader's official IB adapter (the backtesting-engine winner,
    2.0.0rc5), pending the engine comparison.
  - Alpaca: the alpaca-py route (the market-data-reference winner, v0.44.0) and the official Alpaca MCP server, where an
    agent surface is needed.
  - `us-equities/execution-broker` still has no winner; its nine survivors stay with the trading lane.
- **Market data.** Alongside alpaca-py, the market-data-reference winners are edgartools v5.58.0 (a 5.62 screen is in
  flight) and exchange-calendars 4.13.2.
  - The four carried survivors (databento-python, tiingo-python, arcticdb, massive client-python) stay with the trading
    lane.
  - A dedicated read-only market-data credential is an open owner item that unblocks the H1 hub and the scanner.
- **Authority.** The foundation installs and configures; it places no order. Paper operation follows
  `docs/paper-lane-policy.md` and the trading repository's lane rules. Runtime selections stay with the trading lane.

## Decision 5: runtime workers enter as their records say

| Worker | Record | On the new distribution |
| --- | --- | --- |
| Claude Code (headless, subagents, Workflows) | `foundation/native-clients` and `workers` winners; the practice skill | installed by its native installer, the plan's first row (stage C), labelled TRIAL until its layers are FINAL; the harness frameworks as TRIAL (Decisions 6 and 9) |
| Codex native SDK and lanes | `us-equities/agents-models-workers` and `foundation/agent-sdks` winners | installed by the plan's rows, labelled TRIAL until their layers are FINAL |
| Pi, OpenCode (`ns-run` profiles) | #1033 and `notes/runtime-profiles-20261012/`. Profiles remain trial; the W6 parallel-readers comparison is preregistered and not executed | TRIAL through the fence, with superpowers inside each worker profile (Decision 6) |
| Muse Code | [2026-10-14-muse-file-fence.md](2026-10-14-muse-file-fence.md) and its 2026-10-15 directory-grants amendment; a CC delta is pending | TRIAL through the fence, with superpowers through `.muse-plugin` inside the fence; no default promotion |
| Jev (TypeSafe SDK) | `candidate:typesafe-ai-skills` (adopted in the managed skills manifest at `65a39f39`, `docs/decisions/2026-09-25-skills-trial-and-usage.md:121`; its layer verdict is unpinned in `final-stack.json`, Decision 6) in `foundation/instructions-skills`; #1168; the CC's Jev rulings | a typed classifier off the order path that publishes frozen feature artifacts with `available_at` and `expires_at`, live after its three receipts, its conformance unproved until JEV-OFFPATH-FEATURE-ACCEPTANCE (Decision 4); the Python SDK `typesafe-sdk==0.7.2` (`typesafe-ai/typesafe-sdk-python@v0.7.2`, `docs/decisions/2026-10-05-typesafe-sdk-transport.md:9-11`) until the scored run ends; no skill framework |
| Harbor 0.24.0 | #1047 | container harness, as registered |

Defaults change only on a layer's convergence. The model-routes layer is F5's.

## Decision 6: the instructions-skills and memory deltas

- **ECC.** `affaan-m/ECC` is the instructions-skills winner, pinned at `dd6ee538`. The practice-references freshness run of
  2026-10-15 counts 1,114 commits on its default branch after the catalogued pin. The delta: test the changed mechanism
  at the new head.
- **Other skills candidates: already adopted, not pending.** The managed skills manifest
  (`adoption/skills/manifest.json` at `8053f14e7`) is the repository's adopted skill set, and stage C's
  `engineering-process-skills` row installs all of it except the held and native-plugin entries (`install.sh:284`,
  `install_skills.py --json` without `--only`; the installer skips those at `install_skills.py:226` and `:951-952`;
  today `agent-browser` is held and `claude-api` is a native plugin).
  Interim stage C did exactly that.
  - It already holds `typesafe-ai` at `65a39f39` (kept as the instructions-skills verdict winner,
    `docs/decisions/2026-09-25-skills-trial-and-usage.md:121`), two ECC skills, four `mattpocock/skills` and four
    `openai/skills` skills. Each entry carries its adoption record; none is a pending install.
  - What is missing is the layer's verdict pins: `final-stack.json` lists `typesafe-ai-skills` and `openai-skills`
    unpinned. The same delta adjudicates them with the carried survivor.
  - `openai/skills` is deprecated upstream (`README.md:1-2` at `49f948fa`, naming `openai/plugins` as the successor).
    That is evidence for the delta: its four installed skills stay until the delta rules, nothing new installs from it,
    and its successor enters only through its own screen (Decision 9).
  - A candidate outside the manifest installs only after its screen passes at a pin (`AGENTS.md:7` at `8053f14e7`).
- **Harness frameworks: two families, each with its full cycle, all TRIAL.** The owner asked for fully designed
  harness frameworks for the runtime workers (2026-10-15, 18:19Z), placed superpowers in the worker harnesses
  (19:19Z-19:20Z), and gave Claude sessions their own cycles too (19:22Z), all paraphrased.
  - **Runtime workers, per worker profile.**
    - Pi: its `.pi` folder or the #1033 profiles.
    - OpenCode: its `.opencode` folder or the #1033 profiles.
    - Muse Code: `.muse-plugin`, through the Muse fence.
    - Pin: #1033's `bb92a77741419a4ab5f06e711a283343f1ada0c3` (`tools/adoption/runtime_profiles.py:45-46` at
      `8053f14e7`). That is the commit of the release tag `v7.0.0` (annotated tag object `7f043e5e`; the GitHub compare
      reads identical).
  - **Claude Code sessions on NativeHorizonNY.**
    - superpowers through the official marketplace, `superpowers@claude-plugins-official`. That marketplace
      (`anthropics/claude-plugins-official` main `8f814f49`, 2026-10-15) pins the plugin at
      `5bf4e78011075bcfc0dc295f0724994cd123ee71`, release v6.4.1 (2026-09-19), two commits behind `v7.0.0`. The Claude
      Code arm therefore runs v6.4.1 while the worker arms run v7.0.0. Each comparison is within one harness, so the
      difference does not confound it.
    - Beyond it: the managed manifest's skills, which stage C already installs (above, skills CLI 1.7.0), and ECC at
      a pinned commit of its current head, which installs through its vendor's path only after its screen passes at
      that pin.
    - **Install scope: per project.** The role-assignment matrix (Decision 9) installs each framework per project,
      for the roles it suits: `claude plugin install <plugin>@<marketplace> --scope local` in each role's own
      checkout, so no shared settings file changes. The scopes come from Claude Code 2.1.301's help and have not been
      exercised yet; each role's `system/init` check verifies the result.
    - Nothing installs at user scope, so the 19:12Z direction's ruling 3 (per profile or per project, never user scope)
      stands. Addendum-02 ruling 1 is what brings the frameworks to Claude Code sessions on NativeHorizonNY (superpowers
      from the official marketplace, pinned), superseding addendum-01's exclusion of Claude Code. Addendum-04 limits
      each framework to the roles it suits. The fenced sessions stay clean by their fences, and NativeStack2604 gets no
      install.
  - Every framework is installed with one check and a recorded inverse, its plugin or skill uninstall.
  - **Fenced sessions stay clean through their existing fences, not by uninstalling.** These are the account traders
    (headless `claude -p` with tool and settings fences), the blind judges and reviewers, and the paired-run arms.
    - The plugin's SessionStart hook (`hooks/hooks.json` at `v7.0.0`, matcher `startup|clear|compact`) injects into
      every session where the plugin is enabled. So after stage E, each fence is checked: its `system/init` record must
      list no framework plugin or skill.
    - No trading session gets a framework before its own paired check. Jev takes no skill framework. NativeStack2604 is
      unchanged.
  - **Decision.** A preregistered paired same-task comparison inside each harness: Claude Code, Pi, OpenCode and Muse
    Code. One arm runs with the framework and the control arm disables it per project, on a sealed task set, in the
    existing harnesses (promptfoo or the skill-creator benchmark, blind judge plus exact checks).
    - A framework becomes a default only on the layer's multi-angle convergence, which includes the practice skill's
      `orchestration-frameworks` overturn rule (ahead on quality at equal or lower cost).
    - The readiness trigger is the TRIAL installs plus the sealed task set and, for a GPT arm, the new host's own
      gateway (below).
    - **GPT arms wait for the new host's gateway.** The Pi and OpenCode GPT profiles send their requests to the gateway
      at 127.0.0.1:21128 (`tools/adoption/runtime_profiles.py:44`, used at `:308-309` and `:321-322`, at
      `8053f14e7`), and `tools/research/gpt_researcher.sh:31` does the same. On the shared network that is
      NativeStack2604's live gateway.
      - So a GPT arm, or any run through those helpers, starts only after stage S's activation and listener-ownership
        check have proved the new host's own gateway on its own port.
      - It runs through that gateway, at the port the helpers read from the host value file (Decision 3).
      - The Claude arms use the Anthropic provider directly and carry no gateway precondition.
  - Invoke tracking (Decision 8) covers every installed framework skill per lane.
  - The other harness repositories in the practice-reference catalog enter only through stage H's screens (Decision 9);
    until screened, they stay references.
- **Memory.** The durable-memory winner is ai-memory (2.6.6 live), with Hindsight deployed as the research-memory unit
  and recorded as its alternate.
  - The new distribution installs both as recorded.
  - A colliding candidate (for example Graphiti) reopens the layer only on measured evidence. The layer's eight carried
    survivors are its delta: five from the 2026-09-29 sweep and three carried from the sweep before it.

## Decision 7: disk Z and CPU cleanup

The CC's Z: cleanup and CPU disposition plans of 2026-10-15 (private, by name) are plans only.

- The Z: plan never targets the two live disks.
- The CPU plan keeps every trading-adjacent process to the boundary.
- Both are executed by the CC after the boundary, through its own guarded steps; this lane executes neither.

## Decision 8: the native-clients re-pin and invoke tracking

- **Re-pin, a named T1 row.** `final-stack.json` pins `foundation/native-clients` at claude-code 2.1.295 (its run pin).
  NativeStack2604's sessions moved to 2.1.301 on 2026-10-15; NativeHorizonNY's native installer gave 2.1.300 that day,
  and it updates by the native installer after the sign-ins (stage E). The routes are #1128 (the floor and run pin at
  2.1.300), #1171 (the practice skill's currency at 2.1.300), and the practice skill's re-pin to 2.1.301 by the CC's
  19:46Z ruling 4, which cc-native-practice carries.
- **Invoke tracking from the first lane.** Each lane on NativeHorizonNY runs `tools/skill-usage/skill_usage.py` from its
  first session. An installed skill with zero calls is a wiring defect to fix, or a role to retire, per the adoption
  practice.
- **The owner's view.** The CC's status page shows each agent's and worker's installed skills, labelled FINAL, TRIAL or
  GAP, measured on NativeStack2604 and planned or installed on NativeHorizonNY (the CC's 19:12Z ruling 6). The
  per-layer half of that view is generated by #1175 from `final-stack.json`.
  - A PROPOSAL, like the other mechanics of that direction's addenda (Decision 4): the CC's 19:46Z addendum-02, ruling
    5, has its local pages generated from records, never hand-typed. They pass the contrast and layout checks, end the
    browser session on about:blank, show the skills by upstream source repository, and link the starred-repositories
    manifest.
  - The measured NativeStack2604 half has no generator yet; it is a named gap for the CC's pages.

## Decision 9: the harness landscape (stage H) and the role-assignment matrix

The owner asked, through the CC at 19:59Z, for the full landscape of converged harness layers, installed and set up,
not only superpowers. The CC's addendum-03 to its 19:12Z direction sets the rule.

- **Scope: every harness layer.**
  - `instructions-skills` (frameworks and skill packs), `workers`, `native-clients`, `agent-sdks`, `mcp-surfaces`;
  - `token-efficiency`, `durable-memory`, `code-navigation`, `semantic-rag`, `document-retrieval`;
  - `isolation`, `observation-inference`, `quality-evaluation`, `scheduling-supervision`;
  - `git-github-automation`, `ci-supply-chain`, `web-research`, `model-routes`;
  - and the practice skill's `orchestration-frameworks` slot.
- **PROPOSAL rows, routed to the protocol** (the CC's addendum-10, after the owner's direction of 17:54 ET):
  - the god view and orchestration through each platform's own MCP servers and CLIs, CLI first, each pinned with an
    install receipt and an inverse (requirements R2 and R3: cc-native-practice's rows and the co-op's screens);
  - a hygiene sweep with receipts in the self-maintenance loop (R4).
  - Stage H installs each only when its row converges.
- **Named input: the co-op's screen tables,** one per layer, over its full candidate set (the carried candidates in
  `final-stack.json` and the catalogs). A GAP layer gets its sweep first. An unscreened candidate never installs.
- **Per model family** (the CC's addenda 05 and 06). The screens run for each family's own stack: Anthropic (Claude
  Code, the Agent SDK, API slots), OpenAI (Codex and the GPT runtimes through OmniRoute), Meta (Muse Code through its
  fence) and the research stack (DeerFlow, GPT Researcher). A family's runtime workers include its fully harnessed SDK
  and framework workers, not only its native client. Role assignment applies inside each family.
- **Each candidate that passes its screen at a pin** installs through its vendor's own path, with:
  - one check and a recorded inverse;
  - invoke wiring, so its use is measured per lane (Decision 8);
  - a label: FINAL only when its layer converged, TRIAL otherwise. Defaults come only from convergence, which now
    includes measured runs on NativeHorizonNY.
- **Order.** Stage H follows stage C.
  - A client-level install (a Claude Code or Codex plugin, a skill pack) follows stage D. The client-configuration tool
    renders `enabledPlugins` from its closed-world map (`tools/adoption/new_wsl_client_config.py:533` at
    `8053f14e7`), so each enablement is recorded as a delta to that apply, and the map gains its rows before any
    re-apply.
  - A candidate that starts a service follows the port and isolation rules of Decisions 2 and 3.
  - **A candidate that dials the gateway runs only after stage S.** The GPT runtimes and the SDK and framework workers
    dial the gateway at 127.0.0.1:21128: DeerFlow's installed configuration (`config/deer-flow-config.yaml:10`,
    installed by `install.sh:975`) and the OpenHands SDK worker's job template (`config/openhands-job.json:4`,
    `install.sh:947`), at `8053f14e7`.
    - Installing them in stage H is fine, but no stage H run, trial or comparison starts before stage S has proved the
      new host's own gateway through the listener-ownership check.
    - They then reach the gateway at its per-row port, which their configurations read from the host value file
      (Decision 3, part 1).
    - The check is the same ownership check, keyed on the dialled port, run before each such run.
    - The same gate holds for any stage H run before stage E that would dial another plan service port: ai-memory's
      29374 or the collector's 21317-21318 (Decision 3, part 1). Stage H precedes E, so the stage-E rule alone would
      leave those runs ungated.
- NativeStack2604 gets no install from this stage.

### The role-assignment matrix

The owner answered a note on the start-up cost of enabling every framework (through the CC, 20:04Z): install the full
landscape, but enable each framework only for the sessions and agents it suits, as context engineering. The CC's
addendum-04 to its 19:12Z direction makes that the general rule.

- **Install every screened candidate; enable by role.** Each role gets only the frameworks and skills its job uses.
  Frameworks that conflict, such as two packs that both inject SessionStart text, never share a role's profile.
- **The matrix fields below are a PROPOSAL** (the CC's addendum-04): the start-up context cost, the plain control
  profile and the overturn rule. They are routed to the protocol over `instructions-skills` and `token-efficiency`, and
  they become practice only when their upstream sources and measured runs agree. The owner's requirement is fixed:
  each framework only for the sessions and agents it suits.
- **The matrix is generated, versioned and cited.** A generator writes it from the co-op's screen tables, which add each
  candidate's suited roles and start-up context cost, and from the per-role measurements below. Each stage H receipt
  cites the matrix version it applied. The generator and the first version are a named gap, to land by pull request.
- **Start-up context cost.** For each role, the matrix records the skill descriptions and start-up instructions, in
  tokens, measured at session start against the role's plain control profile.
- **Overturn rule: measured outcome per role.** Each role keeps a plain control profile for the paired comparisons. A
  framework stays on for a role only while that role's measured runs and invoke rates support it (zero calls is a
  wiring defect or a retirement, Decision 8).
- **Token saving and context rot** are measured on the same matrix: start-up tokens, compactions and relaunches per
  role.

| Role | Where its enablement lives | Plain control profile | Check |
| --- | --- | --- | --- |
| Builder (Claude Code builder sessions and subagents, Codex build lanes) | per project, installed in the builder's worktree (`claude plugin install <plugin>@<marketplace> --scope local`). Per Codex lane, each lane gets its own `CODEX_HOME`, which relocates Codex's state, configuration and plugins (`openai/codex` `rust-v0.162.1`, `codex-rs/utils/home-dir/src/lib.rs:6-13`), and `codex plugin add` runs inside that home: with a shared home it enables the plugin user-wide, as the local review reproduced with codex-cli 0.162.1 | the same harness with no framework enabled; for Codex, a lane home with no framework | `system/init`, or `codex plugin list` in each lane home, matches the matrix for both arms; invoke tracking |
| Reviewer and auditor, outside the fenced review sessions | per project | the same | the same |
| Researcher (research lanes and workers) | per project or per research profile | the same | the same |
| The CC and the co-op | per project, in their own checkouts | the same | the same |
| Runtime workers: Pi, OpenCode, Muse Code | per worker profile: `.pi`, `.opencode`, `.muse-plugin` through the Muse fence | the worker's plain profile | the profile's listing; invoke tracking |
| Fenced sessions: account traders (headless `claude -p`), blind judges and reviewers, paired-run control arms | their existing tool and settings fences | always plain | each fence's `system/init` lists no framework plugin or skill |
| Jev | none | none: a typed classifier takes no framework | none |

## Decision 10: GitHub access (stage G)

The owner asked, through the CC at 20:41Z, for full access at every layer on the new distribution, with GitHub
automation at the highest quality. The CC's addendum-09 to its 19:12Z direction makes it a GitHub access layer, kept
as code in horizon as names and scopes only, never a secret value. It builds on
[2026-09-22-github-automation-closure.md](2026-09-22-github-automation-closure.md),
[2026-10-02-github-automation-practice.md](2026-10-02-github-automation-practice.md),
[2026-10-09-review-verdict-app-identity.md](2026-10-09-review-verdict-app-identity.md) and
[2026-10-10-retire-in-github-claude-review.md](2026-10-10-retire-in-github-claude-review.md).

- **Named input: api-actions' access manifest in horizon.** It lists each identity's scopes, the repositories it can
  reach and its token lifetime, plus each repository's required checks. The manifest and api-actions' decision record
  are the inputs that turn the PROPOSALS below into practice, through the protocol, citing GitHub's documentation.
- **The owner's commands, cited at the installed client.** gh 2.102.0 (`cli/cli` `v2.102.0`, `fc4b137c`):
  - `gh auth login --web` signs in with a one-time OAuth device code (`pkg/cmd/auth/login/login.go:153-154`;
    `internal/authflow/flow.go:27` and `:48`);
  - `gh auth setup-git` makes gh git's credential helper (`pkg/cmd/auth/setupgit/setupgit.go:35-37`);
  - `gh ssh-key add` registers a key with the account (`pkg/cmd/ssh-key/add/add.go:34-35`).
- **PROPOSALS, routed to the protocol** (the `secrets-credentials` and `git-github-automation` layers), with the
  manifest and api-actions' record as inputs:
  - the identity rules: a new SSH key generated on the new host, with no key file copied from NativeStack2604; the
    no-reply commit identity, with no `-c user.email` override; signed commits where a repository requires them;
  - the automation identities: the review-verdict App identity posting the lander's statuses and making its merges
    (its identity per [2026-10-09-review-verdict-app-identity.md](2026-10-09-review-verdict-app-identity.md));
    builders with contents on their own branches only, main being protected by each repository's ruleset; readers
    with read access only; short-lived tokens and their lifetimes.
- **Repositories and rulesets, cited.** GitHub's "About rulesets" (docs.github.com, read 2026-10-15T21:38Z) makes
  rulesets available in public repositories on GitHub Free and GitHub Free for organizations, and in private
  repositories only on GitHub Pro, Team or Enterprise Cloud.
  - native-agent-stack is public, with the organisation's rulesets and merge queue. GitHub's "Managing a merge queue"
    (read the same day) offers merge queues in public organisation repositories, and in private ones only on
    Enterprise Cloud.
  - us-equities-trading and horizon (after its transfer) are private repositories on the owner's account, which
    reports plan "pro" (`gh api user`). us-equities-trading already carries an active ruleset; the CC measured both on
    2026-10-15 (addendum-08). Each can therefore carry a ruleset that protects main.
  - ecosystem-records is private on the organisation's free plan, so it has no ruleset, and it stays local-first.
  - The hooks (gitleaks on pre-commit and pre-push; a direct push to main refused) are installed in every clone.
- **Runners and Actions.** Hosted CI stays optional for horizon and required as today for native-agent-stack. The
  self-hosted runner pool moves by its own sheet, and Actions secrets stay main-only.
- **The access audit** joins the self-maintenance loop: token expiries, scopes against the manifest, unused
  identities, and any commit on a main branch that the lander did not land.
- **The owner's steps** are the ones api-actions' access manifest lists, with its decision record, and no agent
  performs them. The stage G rows under Owner acts (gh sign-in, the SSH key, the App, any repository secret) are
  PROPOSAL rows that point to that manifest. This plan sets no identity or key default of its own.

## The full stack

The new distribution gets every installed row of the install plan, in the stage order above. That is the definitive
manifest's foundation set: 63 rows, 60 of them by the default run. It also gets the TRIAL rows and the runtime workers of
Decisions 5 and 6, and stage H's screened harness candidates (Decision 9). No engine or trading profile installs before
the engine verdict (Decision 4).

- Rows the plan marks measurement-only or named-only (Loki and Grafana; the two local-model rows) install only when
  their measurement or service runs.
- Each layer's winner is cross-checked against `final-stack.json` as F1 lands.

## Owner acts

Each is the owner's own act and comes with its exact route. None is needed before stage E.

| Act | When | Exact route |
| --- | --- | --- |
| Name and disk | before stage R (decided here; the owner may object) | `NativeHorizonNY` at `Z:\WSL\NativeHorizonNY`; the rehearsal uses a throwaway name in its own `Z:\WSL\<name>` folder |
| Codex sign-in | stage E | in a terminal on the new distribution (`wsl.exe -d NativeHorizonNY`, or the Windows Terminal profile that WSL creates): `codex login`, then the browser sign-in. Its callback listens on `localhost:1455` (`openai/codex` `rust-v0.162.1`, `codex-rs/login/src/server.rs:78`), so no Codex sign-in runs on NativeStack2604 at the same time |
| Claude Code sign-in | stage E, after Codex (recipe F9) | in the same terminal: `claude`, then the browser sign-in it opens |
| Gateway provider sign-in | stage S, after the gateway starts on its own ports and before the after-sign-in checks that need it; the client sign-ins do not provision it | in the same terminal, only when the account is absent: `~/.local/bin/omniroute --base-url http://127.0.0.1:<the gateway's own port> oauth start --provider codex --no-browser`, then the browser sign-in (`evidence/artifacts/new-wsl-install-plan-20261002/README.md:553-554`; `diegosouzapw/OmniRoute` `v3.8.51`, `docs/guides/REMOTE-MODE.md:166` for `--no-browser`). Codex's OAuth returns to a fixed `localhost:1455` (`REMOTE-MODE.md:196-205`), the port `codex login` also listens on (`openai/codex` `rust-v0.162.1`, `codex-rs/login/src/server.rs:78`). On the shared network, no sign-in may run on NativeStack2604 at the same time |
| GitHub sign-in | stage G; a PROPOSAL row, as the access manifest lists the step | `gh auth login --hostname github.com --git-protocol https --web` (a one-time device code; gh 2.102.0), then `gh auth setup-git` for git's credential helper |
| SSH key | stage G; a PROPOSAL row, as the access manifest lists the step | a new key generated on the new host and registered by the owner (`gh ssh-key add`); no key file is copied from NativeStack2604 |
| The review-verdict App | stage G; a PROPOSAL row, as the access manifest lists the step | the owner approves or installs it on each repository the access manifest lists |
| Repository secrets | stage G, only if the manifest names one; a PROPOSAL row, as the access manifest lists the step | the owner sets each by name, per the key practice (Actions secrets main-only) |
| Keys, by name only | stage F, per the CC's list of key names | `tools/credentials/open_credential_terminal.sh <entry-id>`, from the owner's own terminal on the new distribution; paper pairs with `--probe` |
| IBKR session | when the IBKR lane moves | the gateway login with its second factor, per trading-cc's move sheet |
| Purchases | none now | only if a verdict shows fit: the QuantConnect tier the engine comparison names, or the TradingView plan a TRIAL needs, each with its price |
| Live trading | not now: owner-gated (Decision 4) | the owner opens a live order path with written limits and enters the live credentials, after paper evidence under the same code |

## The boundary

One receipt that the owner confirms. The CC set these five conditions in its 18:09Z direction of 2026-10-15 and
restated condition 1 in that direction's addendum-02 (18:30Z). On the new distribution:

1. The install plan's `accept.sh` reports every selected row ok in all three stages (post-install, service health,
   after sign-in) at a landed main commit. The addendum's restatement replaced `bootstrap --check`, because this
   distribution runs no bootstrap profile (recipe F9).
   - **How the receipt reads it, per row** (for the CC to confirm). Rows declare different stages in `install-plan.json`
     (`owners[].acceptance`, keyed by stage): `git` declares only `post_install`, and `memory-owner` declares
     `post_install` and `service_health`.
     - So each selected row must pass every acceptance entry it declares, each in its own stage.
     - The receipt reads `accept.sh`'s per-row lines, not its exit status. The script prints `skipped` for a stage a row
       does not declare and `(78)` for a pending check, and sets its exit status only on another non-zero result
       (`accept.sh:42`, `:57-69` and its final `exit "$failed"`, at `8053f14e7`), so it can exit 0 with nothing proven.
     - For a declared entry, `skipped`, pending, or a check that cannot run is never ok, and it blocks the receipt. A
       `skipped` line for a stage the row does not declare is expected and decides nothing.
2. The owner has signed in both clients, and the client configuration is applied with its receipt. Its GitHub part
   (the CC's addendum-09 to its 19:12Z direction) names a single input: the owner's stage G steps as listed in
   api-actions' access manifest, with its decision record. This plan sets no identity or key default of its own
   (Decision 10).
3. The CC tooling runs: the tracker, the god view and hcom.
4. Records are restored from GitHub and the private records remote.
5. trading-cc has stopped the first moved lane on NativeStack2604 and relaunched it on the new distribution.

Command-center authority moves only after the owner confirms the receipt, and the CC then moves to NativeHorizonNY (the
CC's 19:46Z ruling 5). Account C moves like the other paper lanes (ruling 2).

## Verification boundary

Source review and four read-only checks at `8053f14e7`, each with exit 0:

- `tools/adoption/new_wsl_client_config.py --check`;
- `scripts/new_host_grand_list.py --check`;
- `scripts/final_stack.py --check`;
- `evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py`: 84 rows (63 installed, 60 of them by the default run;
  2 measurement-only; 19 not installed); 193 commands and 113 acceptance entries agree with the scripts.

Also read: the practice-references freshness report of 2026-10-15 (Actions run 38695909735, report-only).

Executed since, on 2026-10-15 (receipts in the lane's private run directory, by name):

- **Stage R passed and was removed.** The rehearsal ran P1-P3, W1-W7 and F1-F3, and was removed at 18:37:42Z with
  interop intact.
  - F3's container proof was owed at F3, because no engine was installed yet. It returned after F4, F5 and the plan's
    container-engine row: `docker --context rootless info` listed `name=rootless`, and `hello-world` printed
    `Hello from Docker!`, each with exit 0 (Docker 29.8.2). Stage A followed the same order.
- **Stage A passed through F8.** W5's paired isolation proof passed, with distinct cgroup namespaces and the 2604
  baseline unchanged. The hostname is `nativehorizonny` and the time zone America/New_York.
- **After the restart (Windows boot 18:55:12Z), F2-F5 passed.** They ran inside a capped user scope, together with the
  plan's container-engine row (Docker 29.8.2, rootless).
  - NativeStack2604's CPU pressure read `some avg10` 0.00 before and 0.16 after.
- **Interim stage C ran, 19:09Z-19:25Z, and is stopped.** Of its 63 rows, 55 exited 0, seven were skipped as listed in
  Decision 2, and `command-output` exited 1. Rerun with `RTK_SUPPRESS_HOOK_WARNING=1` (the variable rtk reads to
  suppress its missing-hook warning: `rtk-ai/rtk` `e001f773` (v0.51.0), `src/core/config.rs:298-313`), the fix the
  install-nostart lane carries, it exited 0 and trusted the Codex hook.
- **These corrections are documentation.** This record ships no executable change, so it carries no fail-first test of
  its own. The executable regressions belong to the implementing lanes, and each is linked here, fail-before and
  pass-after, when it lands. They are distinct from documentation and native-execution evidence. The install-nostart
  lane's fail-first tests cover:
  - the start inventory, including the `--only` dependency dispatch and the engine path's package and rootless setup;
  - transient starts;
  - per-listener ports and the dialled-port ownership check, with the negative fixtures (the closed alerting port,
    a foreign listener);
  - the declared-stage reading of `accept.sh`.
  Framework isolation per role (Decision 9) gets its own check when the role-assignment matrix lands.

## Sources

- Layer-resolution protocol: [2026-10-11-layer-resolution-protocol.md](2026-10-11-layer-resolution-protocol.md).
- Claude Code native practice:
  - `.claude/skills/claude-native-practice/reference/slots.md` (client 2.1.295, checked 2026-10-09);
  - its currency PR #1171 at 2.1.300.
- Claude Code: `anthropics/claude-code` `CHANGELOG.md` at `94506ff0`. npm dist-tags on 2026-10-15: latest 2.1.300, next
  2.1.301, stable 2.1.292 when this plan was drafted; at 20:00:47Z, latest and next 2.1.301, stable 2.1.292 (the
  co-op's capture).
- WSL:
  - Microsoft, [WSL 3.0.1 release](https://github.com/microsoft/WSL/releases/tag/3.0.1), the first stable release with
    distribution cgroup isolation (PR #40519) and namespaces (PR #41512), as the recipe cites;
  - [Basic commands for WSL](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) (`--install --from-file`,
    `--terminate`, `--unregister`, `-l -v`);
  - host WSL 3.0.3.0, PowerShell 7.6.7.
- systemd at `v259` (NativeHorizonNY runs systemd 259.5-0ubuntu3.4):
  - [`man/systemd.resource-control.xml`](https://github.com/systemd/systemd/blob/v259/man/systemd.resource-control.xml)
    (`CPUQuota=`, `MemoryMax=`, `CPUWeight=`);
  - [`man/systemd-run.xml`](https://github.com/systemd/systemd/blob/v259/man/systemd-run.xml) (`--user --scope`);
  - [`man/systemctl.xml`](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml) (`set-property --runtime`;
    `enable` against `--now`).
- Linux at `v6.18` (the WSL kernel is 6.18.54.1):
  [`Documentation/admin-guide/cgroup-v2.rst`](https://github.com/torvalds/linux/blob/v6.18/Documentation/admin-guide/cgroup-v2.rst)
  (`cpu.max`, `cpu.weight`, `cpu.idle`, `memory.max`, PSI `cpu.pressure`).
- Ubuntu 26.04.1 WSL image: sha256 `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104`, Canonical's signed
  `SHA256SUMS`, checked in P1. Codex: codex-cli 0.162.1, from the plan's native-installer row, which pins no version.
- superpowers: [obra/superpowers `README.md` at `v7.0.0`](https://github.com/obra/superpowers/blob/v7.0.0/README.md),
  "Installation" (an install route per harness), and the release
  [v7.0.0](https://github.com/obra/superpowers/releases/tag/v7.0.0), published 2026-10-10T00:28:58Z (GitHub
  releases API); its `RELEASE-NOTES.md:3` at the tag dates the release 2026-10-09.
- TypeSafe: `typesafe-ai/skills` at `65a39f393687675ce170e6094757de20370365b9` (tag v0.5.7),
  `skills/typesafe-ai/SKILL.md:19-23` (Jev is TypeSafe's first System One model).
- MinerU 4.0.10, the installed client on both distributions: `mineru server status --json` (`socket_path`,
  `tcp.enabled`), read on 2026-10-15.
- openai/skills `README.md:1-2` at `49f948faa9258a0c61caceaf225e179651397431`: deprecated, with openai/plugins as its
  successor.
- Plugin scopes, from the installed clients' help on 2026-10-15: Claude Code 2.1.301 `claude plugin install`, `enable`
  and `disable` (`--scope user|project|local`); codex-cli 0.162.1 `codex plugin add`.
