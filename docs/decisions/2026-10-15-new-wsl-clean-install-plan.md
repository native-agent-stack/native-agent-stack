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
  - one paper lane kept on NativeStack2604 and everything else handed over;
  - a plan to clean up disk Z and the processes occupying the CPU.
- **18:05Z and 18:07Z, to the CC:** account C stays on NativeStack2604. The new architecture should give the fastest
  reaction, with Jev and related repositories, instead of selection rounds of several minutes.
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

The CC recorded these in its direction records of 2026-10-15 (18:09Z and 19:12Z, each with its addenda) and its
handover set of the same day. These are private records, cited by name only.

| Role | Owner of it |
| --- | --- |
| The new-distribution build | this lane |
| Everything live on NativeStack2604 until the boundary | the CC |
| Moving accounts A, B and the IBKR lane, by per-lane move sheets with one writer per account | trading-cc |

The owner's lists of tools are leads under the protocol, not selections.

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
  - the trading lane's fast-path work (the H1 stream hub, scanner v1, the Jev classifier path) in the trading repository.

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
  per-layer overrides where this record or a named lane owns the next action.

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
| `foundation/model-routes` | unswept | none | 0 | 0 | F5 (Codex lane) sweeps it; its output is a named input |
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
| `us-equities/catalysts-sentiment` | unswept | none | 0 | 0 | initial sweep scoped to the gap |
| `us-equities/data-quality-orchestration` | reopened | dagu, data-pandera | 1 | 9 | adjudicate 1 carried survivor; E2E and invoke evidence (FINAL 3-4) |
| `us-equities/evaluation-experiments` | reopened | foundation-agent-retrieval-bench, inspect-ai, data-mlflow | 0 | 10 | E2E and invoke evidence (FINAL 3-4) |
| `us-equities/execution-broker` | no-winner | none | 9 | 1 | trading lane: adjudicate its survivors after the engine comparison |
| `us-equities/identity-provenance` | reopened | data-dvc | 2 | 5 | adjudicate 2 carried survivors; E2E and invoke evidence (FINAL 3-4) |
| `us-equities/judgment-features` | unswept | none | 0 | 0 | initial sweep scoped to the gap |
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
| GitHub automation | git-github-automation, ci-supply-chain | stage C rows (worktrunk, gh, difftastic, zizmor, syft, actionlint) |
| Models | model-routes (GAP, unswept), agent-sdks; Muse, OpenAI through OmniRoute, the Anthropic API | Decision 5; the `gpt-gateway` row (Decision 3); F5 sweeps model-routes |

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
- **A new repository: not now.** Every stage below runs from files already on main, with their checks. The kit was the
  last new-repository attempt, and it stalled before any host use.
  - Revisit if the boundary run shows the new distribution needs a host-private artifact that the public repository's
    privacy rules keep out.
  - The private records remote of the continuity design is the place for private state, not a new code repository.

## Decision 2: the plan binds to generated sources, not to a hand-written tool list

