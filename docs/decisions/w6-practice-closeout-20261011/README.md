# Decision: W6 closeout for seven foundation layers (2026-10-11)

All seven layers below are recorded **SCHEDULED**: their comparisons are
preregistered and wait for named inputs. No layer is recorded FINAL.
The co-op relayed #1007 LANDED at 23:35:33Z, after squash
`c2dee173da1f792ffd9cce958dd2ca84f47e8c16` landed at 23:34:58Z.
This satisfies the CC's terminal-recording prerequisite.

[terminal-states.json](terminal-states.json) records each comparison id, exact
preregistration hash, readiness event and fixed decision rule.
The decision follows the [landed #1008 protocol](https://github.com/seathatflowsinourveins/native-agent-stack/blob/569bbc59db2b5f7c8a932357726efb7acca90b91/docs/decisions/2026-10-11-layer-resolution-protocol.md#terminal-states-and-evidence)
and the CC's `ruling-w6-wave-dispatch-20261011.md` §§2–4,
SHA256 `a13204da949ba7f1b883332ea601790a2570ccd6066e9bb1bbc150b7b2e03304`.
The closeout is submitted for Astra and CC Claude review. It supplies no new
host install, model/E2E run, qualified winner or live configuration change.

## Recorded terminal states

| Layer | State | Comparison and frozen scope/rule | Exact preregistration SHA256 |
| --- | --- | --- | --- |
| git-github-automation | SCHEDULED | [w6-git-github-automation-20261011](git-github-automation.comparison.json) | `7645182ce8a46711cf31a904c7f603d2bd15b8ed4dfe36da01f990c0e39affd5` |
| instructions-skills | SCHEDULED | [w6-instructions-skills-20261011](instructions-skills.comparison.json) | `0ca6e570c4dac8416b96125e2acf5fc75a0f89a8a4dfbabf587d77f789b5f751` |
| observation-inference | SCHEDULED | [w6-observation-inference-20261011](observation-inference.comparison.json) | `c23fdfa225861aefbb3f404355542bf8abcf4299e4c32503f7e41ce674a53806` |
| quality-evaluation | SCHEDULED | [w6-quality-evaluation-20261011](quality-evaluation.comparison.json) | `ec4f4271e07c76f0eef2fa5787efa4cf96e862e126e6892c08b5f88f398a7167` |
| recovery-portability | SCHEDULED | [w6-recovery-portability-20261011](recovery-portability.comparison.json) | `14dae35c0e84e071caa54b8ba559f3f2cab202b43e6eee843cdab3322627a2bf` |
| scheduling-supervision | SCHEDULED | [w6-scheduling-supervision-20261011](scheduling-supervision.comparison.json) | `fdc5a6ee76f5d76c9dbbae510565a6e5a9c4632b19eaa4bda6d1fd2f776459c3` |
| token-efficiency | SCHEDULED | [w6-token-efficiency-20261011](token-efficiency.comparison.json) | `0c6cd76ede091d0c799135da66cf98bb33a2e2540fbcb180e6901a17f73bcb05` |

The comparison files name their required source, case/oracle and owner-receipt
inputs. The readiness event is retention of the hash-bound input packet for the
named comparison with every listed input present; the review-and-landing replay
also requires #953 and #975 to land. Both were OPEN at the original source check; they have since
landed as 3a8a8461 and 86fa3844. The case/source/owner inputs remain required, and #1027 is OPEN
at the subsequent source check.
Sixteen retained candidate source mirrors were still missing from the observed
source snapshot, and the corresponding immutable source packets remain required.
No comparison whose complete inputs exist may be delayed or replaced by research.
All work uses the existing W5 harnesses.

The exact file digests are also indexed in
[comparison-preregistrations.json](comparison-preregistrations.json).
Case/source-pin packet seals are run inputs and cannot change the frozen
scenario scope or decision rule. Preserve failures, errors, cancellations,
unknown effort and zero-invoke observations with their actual boundaries.

## Four-condition assessment at the landed authority

The exact `git show c2dee173:catalogs/landscape/final-stack.json` bytes were read
through `scripts.final_stack.Sources.json`; winner run joins use
`scripts.final_stack.run_pin`, both from the landed script.
[final-stack-run-assessment.json](final-stack-run-assessment.json) retains that
source hash, reader hash, verdicts, winners and joined run records.
`python3 scripts/final_stack.py --check` passes at the landed base.

| Layer | Run pins recorded in c2dee173 |
| --- | --- |
| git-github-automation | worktrunk: 0.80.0; candidate:cli-cli: 2.101.0; difftastic: 0.71.0 |
| instructions-skills | affaan-m/ECC: dd6ee538aee0f548d4a6b520118f875431fd749e; candidate:typesafe-ai-skills: no run pin; candidate:openai-skills: historical no run pin, now RETIRED |
| observation-inference | opentelemetry-collector-contrib: 0.162.0; prometheus: 3.15.0; loki: 3.7.8 |
| quality-evaluation | promptfoo: 0.123.1; playwright-test: 1.63.0 |
| recovery-portability | restic: 0.19.1; candidate:astral-sh-uv: 0.12.17 |
| scheduling-supervision | dagu: 2.16.6; systemd: 255.4-1ubuntu8.17 |
| token-efficiency | rtk: 0.51.0; headroom: 0.40.0; ccusage: 20.0.26 |

The owned layers have 18 historical winners: 16 have recorded run pins, two
skill winners have none, and six run pins differ from their verdict pins.
For example gh is recorded at 2.101.0 in the landed manifest, while the installed
CLI reports 2.102.0. The closeout keeps that discrepancy explicit.

Each layer has a historical verdict with wave `20260922`, evidence class and
`next_review` metadata; retained sweeps reopened it. The closeout does not
supply a newly qualified W6 winner verdict, an upstream-owned install/test E2E
joined to every run pin, or a complete per-winner adoption-window invoke join.
Thus the four FINAL conditions are not joined for every winner.
Existing matrix `host_e2e` factors and scoped execution receipts are retained;
they are not silently promoted to the upstream E2E/invoke requirement.
This is not a claim that the tools have zero calls. If a measured zero-call tool
is found, fix its wiring or retire its role under the protocol.

The generator's existing `reopened` statuses retain their own meaning.
This dated closeout records SCHEDULED decisions; it neither hand-edits the
generated aggregate nor equates an aggregate status with a terminal state.

## Inputs and every survivor's disposition

[inputs-and-dispositions.json](inputs-and-dispositions.json) binds the exact
bytes, JSON pointers and historical vote refs for:

- `catalogs/landscape/foundation.json`, its applicable 20260922 verdict wave
  and detailed verdict artifact;
- the latest covering `landscape-sweep-20260929` ledger row for each layer,
  its manifest and retained returns, plus earlier adjudications;
- the 10-08 grand catalog, exact source-review layer slots and delta queue
  `catalogs/landscape/research-state.json`.

Those research inputs were frozen from
`77185991ec9627e59473df5b4d7a11ca87b0461d`; the terminal/run authority is the
later c2dee173 landing. The 10-09 Pine sweep covers another layer and does not
replace these layers' latest covering sweep.

There are **16 cumulative substantive survivors plus five proposals whose GPT
fit votes did not return**. Later omissions do not clear older survivors;
later returned substantive refutations do. Missing votes cannot refute a
candidate. The historical 09-23 ledger row has no `returns_ref`; its lens
references are preserved without claiming fresh completeness.

Every unresolved candidate/role has a recorded disposition: 20 entries are
included in the frozen comparisons, and the in-GitHub Claude OIDC role is
retired by #981. The whole git-github-automation layer remains SCHEDULED.
Grand-catalog slot membership counts are overlapping source inventory counts,
not survivors, qualified choices or native acceptance. No discovery ran.

## Named GitHub and quality deltas

The review-and-landing role compares the current pinned #953/connector/exec/GPT
kit/#975/ruleset/#947 path with gh-aw, codex-action, reviewdog, mergify-cli,
coderabbit skills and PR-Agent on its local CLI path. Landing compares the #975/#1027 scripts,
rulesets and #947 with mergify-cli using a sealed incident replay. Reviewdog is a reporting adapter;
OpenHands and both SWE-agent resolvers are excluded from these roles. W1 review replays
#974, #978, #970, #989, #982 and #992: block every known P1/P2, then minimize false
blockers and complete measured cost. The sem subcomparison follows the existing
[10-02 P2 decision](../2026-10-02-github-automation-practice.md#preregistered-checks):
difftastic sample files and frozen repository PR diffs, scored by promptfoo;
a tie goes to the user.

**HARNESS-WIF-FIX-PROPOSAL: CLOSED, superseded by #981.**
The retained original proposal is in github-ci-finalize's questions file at
line 4327 (`run=37739403956`,
`action=6fed3ca145920b639991cb756090506e1bcaf515`).
[PR #981](https://github.com/seathatflowsinourveins/native-agent-stack/pull/981)
retired in-GitHub Claude review at
`8bffa2c41692ef483e91b68e3b15aeb331423d2c`,
2026-10-11T04:19:45Z. CC W6 §3(a) explicitly directs closure.
No WIF repair is needed for that retired role. Historical proposal bytes remain
intact; local review and landing have separate qualification.

Installed gh reports **2.102.0**; its official release tag is
`fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd`, whereas the observed central HEAD
is `ec5b512045db67e5a2a4ff4a1b02660b2fb24390`.
Retain that release source and lifecycle receipts, reconcile the landed run
inventory, and rerun the Codex pin_moved receipts through their owning native
paths before closing those evidence gaps.

Quality-evaluation preregisters Promptfoo against Inspect on the same 60
independently labeled advice cases, preserving safe controls and uncertain
disagreements. The earlier eight-case diagnostic is not a tuning corpus.
MTEB's embedding-evaluation role is included explicitly as an auxiliary scenario.
Other layers dispatch only their surviving candidates, missing votes, moved
pins and named evidence gaps.

## Primary sources and bounded recovery

[primary-source-refs.json](primary-source-refs.json) retains the 13 initial
central mirrors at full MIRRORS.lock SHAs, exact public source hashes and
documentation section locations. Locked HEADs matched at the original check. Historical lock-snapshot
digests with unavailable preimages are omitted; individual repository pins and source-byte digests remain.
[ollama-source-recovery-20261011.json](ollama-source-recovery-20261011.json)
adds Ollama at `eab97e9f92b9a25c2d52d2cc6c1b1c99bd9fae21`, with lazy fetch and
optional locks disabled. These are source_review observations.

The following 16 retained candidates lacked a central mirror in the 23:35
source snapshot. Recover their known sources and exact pins; their absence
does not justify new discovery:

- https://github.com/embeddings-benchmark/mteb — quality-evaluation.
- https://github.com/mattpocock/skills — instructions-skills.
- https://github.com/ojuschugh1/sqz — token-efficiency.
- https://github.com/paritok-official/paritok-4b-v1 — token-efficiency.
- https://github.com/lockedinlabs-ai/agent-console — token-efficiency.
- https://github.com/atlassian-labs/mcp-compressor — token-efficiency.
- https://github.com/klavis-ai/klavis — token-efficiency.
- https://github.com/traceloop/openllmetry — observation-inference.
- https://github.com/utkuozdemir/nvidia_gpu_exporter — observation-inference.
- https://github.com/nvidia/dcgm-exporter — observation-inference.
- https://github.com/ml-explore/mlx-lm — observation-inference.
- https://github.com/mostlygeek/llama-swap — observation-inference.
- https://github.com/microsoft/pg_durable — scheduling-supervision.
- https://github.com/restatedev/restate — scheduling-supervision.
- https://github.com/conductor-oss/conductor — scheduling-supervision.
- https://github.com/microsoft/wsl — recovery-portability.

The review packet indexes retained authority/source/measurement references,
immutable byte identities and every missing primary input. Readers can retrieve
the committed research inputs at their recorded Git revision and the available
central sources at their exact mirror SHAs. Source hashes establish byte identity,
not new task acceptance or exhaustive upstream qualification.

## Publication and execution boundary

No canonical catalog, generated final-stack file, live client configuration,
paper unit, account state or peer-owned worktree is changed here.
FINAL can follow only after all four conditions join for every winner.
SCHEDULED is terminal for this wave and begins its fixed comparison when its
named inputs exist; RETIRED requires an explicit role reason.

Cued PR work and Monday's paper path retain precedence.
Heavy suites in Monday 08:00Z–20:00Z use the T2 idle wrapper; full suites also
require SUITE-REQUEST/SUITE-GO. No heavy E2E, mutation run or model replay ran
for this source/decision closeout.

## Role corrections and retained reopening inputs

[arm-dispositions.json](arm-dispositions.json) records five Review arms and two Landing arms,
the native resolver retirement, SWE-agent supersession by mini-swe-agent, the reporting-only
reviewdog boundary and candidate:openai-skills **RETIRED** with openai/plugins as successor.
The resolver sources stay in the workers closeout; OpenHands/extensions belongs to W7.
The native merge queue becomes eligible only after the organization move and its qualification.
No successor is installed or adopted by this closeout.

GPU exporters are additive GPU-field trials beside the unchanged guard; llama-swap is a routing
comparison with backend inference held constant. agent-console is an attribution observer; MCP
deferral has explicit permission, hook, approval, invoke and server-instruction gates. Dagu tests
2.17.2 with its scheduler and default/tuned liveness; Restate tests cross-host leader loss. SQL
and Conductor recovery keep their retained job/cancellation scopes and resource controls.
Inspect tests mutations, empty/cancelled controls, failure localization and 20-case top-up.
Each retained not-adopted condition is a named readiness input; missing votes remain missing.
All seven preregistrations, decision-rule copies and readiness copies are re-frozen together.
