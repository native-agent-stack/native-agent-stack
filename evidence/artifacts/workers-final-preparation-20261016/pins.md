# F1: one proposed run pin per recorded winner

All repository path:line locators below refer to current-main snapshot **caa224140a2d04ba5f3d0ca320c487a75f9c9ea1**, retained as this PR's base. JSON pointers disambiguate repeated ids. These are proposals for the co-op's read, not changes to historical verdicts, installer floors or `runs[]`.

## Claude Code: propose 2.1.301

| Pin source | Value / scope | Base locator |
| --- | --- | --- |
| Layer winner / historical verdict | 2.1.278; native child and recovery fixtures at their dated source state | `catalogs/landscape/final-stack.json:8514` (`layers`, foundation/workers); `catalogs/sota-convergence/layer-verdicts-20260922.json:4651` |
| Current derived run record | 2.1.295, sourced from Linux bootstrap pin; no public CLI source commit | `catalogs/landscape/final-stack.json:10496` (`runs[id=claude-code]`) |
| Authoritative run-pin inputs | Both Linux and macOS minimum 2.1.295; native latest-channel behavior can retain a newer installed version. A floor is not an exact live version. | `adoption/pins-linux-x86_64.json:105`, `adoption/pins-macos-arm64.json:85`; `manifests/stack.json:192` |
| Clean-install plan layer row | Claude Code + Worktrunk; reopened, two drifted winner pins | `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:149` |
| Plan's version trajectory | 2.1.295 run pin, 2.1.300 floor/currency work, 2.1.301 native sessions; later installer record supersedes the planned host's 2.1.300 observation | Same plan `:700`, `:1025` |
| Last retained public component practice/floor records | 2.1.295. Their mechanisms/qualification are dated evidence, not automatically requalified at 2.1.301. | `docs/decisions/2026-10-09-claude-code-native-practice.md:1,38`; `2026-10-09-claude-code-floor.md:1,53` |
| Latest committed version/install attestation consumed | 2.1.301 native installer, signed-manifest check and Linux checksum; private receipt named by the plan, not imported here | Clean-install plan `:1027-1038` |
| Installed CLI, read-only version query | `2.1.301 (Claude Code)` | This preparation's version query; isolated pin-specific repetition at [outputs/claude/011-test.txt](outputs/claude/011-test.txt) |
| This fresh vendor installation | 2.1.301; native installer into an empty scratch HOME, no credentials | [claude-code-smoke.json](claude-code-smoke.json), install step 4 and checks 9–12 |

Reason: 2.1.301 matches the latest explicit plan amendment and installed client, and includes vendor resume/compaction corrections relevant to workers. Keeping 2.1.295 merely because the derived run record has not caught up would leave the current deployment unqualified. Conversely, old 2.1.278 child acceptance cannot be upgraded by citation. The proposed pin therefore comes with a **current worker-E2E/invoke GAP**, not a claim that a newer version is automatically a winner.

Public docs tag `v2.1.301` resolves to **03b5892ee77de289bcd5dfa39f541525ade74aff**. The signed release manifest identifies proprietary build commit **12a1baed117fbcc7e0695ab8aa6d2a4c6bd00cbb** and build date `2026-10-15T14:01:03Z`. They are different repositories/source boundaries; the public docs commit is **not** asserted to be CLI source. Exact Linux artifact: 267,955,384 bytes, SHA256 **bc1aad9982c7b59c7d889ff92595d61cf46e0a6eae074cb551d932a989bcd222**. Vendor public-key fingerprint **31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE** was checked in a new scratch keyring; detached manifest verification exited zero and installed binary hash/size matched. See [release-integrity.json](release-integrity.json), the fully published [vendor manifest](claude-release-manifest.json) and [binary check output](outputs/claude/010-verify.txt). No digest of omitted installer/runtime output is used as proof.

Drifts retained: verdict 2.1.278 → component practice/bootstrap/derived run 2.1.295 → intermediate plan/native smoke 2.1.300 → proposed/installed 2.1.301. The prior F1 2.1.300 arm is a private named source lead only; no private receipt/output hash is published or treated as 2.1.301 evidence. macOS's 2.1.295 floor and platform acceptance remain separate; no macOS execution occurred.

## Worktrunk: propose 0.80.0 at b49ca7eea9b03145791a5b94eccaf9c59412ed37

| Pin source | Value / scope | Base locator |
| --- | --- | --- |
| Layer verdict | 0.79.0; old working-directory comparison, with earlier 0.78.0 dirty-refusal fixture | `catalogs/landscape/final-stack.json:8536`; `catalogs/sota-convergence/layer-verdicts-20260922.json:4651` and its winner evidence |
| Derived run pin | 0.80.0, source commit b49ca7eea9b03145791a5b94eccaf9c59412ed37 | `catalogs/landscape/final-stack.json:11392` (`runs[id=worktrunk]`) |
| Run-pin source record | 0.80.0, vendor repository and `wt list` command | `manifests/stack.json:1071` |
| Clean-install plan | Lists Worktrunk in workers and shared Git/isolation roles; no exact Worktrunk version in this layer row | `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:149,194` |
| Last committed named component qualification consumed | 0.80.0; version/list in a synthetic repository, explicitly excludes create/remove/dirty refusal/full cargo suite | `evidence/receipts/worktrunk-0800-qualification-20261003.json:9,19,23` |
| Installed CLI | `wt v0.80.0` | Read-only version query; isolated repetition [outputs/worktrunk/010-verify.txt](outputs/worktrunk/010-verify.txt) |
| Fresh preparation install and lifecycle | Same release/source; published archive checksum matches; create/list/dirty refusal/preservation/clean removal observed | [worktrunk-smoke.json](worktrunk-smoke.json) and [release-integrity.json](release-integrity.json) |

Reason: current derived run pin, installed release and committed component qualification already agree. The fresh smoke fills the narrow create/remove/dirty-refusal gap at **0.80.0** without pretending that the 0.78/0.79 observations were current. Neither it nor an archive install establishes worker-model cancellation, review integration, copy-ignored behavior, shell integration or cross-host crash recovery.

Upstream tag `v0.80.0` is lightweight at **b49ca7eea9b03145791a5b94eccaf9c59412ed37**. The Linux MUSL release archive's SHA256 **532ce3ed5eecb1be274c925b5887f61671e2434a4ca2561b9a8ac9379dbba199** matched its published `sha256.sum`. This is the prebuilt distribution path declared at [dist-workspace.toml:17](https://github.com/max-sixty/worktrunk/blob/b49ca7eea9b03145791a5b94eccaf9c59412ed37/dist-workspace.toml#L17), not a source build. Full Rust tests were not run.

## Carried survivor: Codex, no winner promotion

The September 29 carried source review is **0b1b78a4f1694e2b9e393d385c7b82ca714ca08a**, at `evidence/artifacts/landscape-sweep-20260929/openai-codex.json` (`reviewed_commit`). Current Linux run input is **0.160.0**, macOS conflict **0.155.1** (`final-stack.json`, `runs[id=codex]`; `adoption/pins-linux-x86_64.json:53`, `adoption/pins-macos-arm64.json:59`). Read-only installed query returned **codex-cli 0.162.1**. The prior F1 exact 0.160.0 source was a956835d020762cb2b570053af06f643a11c0ecc; its private run is not a public current-pin worker comparison.

The source screen in this draft remains tied to the retained survivor review pin, with the 0.160 release CI observation explicitly labelled a different snapshot. A comparative arm must freeze its chosen runtime/model/fence pin separately. No silent repin, model route, extra install or Codex execution beyond `--version` is performed for this layer task.