| Stage | Source | Check | Named inputs before it runs |
| --- | --- | --- | --- |
| R. Rehearsal | recipe R1 on a throwaway name, P1-P3, W1-W7 and F1-F3, then its removal | R1's proofs; the interop check after `--unregister` | the host isolation rules below |
| A. Windows side and first boot | recipe P1-P3, W1-W7 and F1-F8 for the real name; `adoption/templates/wsl/` | the recipe's proofs and the stage-1 receipt | R removed with every proof held |
| C. Stage 2: the install plan, the clients first (`install.sh` installs Claude Code and Codex by their native installers before the other rows) | recipe F9; `evidence/artifacts/new-wsl-install-plan-20261002/` (`install.sh`, `accept.sh`) | `check_plan.py`; the post-install stage of `accept.sh` | the slice caps below; a no-start install path in the living plan (below); the gateway's composition tarball (below); F1's run pins as they land |
| D. Client configuration | recipe F9: `tools/adoption/new_wsl_client_config.py --apply --host <host>` | `--check`; the apply receipt | the template-behind rows of the [reconciliation record](2026-10-15-claude-host-config-reconciliation.md); the memory-owner row (its executable); the per-row port change (the collector port, Decision 3) |
| E. Sign-ins | recipe F9: `codex login`, then `claude`, by hand | the after-sign-in checks of `accept.sh` that need no service | the owner: credentials and sign-ins are the owner's |
| S. Services | the plan's service-health stage, then the after-sign-in checks that need a service | `accept.sh --stage service_health`; `accept.sh --only <slot> --stage after_sign_in` for the eight rows whose check needs `omniroute.service` (mcp-inspector, grafana, inspect-ai, promptfoo, cross-family-review, gpt-gateway, agent-runtime-worker, lm-program-optimization) | the per-row port gap below, closed |
| F. Records and lanes | GitHub clones; the continuity design's private records remote | the boundary receipt | the CC's handover index; trading-cc's move sheets |

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
- **Interim stage C.** Until the no-start mode and the per-row ports land (Decision 3), stage C runs
  `install.sh --only <slot>` in plan order for the rows whose install starts no service. It skips seven:
  - `memory-owner`: it starts ai-memory on 29374, NativeStack2604's live memory owner, and points Codex hooks at
    `127.0.0.1:29374` (`install.sh:453-472` at `8053f14e7`), which on the shared network would write into the live
    store. Unregistering the new distribution cannot undo such writes.
  - `local-model-server`: it enables Ollama for boot on 21434.
  - `dagu`: its installer runs with `--service yes`.
  - `gpt-gateway`: it needs the composition tarball.
  - `container-engine`: already installed at F3.
  - `embedding-model` and `local-generation-model`: named-only.
  - After each row, a guard reads the listeners owned by the new distribution's own processes (`sudo ss -ltnp`, lines
    with `users:`). It stops the run if one is still new 5 s after the row ends.
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
- **Shared network, permanently.** WSL 2 distributions share one network namespace, and `.wslconfig` sets mirrored
  networking (recipe, host-wide rules; `adoption/platforms/linux-wsl2.md`, "Listeners and ports"). Account C stays on
  NativeStack2604, so both distributions keep running, and every listener competes for the same ports for good.
  - Measured on 2026-10-15 (`ss -ltnH` on NativeStack2604, 156 listening TCP ports): 14 of the 15 ports that the install
    plan's rows and the F8 host template name are already bound. They are 21080 (dagu), 21090 (prometheus), 21093
    (alerting), 21128 (gpt-gateway), 21300 and 21396 (loki), 21301 (grafana), 21318, 21333 and 21888 (the collector),
    21808 (session-analytics), 29374 (memory-owner) and the host template's 21633 and 28231. Only 21434 (the model
    server) is free.
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
    renderer. The proposed change is one port parameter per service row, read from the host value file and rendered by
    the plan's own renderer.
  - **Named gap, part 2: a no-start path.** The installer starts services as it installs: `systemctl --user enable
    --now` for ai-memory (`install.sh:466-467` at `8053f14e7`, port 29374, which is bound), Ollama (`:739`) and Docker
    (`:852`), and Dagu's installer runs with `--service yes`. It has no option to install without starting.
    - The proposed change is a no-start mode of `install.sh`. Units are installed and reloaded but neither enabled nor
      started; enabling alone would start them at the next boot through linger. Dagu's installer gets its no-service
      mode. The change is covered by `check_plan.py` and a fail-first test.
    - Parts 1 and 2 are one dispatched Codex lane (install-nostart). Its landing closes the CC read's P1-1 and the
      local review's P1-2.
    - Until both parts land, stage C runs only `install.sh --only <slot>` for the rows whose install starts no service.
      The rows that start a service wait.
  - **Gateway input.** The default `gpt-gateway` row needs the prebuilt composition tarball with its recorded size and
    digest (`OMNIROUTE_COMPOSITION_TARBALL`, `install.sh:928` at `8053f14e7`). Neither the checkout nor an earlier stage supplies it.
    Before that row runs, the tarball is copied from NativeStack2604's handover staging and its digest is checked;
    without it, the row waits.
  - Which services account C depends on comes from trading-cc's sheet for C.
- **Lanes.** They move under trading-cc's move sheets, in its order: A, then B, then IBKR.
  - Each move has a STOP-HERE receipt on NativeStack2604 before it starts on the new distribution, so every paper
    account has one writer.
  - Which paper lane stays on NativeStack2604 was the owner's call: account C.
- **CPU and memory.** WSL 3.0.1 and later give each distribution its own cgroup namespace (recipe; host WSL 3.0.3.0).
  - Idle class inside the new distribution yields only to its own processes, not to NativeStack2604's lanes. Account C
    trades in regular hours, after hours and overnight.
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
    claim that the step did not take from account C has a measurement.
- **Disks.** No command touches NativeStack2604's disk (`Z:\WSL\NativeStack2604\ext4.vhdx`), the swap disk
  (`Z:\wsl-swap\swap.vhdx`) or NativeStack2604's state roots.
  - The recipe's host-wide rules apply: no `.wslconfig` change, no `wsl --update`, never `wsl --shutdown`, and no change
    to the default distribution.
