# horizon: a private repository for the NativeHorizonNY runtime ecosystem, with a required local landing workflow

Date: 2026-10-15. Status: accepted for the repository, its visibility and its location. The owner decided the repository
and its visibility on 2026-10-15, and the command center ruled its location the same day. The enforcement design in
Decision 4 is implemented only where it says so; the rest is labelled PENDING or PROPOSAL. Private coordination records are
cited by name only: direction-cc-20261015T1912Z-new-wsl-harness-first addenda 05 to 10, and ROW-cc-20261015T2048Z-correction-practice-by-convergence
with its addenda 01 and 02 (sources at a pin; anything uncited is a PROPOSAL).

## Owner direction (paraphrased, 2026-10-15)

- The new WSL distribution needs its runtime ecosystem as code, kept current by its own maintenance loop: audit,
  reflection, compounding, and change as the landscape changes (16:09 and 16:14 ET).
- Each model family's runtime workers carry their full stacks, and GitHub automation covers the whole pull-request
  lifecycle with reviews from more than one model family (16:09 ET).
- Visibility: follow the best practice for an LLM-native workflow with the highest-quality local pull-request automation;
  if every action stays local and local is better than hosted automation, choose private (16:18 ET).
- The new host gets full access at every layer, with frictionless GitHub automation at maximum quality (16:41 ET).
- The highest-quality automation across the whole lifecycle, everything tracked and kept clean (17:54 ET).

## Decision

1. **One new private repository, `seathatflowsinourveins/horizon`.** It holds the NativeHorizonNY runtime ecosystem as
   code: host configuration and install stages; one runtime stack per model family (Anthropic, OpenAI, Meta as a TRIAL,
   and the research stack) with its native CLI and its fully harnessed SDK and framework workers; the role-assignment
   matrix; the command-center, co-op and god-view tooling; session relaunch; and the multi-family review and landing
   automation.
2. **What stays where.** native-agent-stack stays the public home of research, catalogs, decisions and evidence;
   us-equities-trading stays the private trading code; the organisation's private records repository stays the sealed
   history. horizon pins all three by commit in its `pins.json` (in its root commit) and copies nothing
   wholesale. A piece enters horizon only after it has landed and converged at its source, and its pull request cites that
   source at a pin.
3. **Location: the owner's personal account.** api-actions created the repository in the native-agent-stack organisation
   (`gh repo create native-agent-stack/horizon --private`, `created_at` 2026-10-15T20:33:54Z, `private: true` read back
   before the first push), pushed the root commit, and transferred it to the personal account while it held only that
   commit (`gh api -X POST repos/native-agent-stack/horizon/transfer -f new_owner=seathatflowsinourveins`, exit 0 at
   2026-10-15T20:39:48Z). `gh api repos/seathatflowsinourveins/horizon` then read `private: true`, default branch main,
   squash merge only, delete-branch-on-merge, wiki, projects and auto-merge off. The organisation is on GitHub Free, where
   private repositories get no rulesets; the personal account is on GitHub Pro, where they do (plan facts below).
