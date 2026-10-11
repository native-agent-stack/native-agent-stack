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

### After the first review (2026-10-11)

The co-op's GPT read at `07595323` found three gaps, now closed in both copies of the job:

- **The body is judged before it is read.** A description that is not text, is longer than 65,536 characters, holds a
  lone surrogate, or holds a control character other than tab, LF or CR fails with one fixed rule id (`body-type`,
  `body-size`, `body-encoding`, `body-control`), and nothing else is reported. GitHub's REST docs state no length
  limit for `body`. The 65,536 figure is the API's own refusal text, "body is too long (maximum is 65536 characters)",
  as quoted in <https://github.com/w3c/webref/pull/245> (read 2026-10-11T04:51Z; page sha256
  `6d7e066850b61ad0b9d674ad939fa84c557c2afd3113349fbf4fd26452504470`). It is a reported vendor message, not a
  documented limit, and no body that long was sent to GitHub. `String.prototype.isWellFormed` reports lone surrogates
  (MDN, read 04:51Z, sha256 `cd0a2f9794cc85917bcb6aaa48c28c21bfd42810f5f9cf0398a31c6e26f3b8cd`).
- **Escaped and rendered forms are judged too.** The rules run over the body as written and over four forms, each
  decoded once from it, never to a fixed point. They are percent escapes, JSON `\uXXXX` and `\/` escapes, HTML
  numeric references and a short list of named ones, and Markdown's rendered text. The rendered form keeps link and
  image text and autolinks, resolves backslash escapes, and drops backticks, the inline HTML elements GitHub renders
  (any other `<word>` stays, so a `<name>` placeholder is not read as a tag) and emphasis markers in pairs around a
  word with no separator inside (so a glob such as `Users/*/` keeps its star). Link destinations stay in the body
  itself.
  `<user>`, `example` and `~/` still pass in every form. `scripts/validate.py`'s publication scan does not decode;
  the gate's pre-pass adds to it. A carried email rule would run over the same forms.
- **A macOS home in any case.** The gate-only `macos-user-path` rule catches `/users/<name>` in any case except the
  exact `/Users/` that `personal-home-path` already reports, when nothing precedes the slash but a non-word
  character. `validate.py` keeps the exact `/Users/`. Over this branch's tracked tree at `07595323` the anchored
  case-insensitive form matched 11 times in 5 files: API routes in trial logs and evidence, and a test fixture. The
  unanchored form matched 889 times in 24 files.
- **Python's classes, spelled out.** `validate.py`'s patterns are str patterns, so `\w` is a Unicode letter or
  number or `_`, `\s` is `str.isspace()`, `$` also matches before a final newline, and `re.IGNORECASE` lets
  `[A-Za-z]` match U+0130, U+0131, U+017F and U+212A (Python 3.13 `re` docs, read 04:51Z, sha256
  `19195ec76056c9b8088394ba81014ff47e1d4040a8eae092e450412f75f5c378`). JavaScript's `\b` counts only ASCII word
  characters unless the `i` and `u` flags are both set, and then also what case folding maps onto them (MDN, word
  boundary assertion, read 04:51Z, sha256 `cf1a8e2090e46141531ff492f0e3e49dfbd2811aa530229d821cbfc2cc253878`). The
  gate's rules therefore use the `u` flag and explicit classes (`\p{L}\p{Nd}\p{Nl}\p{No}_`, which on Python
  3.13.16 is exactly the set `\w` matches), lookaround boundaries and spelled-out letter cases. No rule takes the
  `i` flag: under `u`, case folding puts U+0345 in `\p{L}`, and Python's `\w` excludes it.

A new test compares every rule with its Python original over 156,277 code points: all Python 3.13.16 assigns,
except surrogates and the supplementary private-use planes. Node 24.21 carries Unicode 17.0 and Python Unicode
15.1, so code points new since 15.1 are left out. Each code point goes into 69 templates where a class, boundary
or folded letter decides the verdict, 10,783,113 comparisons with no difference. Further tests:

- the read's probe cases: the escaped and rendered forms, the mixed-case macOS home, the Unicode pair, and the
  oversized and NUL bodies;
- every credential rule one below, at and one above its minimum length, alone and glued to Unicode word characters;
- the body guards at the limit, one over and far over it, on each control and encoding case and on four non-text
  bodies;
- every rule carries the `u` flag.

The new tests fail on the job at `07595323` (121 failures, 2 errors). Twenty-two weakened copies of the new script
were run:

- 21 fail the tests: each removed form or guard, a larger budget, the inline-tag list widened to every tag or removed,
  emphasis removed unpaired or not at all, JavaScript's `\b`, `\w` or `\s`, `[A-Za-z]` without U+0130 and U+0131,
  `s` without U+017F, the `i` flag restored, and the macOS rule removed.
- An earlier form of link destinations alone survived because it is redundant (a destination is part of the body),
  and it was removed.
- `$` for the faithful end-of-input lookahead survives and is equivalent: in both places the class beside it already
  holds `\n`.

The new gate was also run over the live description of every open pull request at 2026-10-11T05:00Z (89), with only
rule ids printed. Every one gets the same outcome as on `07595323`: 88 pass and one lacks its SOTA sources section.
Before the rendered form was narrowed, one description failed through a `<name>` placeholder read as a tag.

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