- **Inverse.** `wsl --terminate NativeHorizonNY`, then `wsl --unregister NativeHorizonNY`, which deletes the new disk,
  followed by the recipe's interop proof on NativeStack2604. Any export happens before the unregister.
- **Credentials.** None move. The owner re-enters keys on the new distribution. Broker credentials appear there only
  when a lane moves.

## Decision 4: trading architecture, first design row: no model in the order hot path

- **The row.** The fast path is:
  1. the live stream (the H1 hub);
  2. the seconds-level deterministic scanner;
  3. Jev as a typed classifier (about 90 ms), live only after its three receipts;
  4. deterministic sizing and risk admission;
  5. the broker adapter.
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
| Claude Code (headless, subagents, Workflows) | `foundation/native-clients` and `workers` winners; the practice skill | default, through its native installer, the plan's first row (stage C); the harness frameworks as TRIAL (Decision 6) |
| Codex native SDK and lanes | `us-equities/agents-models-workers` and `foundation/agent-sdks` winners | default |
| Pi, OpenCode (`ns-run` profiles) | #1033 and `notes/runtime-profiles-20261012/`. Profiles remain trial; the W6 parallel-readers comparison is preregistered and not executed | TRIAL through the fence, with superpowers inside each worker profile (Decision 6) |
| Muse Code | [2026-10-14-muse-file-fence.md](2026-10-14-muse-file-fence.md) and its 2026-10-15 directory-grants amendment; a CC delta is pending | TRIAL through the fence, with superpowers through `.muse-plugin` inside the fence; no default promotion |
| Jev (TypeSafe SDK) | `candidate:typesafe-ai-skills` (unpinned) in `foundation/instructions-skills`; #1168; the CC's Jev rulings | the trading fast path's typed classifier after its three receipts (Decision 4); SDK pinned at 0.7.2 until the scored run ends; no skill framework |
| Harbor 0.24.0 | #1047 | container harness, as registered |

Defaults change only on a layer's convergence. The model-routes layer is F5's.

## Decision 6: the instructions-skills and memory deltas

- **ECC.** `affaan-m/ECC` is the instructions-skills winner, pinned at `dd6ee538`. The practice-references freshness run of
  2026-10-15 counts 1,114 commits on its default branch after the catalogued pin. The delta: test the changed mechanism
  at the new head.
- **Other skills candidates.** The carried survivor `mattpocock/skills` and the unpinned candidates `typesafe-ai-skills`
  and `openai-skills` are adjudicated in the same delta.
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
    - "Beyond" it, the instructions-skills candidates: ECC at a pinned commit of its current head, plus the carried
      `mattpocock/skills`, `typesafe-ai-skills` and `openai-skills`. Each goes through its vendor's path.
      `mattpocock/skills` is already installed by the plan's `engineering-process-skills` row (tag `v1.2.3`, skills CLI
      1.7.0).
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
    - The readiness trigger is the TRIAL installs plus the sealed task set.
  - Invoke tracking (Decision 8) covers every installed framework skill per lane.
  - The other harness repositories in the practice-reference catalog stay references.
- **Memory.** The durable-memory winner is ai-memory (2.6.6 live), with Hindsight deployed as the research-memory unit
  and recorded as its alternate.
  - The new distribution installs both as recorded.
  - A colliding candidate (for example Graphiti) reopens the layer only on measured evidence. The layer's five carried
    survivors from the 2026-09-29 sweep are its delta.

## Decision 7: disk Z and CPU cleanup

The CC's Z: cleanup and CPU disposition plans of 2026-10-15 (private, by name) are plans only.

- The Z: plan never targets the two live disks.
- The CPU plan keeps every trading-adjacent process to the boundary.
- Both are executed by the CC after the boundary, through its own guarded steps; this lane executes neither.

## Decision 8: the native-clients re-pin and invoke tracking

- **Re-pin, a named T1 row.** `final-stack.json` pins `foundation/native-clients` at claude-code 2.1.295 (its run pin).
  Both distributions run 2.1.300; NativeHorizonNY's native installer gave 2.1.300 on 2026-10-15. The routes are #1128
  (the floor and run pin at 2.1.300) and #1171 (the practice skill's currency).
- **Invoke tracking from the first lane.** Each lane on NativeHorizonNY runs `tools/skill-usage/skill_usage.py` from its
  first session. An installed skill with zero calls is a wiring defect to fix, or a role to retire, per the adoption
  practice.
