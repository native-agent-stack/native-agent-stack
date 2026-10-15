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

The CC recorded these in its direction record of 2026-10-15T18:09Z and its handover set of the same day (private
records, cited by name only).

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
catalogs, plus `foundation/model-routes`, `us-equities/catalysts-sentiment` and `us-equities/judgment-features`. No subset.

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

The install plan installs each layer's current winners, as the plan's rows record them. A layer's next action changes
what the new distribution installs only when its result lands.

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
| C. Stage 2: the install plan, the clients first (`install.sh` installs Claude Code and Codex by their native installers before the other rows) | recipe F9; `evidence/artifacts/new-wsl-install-plan-20261002/` (`install.sh`, `accept.sh`) | `check_plan.py`; the post-install stage of `accept.sh` | the CPU and memory caps below; F1's run pins as they land |
| D. Client configuration | recipe F9: `tools/adoption/new_wsl_client_config.py --apply --host <host>` | `--check`; the apply receipt | the template-behind rows of the [reconciliation record](2026-10-15-claude-host-config-reconciliation.md) |
| E. Sign-ins | recipe F9: `codex login`, then `claude`, by hand | the after-sign-in stage of `accept.sh` | the owner: credentials and sign-ins are the owner's |
| S. Services | the plan's service-health stage | `accept.sh --stage service_health` | the per-row port gap below, closed |
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
  - The recipe's mechanisms apply: F8 picks the host file's ports outside the workstation's set, and
    `observability/backends/configure.py --port-overrides` moves the observability block.
  - **Named gap on the living plan:** the other services' ports are fixed in the plan's configuration files. The proposed
    change is one port parameter per service row, read from the host value file.
  - Until that change lands, stage C runs `install.sh` and the post-install stage of `accept.sh` only, and no service of
    the plan starts. Dagu's installer starts its unit, so a bind failure on 21080 is expected and is recorded as it
    occurs.
  - Which services account C depends on comes from trading-cc's sheet for C.
- **CPU and memory.** WSL 3.0.1 and later give each distribution its own cgroup namespace (recipe; host WSL 3.0.3.0).
  - Idle class inside the new distribution yields only to its own processes, not to NativeStack2604's lanes. Account C
    trades in regular hours, after hours and overnight.
  - The heavy stages therefore run in `systemd-run --user --scope` units with absolute limits: `CPUQuota=` and
    `MemoryMax=`. The values are set from the load measured at the time, with headroom kept for NativeStack2604.
  - The scope's `cpu.max` and `memory.max` are read back before the step starts.
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
  - Its verdict is a named input. This row stays open until it lands; the new distribution installs no engine default
    before then.
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
| Claude Code (headless, subagents, Workflows) | `foundation/native-clients` and `workers` winners; the practice skill | default, at stage B |
| Codex native SDK and lanes | `us-equities/agents-models-workers` and `foundation/agent-sdks` winners | default |
| Pi, OpenCode (`ns-run` profiles) | #1033 and `notes/runtime-profiles-20261012/`. Profiles remain trial; the W6 parallel-readers comparison is preregistered and not executed | TRIAL through the fence |
| Muse Code | [2026-10-14-muse-file-fence.md](2026-10-14-muse-file-fence.md) and its 2026-10-15 directory-grants amendment; a CC delta is pending | TRIAL through the fence; no default promotion |
| Jev (TypeSafe SDK) | `candidate:typesafe-ai-skills` (unpinned) in `foundation/instructions-skills`; #1168; the CC's Jev rulings | the trading fast path's typed classifier after its three receipts (Decision 4); SDK pinned at 0.7.2 until the scored run ends |
| Harbor 0.24.0 | #1047 | container harness, as registered |

Defaults change only on a layer's convergence. The model-routes layer is F5's.

## Decision 6: the instructions-skills and memory deltas

- **ECC.** `affaan-m/ECC` is the instructions-skills winner, pinned at `dd6ee538`. The practice-references freshness run of
  2026-10-15 counts 1,114 commits on its default branch after the catalogued pin. The delta: test the changed mechanism
  at the new head.
- **Other skills candidates.** The carried survivor `mattpocock/skills` and the unpinned candidates `typesafe-ai-skills`
  and `openai-skills` are adjudicated in the same delta.
- **Harness frameworks: superpowers enters as a TRIAL.** On 2026-10-15 (18:19Z) the owner asked for fully designed
  harness frameworks to power the runtime workers cleanly (paraphrased).
  - The screen at its release `v7.0.0` (2026-10-10) passes the supported-harness requirement. Its README documents an
    install route per harness:
    - Claude Code: `superpowers@claude-plugins-official`, the official marketplace;
    - Codex: the official Codex plugin marketplace;
    - OpenCode and Pi: the repository's `.opencode` and `.pi` folders, through those clients' own routes;
    - Muse: `.muse-plugin`;
    - others named in the README.
  - On the new distribution it installs through each harness's own route, as TRIAL, beside the native composition. It is
    not a default.
  - The decision is a preregistered paired same-task comparison per harness (Claude Code, OpenCode, Pi): superpowers at
    the `v7.0.0` commit against native composition, on a sealed task set, in the existing harnesses (promptfoo or the
    skill-creator benchmark, blind judge plus exact checks).
  - Its decision rule is the practice skill's `orchestration-frameworks` overturn rule: a framework becomes the default
    only when it is ahead on quality at equal or lower cost. The readiness trigger is the TRIAL install on the new
    distribution plus the sealed task set.
  - ECC, the instructions-skills winner, joins the same comparison at its current head (its own delta above). The other
    harness repositories in the practice-reference catalog stay references.
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

## The full stack

The new distribution gets every installed row of the install plan. That is the definitive manifest's foundation set: 63
rows, 60 of them by the default run. It then gets the grand list's trading profiles (`research-runtime`,
`trading-nautilus`), the TRIAL rows above and the runtime workers of Decision 5.

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
5. trading-cc has stopped account A's lane on NativeStack2604 and relaunched it on the new distribution.

Command-center authority moves only after the owner confirms the receipt. Account C stays on NativeStack2604.

## Verification boundary

Source review and four read-only checks at `8053f14e7`, each with exit 0:

- `tools/adoption/new_wsl_client_config.py --check`;
- `scripts/new_host_grand_list.py --check`;
- `scripts/final_stack.py --check`;
- `evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py`: 84 rows (63 installed, 60 of them by the default run;
  2 measurement-only; 19 not installed); 193 commands and 113 acceptance entries agree with the scripts.

Also read: the practice-references freshness report of 2026-10-15 (Actions run 38695909735, report-only).

Nothing has been installed, no distribution has been created, and no stage of this plan has run.

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
- systemd: [systemd.resource-control(5)](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
  (`CPUQuota=`, `MemoryMax=`, `CPUWeight=`), and [systemd-run(1)](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)
  (`--user --scope`).
- Linux cgroup v2: [Control Group v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) (`cpu.max`, `cpu.weight`,
  `cpu.idle`, `memory.max`, PSI `cpu.pressure`).
- superpowers: [obra/superpowers `README.md` at `v7.0.0`](https://github.com/obra/superpowers/blob/v7.0.0/README.md),
  "Installation" (an install route per harness), and the release
  [v7.0.0](https://github.com/obra/superpowers/releases/tag/v7.0.0) (2026-10-10).
