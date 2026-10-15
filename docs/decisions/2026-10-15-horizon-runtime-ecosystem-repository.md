# horizon: a private repository for the NativeHorizonNY runtime ecosystem, with local-first enforcement

Date: 2026-10-15. Status: accepted. The owner decided the repository and its visibility on 2026-10-15, and the command
center ruled its location and enforcement the same day. Its private coordination records are cited by name only:
direction-cc-20261015T1912Z-new-wsl-harness-first addenda 05 to 09.

## Owner direction (paraphrased, 2026-10-15)

- The new WSL distribution needs its runtime ecosystem as code, kept current by its own maintenance loop: audit,
  reflection, compounding, and change as the landscape changes (16:09 and 16:14 ET).
- Each model family's runtime workers carry their full stacks, and GitHub automation covers the whole pull-request
  lifecycle with reviews from more than one model family (16:09 ET).
- Visibility: follow the best practice for an LLM-native workflow with the highest-quality local pull-request automation;
  if every action stays local and local is better than hosted automation, choose private (16:18 ET).
- The new host gets full access at every layer, with frictionless GitHub automation at maximum quality (16:41 ET).

## Decision

1. **One new private repository, `seathatflowsinourveins/horizon`.** It holds the NativeHorizonNY runtime ecosystem as
   code: host configuration and install stages; one runtime stack per model family (Anthropic, OpenAI, Meta as a TRIAL,
   and the research stack) with its native CLI and its fully harnessed SDK and framework workers; the role-assignment
   matrix; the command-center, co-op and god-view tooling; session relaunch; and the multi-family review and landing
   automation.
2. **What stays where.** native-agent-stack stays the public home of research, catalogs, decisions and evidence;
   us-equities-trading stays the private trading code; the organisation's private records repository stays the sealed
   history. horizon pins all three by commit in its `pins.json` and copies nothing wholesale. A piece enters horizon only
   after it has landed and converged at its source, and its pull request cites that source at a pin.
3. **Location: the owner's personal account.** The repository was created in the native-agent-stack organisation at
   2026-10-15T20:33:54Z and transferred to the personal account at 20:39:48Z, while it held only its root commit. It stays
   private. The organisation is on GitHub Free, where private repositories get no rulesets; the personal account is on
   GitHub Pro, where they do (facts below).