4. **The lander is the required local workflow. GitHub enforces three status contexts and freshness, not the local gates.**
   - **Implemented on GitHub: ruleset 25195996 on main.** Created by `gh api -X POST repos/seathatflowsinourveins/horizon/rulesets`
     (2026-10-15T20:40:17Z) and read back by `gh api repos/seathatflowsinourveins/horizon/rules/branches/main`: active, no
     bypass actors; deletion and force-push blocked; linear history; pull request required with squash only, zero
     required approvals and resolved review threads; and `lander/local-ci`, `lander/verdict-claude` and
     `lander/verdict-gpt` required with the strict policy, so the branch must be up to date with main before merging
     ([github/docs@be38ec5d `available-rules-for-rulesets.md:172`, `:188-193`](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md#L172-L193)).
     A direct push was refused (below). No hosted CI is required.
   - **Implemented in horizon's root commit:** gitleaks on pre-commit and pre-push, and a pre-push hook that refuses any
     update or deletion of main, each active once a clone sets `core.hooksPath` (its `tests/hooks_test.sh` passes 8 cases
     against a throwaway remote); Claude Code deny rules (`.claude/settings.json`) and Codex forbidden rules
     (`.codex/rules/horizon.rules`, checked with `codex execpolicy check`) for the push-to-main, hook-bypass and merge
     command forms. The Claude rules follow the permissions documentation and are not yet probed in a session.
   - **PENDING (#1194, not on main): the lander, `tools/landing/horizon_land.sh`.** It lands a pull request only when the
     PR targets main; a Claude-family and a GPT-family verdict file each approve the full head SHA (Muse verdicts are a
     TRIAL third family: recorded, never required); the local CI receipts at that head pass; and CODEOWNERS, read from main
     (the base branch, [about-code-owners.md:44](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/content/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners.md#L44)),
     names only the merging account and GitHub reports no CODEOWNERS errors. Only then does it post the three statuses and
     squash-merge pinned to that head. The squash commit carries the lander's receipt as trailers: the head and each
     verdict and receipt file by name, never a digest of an unpublished file; the digests stay in a local landing receipt.
   - **Residual, stated plainly.** GitHub checks only that the three contexts report success at the head; any person or
     integration with write access can set a status's state unless an expected App source is bound
     ([`available-rules-for-rulesets.md:178`](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md#L178)).
     So a writer can post three successes and merge in the web interface without running the local gates; the lander's own
     README (#1194) names the same gap. Detecting such a merge is the self-audit's job.
   - **PROPOSAL: the self-audit** in the maintenance loop: every first-parent commit on main after the root is the squash
     merge of exactly one pull request ([`GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls`](https://docs.github.com/rest/commits/commits#list-pull-requests-associated-with-a-commit))
     whose lander trailers name its head, matched to the local landing receipt.
5. **Full lifecycle, a receipt at each step.** Implemented, manual and pending steps for horizon:
   - **plan (manual):** the PR description names its sources at a pin. horizon has no check for it: its ruleset requires
     only the `lander/*` contexts, and the lander reads no PR body. Automating it is R5 of addendum-10: a landscape survey
     of upstream PR-policy and citation checkers comes first, screened by both families, and no check is added until a
     mechanism converges (PROPOSAL);
   - **PR and reads (manual, then lander-checked):** a Claude-family and a GPT-family verdict file, each naming the full
     head SHA, checked by the lander once #1194 lands;
   - **land (PENDING #1194):** the statuses and the trailers in the squash commit;
   - **post-merge audit (PROPOSAL):** the self-audit above.
6. **Statuses until the review App exists.** Commit statuses carry no reviewer identity. This follows the interim of
   [the review-verdict App record](2026-10-09-review-verdict-app-identity.md): a status is a backstop, and the lander
   re-reads its own verdict and receipt files before every merge. **PROPOSAL:** extend that App to horizon. It is scoped
   today to native-agent-stack and us-equities-trading (that record's Decision 1), so the owner would install it on
   horizon, and the record's Transition checks would run on a non-production horizon PR. Only then do horizon's required
   checks bind to the App's integration and the lander post App check runs.
7. **Existing repositories (read-only audit of 21; private record repo-audit-horizon-20261015 with its erratum 01).** This
   changes the 2026-10-10 consolidation (S8) only where horizon changes it:
   - **agent-ecosystem folds INTO horizon (PROPOSAL until its first piece is screened).** Owner: api-actions. Each piece
     moves by a cited horizon pull request once it is shown converged; the repository is archived with a pointer only after
     the repositories that consume it have moved.
   - **north-star-research: unchanged from S8.** S8's record (the owner brief of 2026-10-10, 09:45 ET, by name) folds it into
     native-agent-stack, with trading outputs to us-equities-trading. Its GitHub description named agent-ecosystem; the
     description was corrected to S8's target on the command center's direction on 2026-10-15 (`gh repo edit --description`, exit 0 at 23:33:25Z, only
     the description changed; the previous text is kept as the inverse in a private receipt).
   - **agent-harness and agent-lab:** still fold into native-agent-stack under S8 (practice belongs in public).
   - The trading research and desk repositories are the trading lane's call; the owner's side projects are out of scope;
     archived repositories stay retired.

## Plan facts behind the location

| Fact | Source |
| --- | --- |
| The organisation is on the free plan; the personal account is on Pro | `gh api orgs/native-agent-stack` (`plan.name: free`, read about 20:15Z) and `gh api user` (`plan: pro`, read by the command center at about 20:38Z), 2026-10-15 |
| An organisation private repository refuses rulesets and branch protection | `gh api` `GET .../rulesets` and `.../branches/main/protection` on the organisation's private repository, about 20:15Z: HTTP 403, "Upgrade to GitHub Pro or make this repository public to enable this feature." |
| Rulesets: public repositories on Free; public and private on Pro, Team and Enterprise Cloud | [github/docs@be38ec5d `data/reusables/gated-features/repo-rules.md:1`](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/data/reusables/gated-features/repo-rules.md) (the "Who can use this feature?" text of "About rulesets") |
| Protected branches: the same split | [github/docs@be38ec5d `data/reusables/gated-features/protected-branches.md:1`](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/data/reusables/gated-features/protected-branches.md) |
| Merge queue: public organisation repositories, and private ones only on Enterprise Cloud | [github/docs@be38ec5d `data/reusables/gated-features/merge-queue.md:2`](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/data/reusables/gated-features/merge-queue.md) |
| Code owners in private repositories need Pro, Team or Enterprise | [github/docs@be38ec5d `data/reusables/gated-features/code-owners.md:1`](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/data/reusables/gated-features/code-owners.md) |
| A personal private repository's ruleset is active | `gh api repos/seathatflowsinourveins/us-equities-trading/rulesets/<id>`, `enforcement: active`, about 20:40Z |
| horizon's ruleset refuses a direct push | 2026-10-15T20:40:27Z: an empty commit pushed to main with the local hook bypassed was refused, "GH013: Repository rule violations found for refs/heads/main"; main did not move (`git ls-remote`) |

The captures of these reads are private and cited by name; the plan and the refused push are what they establish, not
the ruleset's full payload or every clone's configuration.

## Sources

- gitleaks 8.30.1, the installed client (`gitleaks version`): `gitleaks git --pre-commit --staged` and `--log-opts` from its `git --help`; configuration `[extend] useDefault = true` from [gitleaks@v8.30.1 `README.md:263-293`](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md#L263-L293).
- git 2.53.0, the installed client: [git@v2.53.0 `Documentation/githooks.adoc:232-257`](https://github.com/git/git/blob/v2.53.0/Documentation/githooks.adoc#L232-L257), pre-push: one `<local-ref> SP <local-object-name> SP <remote-ref> SP <remote-object-name>` line per ref on standard input, a deletion supplied as `(delete)`, and a non-zero exit aborts the push.
- openai/codex `rust-v0.162.1` (the installed codex-cli 0.162.1): `codex-rs/execpolicy/README.md` (`prefix_rule` with `decision = "forbidden"`, and `match`/`not_match` checked at load) and `codex-rs/core/src/exec_policy.rs:662-679` (each trusted config layer's `rules/*.rules` loads).
- Claude Code, [Configure permissions](https://code.claude.com/docs/en/permissions) (read 2026-10-15): deny rules apply in every mode; Bash rules match the whole command text, with `*` for any text, and a deny rule matches any subcommand of a compound command.
- GitHub documentation pinned at [github/docs@be38ec5d](https://github.com/github/docs/tree/be38ec5d78e24172587e61b3c6ff40ace1865c71), as cited above; GitHub REST: [rulesets](https://docs.github.com/rest/repos/rules), [repository transfer](https://docs.github.com/rest/repos/repos#transfer-a-repository), [commit statuses](https://docs.github.com/rest/commits/statuses).
- This repository: [the review-verdict App record](2026-10-09-review-verdict-app-identity.md), [the GitHub automation practice](2026-10-02-github-automation-practice.md), [the in-GitHub Claude review retirement](2026-10-10-retire-in-github-claude-review.md) and [the automation closure](2026-09-22-github-automation-closure.md); `tools/landing/nas_land.sh`, whose shared block the horizon lander (#1194) reuses unchanged.

## Alternatives considered

- **Reuse agent-ecosystem as the repository.** Its scope is the closest fit, but it carries open pull requests and material
  from retired hosts. A clean repository seeded only from converged pieces follows the owner's 2026-10-14 direction to
  curate, not mirror. Its converged pieces move in by pull request instead.
- **Keep the runtime code in native-agent-stack.** That repository is public; host configuration, worker profiles and the
  command center's tooling would need every public-repository privacy scan, and the owner chose private.
- **A private repository in the organisation.** On the free plan GitHub enforces nothing there, so a merge that skipped
  the local gates would show nothing on GitHub until the self-audit ran.
- **Upgrade the organisation to Team or Enterprise Cloud.** That is an owner cost decision. It would bring rulesets (Team)
  or the merge queue (Enterprise Cloud) to private organisation repositories.

## Overturn when

- **The organisation gets a plan with private-repository rulesets (Team), or the owner wants a merge queue (Enterprise
  Cloud).** A transfer back on the free plan would lose the ruleset and gain nothing. Order: the destination plan first;
  then the transfer (`POST /repos/seathatflowsinourveins/horizon/transfer` with `new_owner=native-agent-stack`); then the
  ruleset re-created and verified by a read-back and a refused direct push; only then the next landing.
- **The review App's Transition is verified on horizon** (Decision 6): required checks bind to the App, and statuses stop
  counting.
- **A spoofed `lander/*` status, or a commit on main that the lander did not land, is found:** the command center reviews
  the identity model before the next landing.

## Recovery

A landing that stops after the lander has posted statuses follows: stop; revoke (the lander posts `failure` for each
context it posted; a failed revocation or a lost host leaves successes that are revoked by hand); fix; rerun the local CI
at the new head; obtain new verdicts for it; land again.

## Inverse

Archive the repository; delete it only on the owner's decision. The ruleset's inverse is
`DELETE /repos/seathatflowsinourveins/horizon/rulesets/25195996`.
