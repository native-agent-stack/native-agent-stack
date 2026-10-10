# Decision: top rule, never self-write without a SOTA source, enforced by a required PR check (2026-09-25)

**Decided by:** the owner, in agent-lab session agent-lab-ea on 2026-09-25. The record is agent-lab's
`docs/tasks/2026-09-24-sota-mover-strategies.md`, sections "Top rule adopted" and "Upstream-first correction"; [Claude's explore/plan guidance](https://code.claude.com/docs/en/best-practices) informs research, not that authority. The
same rule lands in agent-lab through PR #71. This change is on branch `claude/top-rule-sota-sources-20260925`,
based on `origin/main@0074a0c3`.

**Scope:**
- `AGENTS.md`, the first rule every session in this repository reads.
- `examples/claude-native/CLAUDE.md`, the portable user-level instructions a new PC installs.
- `.github/pull_request_template.md`, which adds a "SOTA sources" section.
- `.github/workflows/validate.yml`, which adds the `sota-sources` job.
- `.github/main-ruleset.json`, which makes `sota-sources` a required status check.
- `manifests/evidence.json`, with the new hashes for these files.

## Decision

The owner's September 25 decision requires every layer, component and action to have a maintained SOTA
repository or published reference: install directly, or build only from a cited reference implementation.
They made this the first rule in the instruction files; a missing source requires stopping and reporting. This record's decided wording follows:

> **Top rule: never self-write without a SOTA source.** Every layer, component and action comes from a maintained
> SOTA repository or published reference: install it directly, or build only from a cited reference implementation,
> and name that source (repository, pin, file or paper) for every action. With no SOTA source, stop and report
> instead of writing one.

The `sota-sources` job fails a pull request whose description has no non-empty "SOTA sources" section (`##` or
`###`). It reads the description from the `pull_request` payload through [actions/github-script v9.0.0 at `3a2844b7`](https://github.com/actions/github-script/blob/3a2844b7e9c422d3c10d287c895573f7108da1b3/README.md),
pinned to commit `3a2844b7e9c422d3c10d287c895573f7108da1b3`. No description text reaches a shell, and
the job needs only `contents: read`. [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) make it merge-blocking; citation presence establishes no source merit, freshness or native acceptance.

## Evidence

**Why the rule** (`native_proven` on the agent-lab host). On 2026-09-25 an in-house trading engine and its
self-written strategy arms ran on an Alpaca paper account. The arms had no maintained upstream implementation and no
qualified catalog entry: `catalogs/us-equities/engines-strategies.json` qualifies engines and libraries but no
strategy. The session lost $12,443.07, reconciled against 635 broker fills with a $0.00 residual. The arms without
historical support went −6.61R over 35 trades, and a self-written after-hours exit lost $10,928 against the official
close. Their historical tests had already refuted or failed to support the arms:
- ORB-1: −0.76R, n 10,771;
- mover early-entry: 0 of 1,012 development candidates;
- NEWS-3: −19.4 bps/day, t −12.6.

**The check** (`local_integration`):
- The body matcher was run in Node on four cases: empty section, filled, last section and missing.
- zizmor, offline strict, reports no findings.
- actionlint 1.7.12 (pinned, sha256 verified) passes.
- `scripts/validate.py`, `scripts/validate_catalogs.py`, `scripts/build_ecosystem.py --check` and
  `scripts/evidence_manifest.py --check` pass.

**Sources:**
- `actions/github-script`: https://github.com/actions/github-script, v9.0.0.
- The `pull_request` payload: https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request
- Ruleset required checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## PR-body privacy scan (2026-10-10)

The command center's correction #145 found the host account name, inside absolute home paths, in eleven places in
this public repository's pull request descriptions and comments; it masked them all. To keep a new description from
carrying one, the required `sota-sources` job (both byte-identical copies, `pr-metadata.yml` and
`sota-sources-gate.yml`) also scans the current pull request body, read through the REST "Get a pull request" endpoint
as before (<https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request>, `body`; read 2026-10-10T19:54Z):

- the rules are the home-path and credential rules of `scripts/validate.py`'s `PRIVATE_CONTENT` (personal home path,
  Windows user path, encoded home path, Hugging Face, GitHub and Tavily tokens, API secrets, private keys, bearer
  credentials), written in JavaScript; the two session-identifier rules are left out, since a pull request body may
  cite an identifier on purpose;
- no host name is needed: the rules match any `/home/<name>/` or `/Users/<name>/` path, and the documented exemptions
  (`example`, `<user>`, `~/`) pass;
- the job fails closed and its message names only the rule ids, never the matched text;
- `tests.test_sota_sources_gate.GatePrivacyTests` runs both copies on fixtures built at run time (so the test file
  carries no private-looking value), checks that a missing section and a private body are reported together, and runs
  every rule against its Python original on a shared corpus. On the job before this change the new tests fail (21
  failures).

Callers of the reusable gate get the scan when they bump their pin.

## Alternatives considered

- **A checklist item in the PR template only.** Rejected: nothing fails, and the rule was already implied by the core
  rule ("research upstream before building"), yet it did not stop self-written arms.
- **A reviewer-only rule.** Rejected: reviewers check what is in front of them, and a missing source is an absence.
- **An automated source check per file.** Rejected for now. No maintained upstream tool maps changed lines to cited
  sources, and writing one would itself break the rule.

## Comparison that would overturn it

Count, over at least 30 merged PRs, those in which the required "SOTA sources" section was satisfied only by filler.
A reviewer finds no real source for at least one change, measured by an independent review of each PR's listed
sources. If that share exceeds 20%, the section check is replaced by a stronger mechanism: required reviewer sign-off
on sources, or a maintained upstream provenance tool once one exists. If PRs are blocked because a legitimate change
has no possible upstream (for example, repository-specific configuration), add an explicit, reviewed exemption line
rather than dropping the check.