- **The owner's view.** The CC's status page shows each agent's and worker's installed skills, labelled FINAL, TRIAL or
  GAP. The per-layer half of that view is generated by #1175 from `final-stack.json`.

## The full stack

The new distribution gets every installed row of the install plan, in the stage order above. That is the definitive
manifest's foundation set: 63 rows, 60 of them by the default run. It also gets the TRIAL rows and the runtime workers of
Decisions 5 and 6. No engine or trading profile installs before the engine verdict (Decision 4).

- Rows the plan marks measurement-only or named-only (Loki and Grafana; the two local-model rows) install only when
  their measurement or service runs.
- Each layer's winner is cross-checked against `final-stack.json` as F1 lands.

## Owner acts

Each is the owner's own act and comes with its exact route. None is needed before stage E.

| Act | When | Exact route |
| --- | --- | --- |
| Name and disk | before stage R (decided here; the owner may object) | `NativeHorizonNY` at `Z:\WSL\NativeHorizonNY`; the rehearsal uses a throwaway name in its own `Z:\WSL\<name>` folder |
| Codex sign-in | stage E | in a terminal on the new distribution (`wsl.exe -d NativeHorizonNY`, or the Windows Terminal profile that WSL creates): `codex login`, then the browser sign-in |
| Claude Code sign-in | stage E, after Codex (recipe F9) | in the same terminal: `claude`, then the browser sign-in it opens |
| GitHub CLI, for the private repositories | stage F | `gh auth login --hostname github.com --git-protocol https --web` |
| Keys, by name only | stage F, per the CC's list of key names | `tools/credentials/open_credential_terminal.sh <entry-id>`, from the owner's own terminal on the new distribution; paper pairs with `--probe` |
| IBKR session | when the IBKR lane moves | the gateway login with its second factor, per trading-cc's move sheet |
| Purchases | none now | only if the engine comparison shows fit: the QuantConnect tier its verdict names, with its price |

## The boundary

One receipt that the owner confirms; the CC accepted these five conditions on 2026-10-15. On the new distribution:

1. The install plan's `accept.sh` reports every selected row ok in all three stages (post-install, service health,
   after sign-in) at a landed main commit. This replaces the earlier wording, `bootstrap --check`: this distribution runs
   no bootstrap profile (recipe F9).
2. The owner has signed in both clients, and the client configuration is applied with its receipt.
3. The CC tooling runs: the tracker, the god view and hcom.
4. Records are restored from GitHub and the private records remote.
5. trading-cc has stopped the first moved lane on NativeStack2604 and relaunched it on the new distribution.

Command-center authority moves only after the owner confirms the receipt. Account C stays on NativeStack2604.

## Verification boundary

Source review and four read-only checks at `8053f14e7`, each with exit 0:

- `tools/adoption/new_wsl_client_config.py --check`;
- `scripts/new_host_grand_list.py --check`;
- `scripts/final_stack.py --check`;
- `evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py`: 84 rows (63 installed, 60 of them by the default run;
  2 measurement-only; 19 not installed); 193 commands and 113 acceptance entries agree with the scripts.

Also read: the practice-references freshness report of 2026-10-15 (Actions run 38695909735, report-only).

Executed since, on 2026-10-15 (receipts in the lane's private run directory, by name):

- **Stage R passed and was removed.** The rehearsal ran P1-P3, W1-W7 and F1-F3, with rootless Docker printing
  `Hello from Docker!`, and was removed at 18:37:42Z with interop intact.
- **Stage A passed through F8.** W5's paired isolation proof passed, with distinct cgroup namespaces and the 2604
  baseline unchanged. The hostname is `nativehorizonny` and the time zone America/New_York.
- **After the restart (Windows boot 18:55:12Z), F2-F5 passed.** They ran inside a capped user scope, together with the
  plan's container-engine row (Docker 29.8.2, rootless).
  - NativeStack2604's CPU pressure read `some avg10` 0.00 before and 0.16 after.
- **Interim stage C is running.**

## Sources

- Layer-resolution protocol: [2026-10-11-layer-resolution-protocol.md](2026-10-11-layer-resolution-protocol.md).
- Claude Code native practice:
  - `.claude/skills/claude-native-practice/reference/slots.md` (client 2.1.295, checked 2026-10-09);
  - its currency PR #1171 at 2.1.300.
- Claude Code: `anthropics/claude-code` `CHANGELOG.md` at `94506ff0`. npm dist-tags on 2026-10-15: latest 2.1.300, next
  2.1.301, stable 2.1.292.
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
  [v7.0.0](https://github.com/obra/superpowers/releases/tag/v7.0.0) (2026-10-10).