4. **Local gates are primary; GitHub refuses only a merge that skipped them.**
   - **The lander is the only merge path.** It merges a pull request only when a Claude-family and a GPT-family verdict
     file each approve the full head SHA, and the local CI receipts at that head pass. Muse verdicts are a TRIAL third
     family: recorded, never required. It then posts three commit statuses at the head, `lander/local-ci`,
     `lander/verdict-claude` and `lander/verdict-gpt`, and squash-merges pinned to that head. The squash commit carries the
     lander's receipt as trailers (head, verdict and receipt digests), so the self-audit can read it from main itself. The
     lander is `tools/landing/horizon_land.sh` in this repository (#1194, its own pull request).
   - **Ruleset on main** (id 25195996, active, no bypass): pull request required (squash only), deletion and force-push
     blocked, linear history, and the three `lander/*` contexts required with the strict up-to-date policy. No hosted CI is
     required.
   - **Hooks in every clone:** gitleaks on pre-commit and pre-push, and a pre-push hook that refuses any update or deletion
     of main.
   - **Agent permission rules:** Claude Code deny rules and Codex forbidden rules for the push-to-main, hook-bypass and
     merge command forms.
   - **Self-audit** in the maintenance loop (PROPOSAL: designed, not built): every first-parent commit on main after the
     root is the squash merge of exactly one pull request ([`GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls`](https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit))
     whose lander trailers name its head.
5. **Full lifecycle, a receipt at each step** (owner direction of 2026-10-15, 17:54 ET, paraphrased: the highest-quality
   automation across the whole lifecycle). For horizon:
   - **plan:** the PR description, with its sources at a pin (the existing `sota-sources` practice);
   - **PR and reads:** a Claude-family and a GPT-family verdict file, each naming the full head SHA;
   - **land:** the lander's statuses and its trailers in the squash commit;
   - **post-merge audit:** the self-audit above (PROPOSAL until built).
   Citation checks beyond the presence of the `SOTA sources` section are not automated: a landscape survey of upstream
   PR-policy and citation checkers comes first, screened by both families, and nothing changes in the gate until a
   mechanism converges (PROPOSAL).
6. **Statuses until the review App exists.** Commit statuses carry no reviewer identity: any account with push access can
   post one. This is the interim of [the review-verdict App record](2026-10-09-review-verdict-app-identity.md): a status is
   a backstop, and the lander re-reads its own verdict and receipt files before every merge. When the owner has registered
   that App and the CC has verified its Transition, horizon's required checks bind to the App's integration and the lander
   posts App check runs instead.
7. **Existing repositories (audit of 21, read-only).** This updates the 2026-10-10 consolidation dispositions only where
   horizon changes them:
   - the private foundation control plane, agent-ecosystem (host registry and managed client setup), folds INTO horizon
     piece by piece, each piece by a cited pull request once it is shown converged; it is archived with a pointer only
     after the repositories that consume it have moved;
   - north-star-research no longer folds into agent-ecosystem: its research goes to native-agent-stack and its trading
     outputs to us-equities-trading;
   - agent-harness and agent-lab still fold into native-agent-stack (practice belongs in public);
   - the trading research and desk repositories are the trading lane's call; the owner's side projects are out of scope;
     archived repositories stay retired.

## Plan facts behind the location (measured 2026-10-15 and read from GitHub's documentation)

| Fact | Source |
| --- | --- |
| The organisation is on the free plan; the personal account is on Pro | `gh api orgs/native-agent-stack` (`plan.name: free`); `gh api user` (`plan: pro`) |
| An organisation private repository refuses rulesets and branch protection | `GET .../rulesets` and `.../branches/main/protection` on the organisation's private repository: HTTP 403, "Upgrade to GitHub Pro or make this repository public to enable this feature." |
| Rulesets and protected branches: public repositories on Free; public and private on Pro, Team and Enterprise Cloud | docs.github.com, "About rulesets" and "About protected branches", section "Who can use this feature?" |
| Merge queue: public organisation repositories, and private ones only on Enterprise Cloud | docs.github.com, "Managing a merge queue", "Who can use this feature?" |
| Code owners in private repositories need Pro, Team or Enterprise | docs.github.com, "About code owners", "Who can use this feature?" |
| A personal private repository's ruleset is active | `us-equities-trading`'s branch ruleset, `enforcement: active` |
| horizon's ruleset refuses a direct push | 2026-10-15T20:40:27Z: an empty commit pushed to main with the local hook bypassed was refused, "GH013: Repository rule violations found for refs/heads/main"; main did not move |

## Sources

- gitleaks 8.30.1, the installed client (`gitleaks version`): `gitleaks git --pre-commit --staged` and `--log-opts` from its `git --help`; configuration `[extend] useDefault = true` from [gitleaks@v8.30.1 `README.md:263-293`](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md#L263-L293).
- git 2.53.0, the installed client: [git@v2.53.0 `Documentation/githooks.adoc:232-257`](https://github.com/git/git/blob/v2.53.0/Documentation/githooks.adoc#L232-L257), pre-push: one `<local-ref> SP <local-object-name> SP <remote-ref> SP <remote-object-name>` line per ref on standard input, a deletion supplied as `(delete)`, and a non-zero exit aborts the push.
- openai/codex `rust-v0.162.1` (the installed codex-cli 0.162.1): `codex-rs/execpolicy/README.md` (`prefix_rule` with `decision = "forbidden"`, and `match`/`not_match` checked at load) and `codex-rs/core/src/exec_policy.rs:662-679` (each trusted config layer's `rules/*.rules` loads). The rules were checked with `codex execpolicy check`.
- Claude Code, [Configure permissions](https://code.claude.com/docs/en/permissions) (read 2026-10-15): deny rules apply in every mode; Bash rules match the whole command text, with `*` for any text, and a deny rule matches any subcommand of a compound command.
- GitHub REST: [rulesets](https://docs.github.com/rest/repos/rules), [repository transfer](https://docs.github.com/rest/repos/repos#transfer-a-repository) and [commit statuses](https://docs.github.com/rest/commits/statuses).
- This repository: [the review-verdict App record](2026-10-09-review-verdict-app-identity.md), [the GitHub automation practice](2026-10-02-github-automation-practice.md), [the in-GitHub Claude review retirement](2026-10-10-retire-in-github-claude-review.md) and [the automation closure](2026-09-22-github-automation-closure.md); `tools/landing/nas_land.sh`, whose shared block the horizon lander reuses unchanged.

## Alternatives considered

- **Reuse agent-ecosystem as the repository.** Its scope is the closest fit, but it carries open pull requests and material
  from retired hosts. A clean repository seeded only from converged pieces follows the owner's 2026-10-14 direction to
  curate, not mirror. Its converged pieces move in by pull request instead.
- **Keep the runtime code in native-agent-stack.** That repository is public; host configuration, worker profiles and the
  command center's tooling would need every public-repository privacy scan, and the owner chose private.
- **A private repository in the organisation.** On the free plan GitHub enforces nothing there, so a merge that skipped
  the local gates could land unnoticed until the self-audit ran.
- **Upgrade the organisation to Team or Enterprise Cloud.** That is an owner cost decision. It would bring rulesets (Team)
  or the merge queue (Enterprise Cloud) to private organisation repositories.

## Overturn when

- The organisation moves to a plan with private-repository rulesets, or the owner wants a merge queue: transfer horizon
  back (`POST /repos/seathatflowsinourveins/horizon/transfer` with `new_owner=native-agent-stack`) and move the ruleset.
- The review App's Transition is verified: required checks bind to the App, and statuses stop counting.
- A spoofed `lander/*` status, or a commit on main that the lander did not land, is found: the CC reviews the identity
  model before the next landing.

## Inverse

Archive the repository; delete it only on the owner's decision. The ruleset's inverse is `DELETE /repos/seathatflowsinourveins/horizon/rulesets/25195996`.
