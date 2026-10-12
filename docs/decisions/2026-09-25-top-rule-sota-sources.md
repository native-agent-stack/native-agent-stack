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
this public repository's pull request descriptions and comments; it masked them all. So that a new description
carrying one is detected and its pull request kept from landing (a failing check cannot withdraw a published
description; see "Publication comes first" below), the required `sota-sources` job (both byte-identical copies, `pr-metadata.yml` and
`sota-sources-gate.yml`) also scans the current pull request body, read through the REST "Get a pull request" endpoint
as before (<https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request>, `body`; read 2026-10-10T19:54Z):

- the rules are the home-path and credential rules of `scripts/validate.py`'s `PRIVATE_CONTENT` (personal home path,
  Windows user path, encoded home path, Hugging Face, GitHub and Tavily tokens, API secrets, private keys, bearer
  credentials), written in JavaScript; the two session-identifier rules are left out, since a pull request body may
  cite an identifier on purpose;
- no host name is needed: the rules match any `/home/<name>/` or `/Users/<name>/` path (and, since the command
  center's read of `4e5ef13d`, a WSL home through its Windows UNC path), and the documented exemptions (`example`,
  `<user>`, `~/`) pass;
- the job fails closed and its message names only the rule ids, never the matched text;
- `tests.test_sota_sources_gate.GatePrivacyTests` runs both copies on fixtures built at run time (so the test file
  carries no private-looking value), checks that a missing section and a private body are reported together, and runs
  every rule against its Python original on a shared corpus. On the job before this change the new tests fail (21
  failures).

Callers of the reusable gate get the scan when they bump their pin.

### After the first review (2026-10-11)

The co-op's GPT read at `07595323` found three gaps, now closed in both copies of the job:

- **The body is judged before it is read.** A description that is not text, is longer than the gate's bound, holds a
  lone surrogate, or holds a control character other than a tab or a line break (LF and CR at first; since the
  command center's read of `4e5ef13d`, every paragraph separator, see the last section) fails with one fixed rule id (`body-type`,
  `body-size`, `body-encoding`, `body-control`), and nothing else is reported. The bound was first 65,536 UTF-16 code
  units, on the premise that GitHub refuses a longer body; that premise was wrong, and the bound is now the gate's own
  (correction in the next section). `String.prototype.isWellFormed` reports lone surrogates
  (MDN, read 04:51Z, sha256 `cd0a2f9794cc85917bcb6aaa48c28c21bfd42810f5f9cf0398a31c6e26f3b8cd`).
- **Escaped and rendered forms are judged too.** The rules run over the body as written and over four forms, each
  decoded once from it, never to a fixed point. They are percent escapes, JSON `\uXXXX` and `\/` escapes, HTML
  numeric references and a short list of named ones, and Markdown's rendered text. The rendered form keeps link and
  image text (a label without brackets in it) and autolinks, resolves backslash escapes, and drops backticks, the inline HTML elements GitHub renders
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

### After Codex's review (2026-10-11)

Codex's GitHub review of `de4eed8f` (requested at 08:19Z) raised four P1 and three P2 findings. Six are fixed in both
copies of the job. The seventh, about publication order, is answered without a code change:

- **Correction: GitHub does not refuse a description over 65,536 characters.** The first fix took that limit from a
  refusal message quoted in another repository's pull request, and counted it in UTF-16 code units. Probes went
  through the REST update of this pull request's own description (2026-10-11T13:34Z to 14:19Z). Each probe was
  restored at once, and the description read back equal to the original. These were stored whole, each with an entry
  in the edit history:
  - 65,537 ASCII characters;
  - 65,536 astral characters (131,033 UTF-16 code units, 262,027 UTF-8 bytes);
  - 32,788 code points that are 65,537 UTF-16 code units;
  - 65,539 code points of combining sequences;
  - 262,144 ASCII characters.

  Three probes kept nothing: 262,145 ASCII characters, 262,199 UTF-8 bytes of astral text (65,579 code points) and
  1,048,577 characters. The REST update thus keeps at most 262,144 UTF-8 bytes. Over that, it still answers 200 and
  echoes the body, while a GET returns the original and the edit history records nothing. A first version of this
  note, pushed as `d81969dd`, said the 1,048,577-character body was stored, on the strength of that 200 answer; a GET
  read-back corrected it. Creating a pull request was not probed. This repository has also carried a
  75,726-character description (#786).

  The bound is therefore the gate's own: 262,144 code points, so an astral character counts once. A code point takes
  at least one UTF-8 byte, so no description the update stores reaches the bound. It is also about 3.5 times the
  longest description seen here. On Node 24.21, 52 adversarial shapes at the bound each get a verdict within
  0.46 s on this 64-CPU host at a load of about 25 (four runs, worst 0.39, 0.43, 0.41 and 0.46 s), measured at the round-2 commit
  (the last section). Earlier versions of this sentence said "within 0.3 s" for every body at the bound, which an
  unclosed link of whitespace broke, and "within 0.25 s", which the command center's micro at `752d9618` measured as
  0.26 to 0.28 s at a load of about 26.
- **The decoders compose.** Each decoder still runs at most once along a chain, never to a fixed point. The rules
  now see every order of every subset of the four decoders: 65 forms, counting the body. A slash written as a
  character reference around a name in emphasis is therefore read as GitHub displays it. Codex suggested a pinned
  GitHub-compatible renderer. The job runs inline in `actions/github-script` with no dependency install, so the
  rendered form stays the handwritten approximation described above. A Markdown construct it does not model, such as a
  reference definition or nested emphasis, can still hide a name from it.
- **Any private-key label.** In `validate.py` and the gate, the private-key rule now takes gitleaks's header form,
  `-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----`
  ([gitleaks `config/gitleaks.toml`, rule `private-key`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/gitleaks.toml#L2784-L2788)).
  The rule drops gitleaks's `(?i)` and stays case-sensitive as before. PKCS #8 `ENCRYPTED PRIVATE KEY` and OpenPGP
  `PGP PRIVATE KEY BLOCK` headers are caught; `PUBLIC KEY` is not. Over this branch's tracked tree the wider rule adds no
  match.
- **A repository named like a graph id passed the gate, until fix round 2 removed the exemption (the last
  section).** The graph-id form of `encoded-home-path` (`home-<name>-code-`
  with no leading dash) failed a cited URL such as `github.com/<owner>/home-<name>-code-review`. In the gate only,
  that form was not read as a repository name: the segment right after one owner segment of a public code host's URL,
  where the URL starts its token (narrowed after the command center's read of `4e5ef13d`, the last section; before
  it, the whole path within 256 characters of the host was exempt). The hosts are
  `github.com`, `githubusercontent.com`, `gitlab.com`, `bitbucket.org`, `codeberg.org`, `huggingface.co` and `sr.ht`,
  with up to four subdomain labels, in lower case. (At `fc60da90` any `http(s)` URL was exempt; the second GPT read
  corrected that.) The check runs only where `home-` occurs. The first form tried scanned back from every position:
  13.7 s on a 262,144-character run of `home-a`, against 0.1 s without it. Still caught:
  - a graph id in a cache path (`~/.cache/codebase-memory-mcp/home-<name>-code-<project>.db`);
  - the dashed form in any URL;
  - the graph-id form in any other URL: a loopback, `localhost`, `*.localhost`, private-address or unlisted host,
    userinfo or a query string after a code host, or a code host written in upper case.

  `validate.py` keeps the URL case, because Python's lookbehinds are fixed-width.
- **The graph-id form is bounded.** It searched from every `home-` to the end of its run. A 262,144-character run of
  `home-a.b-c_d-` took 21 to 28 s per form in the gate and 93 s in `validate.py`, so a body whose forms differ could
  run past the job's 2-minute limit. In both, the name now runs at most 256 characters to `-code-` (`[\w.][\w.-]{0,255}`). On 200,000
  random strings of short pieces the old and new rules agree; they differ only for a name over 256 characters. The
  same run now takes 0.05 s in Python. A regression test holds both the gate and `validate.py` to a time limit at the
  bound.
- **Redundant leading slashes.** `macos-user-path` now accepts any number of leading slashes, so `///users/<name>` is
  caught (POSIX resolves three or more leading slashes to one). A `file:///users/<name>` URL is caught too, by this rule
  and, as in Python, by `windows-user-path`. A doubled slash inside a URL path still passes.
- **Every rule is carried.** A new test fails when the two scans drift: when `validate.py`'s `PRIVATE_CONTENT` gains or
  renames a rule the gate does not carry (the two session rules aside), or when the gate's rule ids differ from that
  mapping plus `macos-user-path`. A carried email rule must therefore join the gate when `validate.py` adds it.
- **Publication comes first (no change).** GitHub stores a description before any check runs, so a failing check
  detects a leak but cannot withdraw it. The gate is the backstop: it keeps such a pull request from landing and names
  the rule. Prevention happens before sending, for example by scanning the text with
  `python3 scripts/validate.py --scan-file <body.md>` before `gh pr create` or `gh pr edit`. That scan runs
  `validate.py`'s rules without the gate's decoded forms.

The new tests fail on the job at `de4eed8f` (22 failures: seven of the new privacy cases, the body guards at the new
bound and in code points, and the bounded-time test). The coverage test passes there by design, since it guards
against later drift. Eleven weakened copies of the new job and rules were run, and each fails the tests:

- the decoders not composed;
- the bound in UTF-16 code units, or 65,536 again;
- the old private-key labels in both scans, or in the gate only;
- the URL exemption removed, or unbounded (34.6 s at the bound);
- one leading slash only;
- the graph-id bound removed in both scans, or 255 in the gate only;
- a `validate.py` rule the gate does not carry.

The new gate was also run over the live description of every open pull request at 2026-10-11T13:56Z (88), with only
rule ids printed. Each gets the same outcome as under the `de4eed8f` gate.

### After the second GPT read (2026-10-11)

The co-op's GPT read at `fc60da90` (Astra, CHANGES_REQUESTED) reproduced two P2 regressions in the new lines. Both
are fixed in both copies of the job, on a rebase onto main `0f153784`:

- **A graph id in a local URL passed.** The URL exemption at `fc60da90` skipped the graph-id form after any `http(s)`
  scheme, so `http://127.0.0.1:8788/p/home-<name>-code-<project>` and the same id under `https://localhost/` passed
  both copies, while `validate.py` refused both. The exemption is now limited to the path of a public code host's URL
  (above), an allowlist rather than a list of local hosts, so private addresses and intranet names stay caught too.
  (That path still reached an inner `https://` and Markdown delimiters; the read of `4e5ef13d` narrowed it to a
  repository name, and fix round 2 removed it.)
  New cases cover loopback, `localhost`, `[::1]`, `*.localhost`, a private address, an unlisted public host, userinfo,
  a query string and an upper-case host; each agrees with `validate.py`. The public-repository control, now also on a
  code host's subdomain, passes.
- **Unmatched brackets ran past the job's limit.** The link and reference-link labels admitted `[`, so from every
  unmatched `[` the decoder scanned to the end of the body, and composition repeats that decoder. The reader's run of
  262,144 `[` gave no verdict within 125 s, against the job's 2-minute limit; here, 4,096 took 0.87 s and 8,192 took
  3.26 s. A label now holds no bracket, as in CommonMark, in all three classes. That run now takes 0.16 s, and 21
  adversarial shapes at the bound (bracket, parenthesis, tag, entity, percent, emphasis, backslash, backtick and
  graph-id runs) take at most 0.26 s each. That set missed an unclosed link of whitespace, which the command center's
  read of `4e5ef13d` found (the last section). The bounded-time test adds three bracket runs. The 41 earlier privacy-case
  outcomes are unchanged, including a name split by a Markdown link.

The new tests fail on the rebased previous head `ee2070f0` (18 failures, 1 error). Thirteen weakened copies were run,
and twelve fail the tests:

- the exemption for any host;
- `localhost` or a private address added to the allowlist;
- userinfo and query strings allowed in the path;
- no subdomain;
- `[` allowed in the inline-link label or in the reference-link label;
- five earlier guards: composition off, UTF-16 size, one leading slash, the graph-id bound, and a rule the gate does
  not carry.

The thirteenth allows `[` in the reference target and survives. It is equivalent for run time: a match needs
`[label][`, and the target scan stops at the next `]`, so it cannot rescan. It differs only on a target containing
`[`, which CommonMark does not accept as a reference.

The reader's P3 follow-ups are not in this change: two live line locators that the diff moved
(`blueprints/runtime-workers/openhands/resolver.py:456` and `blueprints/native-skill-practice/p1/README.md:14`); pinned
captures for the handwritten Markdown approximation, the URL exemption, the 256-character bound and the POSIX
leading-slash rule; the repeated-decoding boundary, already stated above; and existing hostname references in the
manifest.

### After the command center's Claude read of `4e5ef13d` (2026-10-12)

The command center's Claude read at `4e5ef13d` (CHANGES_REQUESTED) found four defects, and its adjudication ruled two
of them privacy P1s. All four are fixed in one commit, in both copies of the job and, for the home-path rule, in
`validate.py`:

- **B3 (P1): the code-host exemption let an encoded home path through.** It skipped the graph-id form anywhere within
  256 characters after a listed host, across `)`, `(`, `]`, `[`, `,`, `;`, `|`, `*` and an inner `https://`. So a graph
  id behind `https://github.com/` inside a local URL or its query, as the destination of a link whose label is a
  code-host URL, after a comma, or deeper in a code-host path passed both copies, while `validate.py` refused each. The
  exemption now covers only a repository name: the segment right after one owner segment (`[A-Za-z0-9_.~-]{1,100}`) of
  a listed host's URL, and the URL must start its token, after whitespace, a quote, `<`, `(` or `[`. The check still
  runs only where `home-` occurs and looks back over a bounded window, so it stays linear.
- **B4 (P1): a WSL home through its UNC path passed all three scans.** `\\wsl.localhost\<distro>\home\<name>`,
  `\\wsl$\...` and the JSON-escaped form carry the account name, and this repository's own WSL tooling writes the
  form (masked). `personal home path`, in `validate.py` and both copies, now also reads `\\wsl$\`, `\\wsl\` and
  `\\wsl.localhost\` in any case, with one or two backslashes per separator, then `<distro>\home\<name>`, with the POSIX
  form's `example` exemption and end. Sources: Microsoft's "Working across file systems"
  (<https://learn.microsoft.com/en-us/windows/wsl/filesystems>, read 2026-10-12T03:48:54Z, sha256
  `fc8542ae8955e3ee1c732b33a83f9e8f34d596ffde35bf3a2463d2badcca791d`; its source, MicrosoftDocs/wsl@`a1473a69`
  `WSL/filesystems.md:34`), `WSL/wsl-config.md:162` (`\\wsl.localhost\Ubuntu-20.04\etc\wsl.conf`), and the WSL
  release notes, `WSL/release-notes.md:24` (Build 21354: the `\\wsl.localhost` prefix, and `\\wsl$` keeps working),
  `:76` (Build 20175: `\\wsl`) and `:145` (Build 19013: the `\\wsl$` check is case-insensitive). The 19 tracked
  lines that write the form, in 11 files, stay clean, and so does the rest of the tree.
- **B1 (P2): the body guard turned a required check red.** It refused U+001C and U+0085, while #1003's mirror
  (`tools/sota-sources/verify_sources.py`; an earlier version of this line named `scripts/verify_sources.py`, which
  does not exist) counts them as section content, since its `JS_TRIM` (`:142`) leaves them, so `tests.test_verify_sources` failed in shard 4 of the
  required `validate`. The guard now admits tabs and line breaks, a line break being a paragraph separator by Unicode's
  Bidi_Class B: LF, CR, U+001C to U+001E and U+0085 (Python's `unicodedata`, UCD 15.1.0). Every other C0 and C1
  control is still refused; a test runs all 65 through both copies. The failure message is unchanged.
- **B2 (P2): the link decoder backtracked quadratically.** Three adjacent whitespace quantifiers around a possibly
  empty destination retried every split of a run: `[a](` and 32,768 spaces took 42 s, and 65,536 gave no verdict
  within 130 s. The parentheses are now read as runs that cannot overlap, with no line break and one level of nested
  pairs (`\([^()\n]*(?:\([^()\n]*\)[^()\n]*)*\)`), so an unclosed `(` is scanned once to the end of its line. A
  destination with spaces, or a link with a title, is still decoded. A link split across lines, or whose title holds an
  unmatched parenthesis, was no longer decoded, a regression from `4e5ef13d` that fix round 2 restores.

On Node 24.21, 35 adversarial shapes at the bound each got a verdict within 0.25 s in this run (the micro at
`752d9618` measured 0.26 to 0.28 s at a load of about 26; the last section restates the bound): the second read's 21, plus
unclosed links of spaces, line feeds and tabs, nested, quoted and repeated link runs, code-host owner runs and UNC
runs. One of them is refused for its own content: after Markdown's unescaping it holds a home named `wsl`.

The new tests fail on `4e5ef13d`'s job and `validate.py` (34 failures, 1 error). They include the four subtests of
`tests.test_verify_sources` that kept the required check red. Thirteen weakened copies were run, and all thirteen
fail the tests:

- the exemption back to 256 characters after the host, or a URL that need not start its token;
- an owner segment that may hold `,`, `|` and `;`, or `/`;
- no UNC form in the two copies, or in `validate.py`; no `\\wsl` prefix without a suffix; no `example` exemption in
  it; single separators only (no JSON-escaped form);
- U+0085 refused again, or U+001F admitted;
- the old link regex, or one whose runs overlap (each gives no verdict within the test's 60 s).

Old and new gates give the same outcome on the live description of every open pull request (76) and of the
latest 400 in any state, at 2026-10-12T04:24Z; neither names a rule on any of them. Only rule ids were printed.

Boundaries this states: the exemption takes exactly one owner segment, so a GitLab subgroup's repository named like a
graph id is refused, as is a code-host URL glued to a preceding word character (fix round 2 removes the exemption).
The UNC form needs a distribution name of at most 64 characters (255 since fix round 2); a home under another share, such as `\\host\c$\Users\<name>\`, and `\home\<name>\`
without a prefix stay follow-ups, as the read listed them.

### After the command center's Claude micro of `752d9618` (2026-10-12, fix round 2)

The command center's Claude micro at `752d9618` verified B2, B3's five bodies, B4 and the fail-first account, and found
three blockers; the command center's adjudication ruled M1 and M2 privacy P1s and upheld Codex's T8 as P1. The class
recurred three times (B1 to M1, B3 to M2, and T8), so the fix moves to the input rather than the patterns (rule 4).
One commit, in both copies of the job and, for the home-path rule, in `validate.py`:

- **M1 and T8: a projection for reading.** The guard admits U+001C to U+001E and U+0085, and no form removed them, so
  a home path, a graph id, a UNC home, a Windows profile or a token split by one passed both copies (52 of 68 of the
  micro's bodies; at `4e5ef13d` all 68 were refused). An HTML comment split a value the same way (T8), and GitHub hides
  it. The rules now read the body as written and a projection of it: HTML comments removed as CommonMark reads them
  (0.31.2, spec.txt:8986: `<!-->`, `<!--->`, or `<!--` up to `-->`; <https://spec.commonmark.org/0.31.2/spec.txt>,
  read 2026-10-12T05:21:42Z, sha256 `bfef4ddc97276b6ab6c2a28ace48478e35b1c50e60cde9f517ab8ab030aa3b82`), found by one
  linear scan, and every character of general category Cc, Cf, Zl or Zp but tab, LF and CR removed. Those are 234 code
  points in the Unicode 17.0.0 database, which Node 24.21 carries (ICU 78.3), and the same 234 in Python 3.13.16's
  15.1.0 (`extracted/DerivedGeneralCategory.txt`, <https://www.unicode.org/Public/17.0.0/ucd/extracted/>, read
  05:21:42Z, sha256 `d62e5bab70ca74f099343f71224fa051cb1fdd61a1ab45c0488c44cfc0b6102e`; Node's
  `\p{Cc}\p{Cf}\p{Zl}\p{Zp}` gives the same set). The decoders compose over the projection as over the body, and in
  the projection's chains each decoder's output is projected again, so a reference that decodes to a comment or a
  format character is removed too. Clean bodies that carry these characters still pass, as #1003's mirror expects.
- **M2: the code-host exemption is removed.** A code-host URL glued inside another URL after `(`, `'`, `"`, `[`, `<` or
  `>` still exempted a graph id (the real names caught 0 of 3 in the gate, 3 of 3 in `validate.py`). After two rounds
  of bypasses the exemption is gone, and the gate reads the graph-id form as `validate.py` does. A repository named
  like a graph id is refused by both scans; it is cited another way.
- **The rarer UNC forms.** A device UNC path (`\\?\UNC\wsl.localhost\...`, `\\.\UNC\wsl$\...`), either slash
  (`//wsl$/<distro>\home\<name>`), a distribution name with a space or up to 255 characters, and a Windows profile
  through the distribution's mount (`<distro>\mnt\<drive>\Users\<name>`) are now read in all three copies.
  Sources: dotnet/docs@`8a189e07f74e50fa0e49551857c3b88d69a7630b` `docs/standard/io/file-path-formats.md:94-95` (the
  `\\.\UNC\` and `\\?\UNC\` device paths), `:155` (forward slashes are separators) and `:206` (names are
  case-insensitive); file sha256 `82ed20b86d1d6fc189337703f40e95de6ec9ab624439662a8ed6ea1348cfc64c`, read 05:22:04Z.
  The B4 citation now names `WSL/filesystems.md:34` only; `:22` is the `/mnt/c` line.
- **The two link shapes 752d9618 stopped decoding** (a link whose title is on the next line, and a title holding an
  unmatched parenthesis) are decoded again by a second link pattern in CommonMark's own shape. Each whitespace run in it
  is taken whole (`(?=(\s*))\N`), so it stays linear.
- **M3:** the mirror's path and reading are corrected above and in the job's comment.

On Node 24.21, 52 adversarial shapes at the bound each get a verdict within 0.46 s on this 64-CPU host at a load
of about 25 (four runs, worst 0.39, 0.43, 0.41 and 0.46 s): the earlier 35, plus unclosed comments, quote,
whitespace and pointy link runs, admitted and format character runs, comment- and format-split values, and device
and slash UNC runs. Two are refused for their own content: a UNC home named `wsl`, as before, and a format-split home
path.

The new tests fail at `752d9618` (183 failures). Twelve weakened copies were run, and all twelve fail the tests:

- no projection, comments kept in it, no character removed from it, only Cc removed, or the projection's chains not
  projected again;
- the code-host exemption back, as at `752d9618`;
- the titled link pattern removed;
- no device UNC prefix in the two copies, or in `validate.py`; no `mnt\<drive>\Users` branch; distribution names of 64
  characters at most; backslashes only (the two copies), as at `752d9618`.

Old and new gates give the same outcome on the live description of every open pull request (76) and of the latest
400 in any state, at 2026-10-12T05:31Z; neither names a rule on any of them. Only rule ids were printed.

Codex's T9 (`/ho&#x110000;me/<name>/x` is refused, though GitHub renders U+FFFD there) and T11 (an unresolved reference
link such as `/home/[al][missing]ice/x` is refused) are fail-safe false positives on contrived text. They stay as they
are and are follow-ups.

Boundaries this states: the projection removes characters, it does not render Markdown, so a value split across a
line break or by a carriage return is still not joined; and a value hidden under two layers of the same encoding is
not decoded, as before.

### After the command center's Claude micro of `e15d1259` (2026-10-12, the terminal commit)

The command center's micro at `e15d1259` found three more ways to hide a split from the projection, each a privacy P1,
and its adjudication made this the terminal commit. The class had recurred three times (B1 to M1 to N3, T8 to N1, and
the entity map to N2), so each enumeration is replaced by the set a specification defines (rule 4), in both copies:

- **N1: raw HTML other than a comment.** An unknown tag, `<font>`, `<input>`, CDATA or a processing instruction split
  a home path or a token; GitHub drops the markup and shows the value whole. The projection now removes every raw-HTML
  construct of the GFM grammar: an open tag, a closing tag, a comment, a processing instruction, a declaration and a
  CDATA section (github/cmark-gfm@`587a12bb54d95ac37241377e6ddc93ea0e45439b` `test/spec.txt:9360-9431`, "Raw HTML";
  file sha256 `7d8e5814befec287ac116786d81ff14e0adc9b13295b4494649e995408fd871c`). It reads them from the body as
  written only, as GitHub parses raw HTML there and never in what a reference or an escape decodes to, and it treats
  a backslash-escaped `<` as text (CommonMark's backslash escapes). One left-to-right scan finds them; once a closer
  (`-->`, `?>`, `]]>`, `>`) is missing after one opening, later openings of that kind are skipped, so the scan stays
  linear. A construct that stands alone between separators (whitespace, a slash or a backslash, or either end), such
  as the documented `<user>` placeholder in `C:\Users\<user>\x`, was kept: removing it would join the separators
  around it into a different path. Addendum 01 below narrows that to tags, for the home-path rules only.
- **N2: named references outside the 16-name map.** `&shy;`, `&zwj;`, `&UnderBar;` or `&dollar;` split or completed a
  value. Named references are now decoded from the HTML5 table as cmark-gfm pins it (`src/entities.inc` at the same
  commit, 2,125 names; the spec names WHATWG's `entities.json` as the authority, `test/spec.txt:5946-5950`), limited
  mechanically to the 297 names whose text, after the projection's character step, is ASCII or nothing; no other
  name can complete or hide a value the rules read. `tests/fixtures/cmark-gfm-entities-587a12bb.json` keeps the table
  (sha256 of the source file `3932dfa630067813f47be6ae0072e1645c1183bde41140b51443f50857c88909`), and a test
  regenerates the subset from it and compares it with the job's map; another, where the mirror is present, compares the
  fixture with `src/entities.inc` at the pin. The old map's `&hyphen;` and `&dash;` gave ASCII `-`; the table gives
  U+2010, which no rule reads.
- **N3: invisible characters outside Cc, Cf, Zl and Zp.** A variation selector, the combining grapheme joiner, a Hangul
  filler or a reserved default-ignorable split a value. The projection also removes every Default_Ignorable_Code_Point
  (Unicode 17.0.0 `DerivedCoreProperties.txt`, 4,174 code points, <https://www.unicode.org/Public/17.0.0/ucd/>, read
  2026-10-12T08:01:08Z, sha256 `24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08`; Node 24.21's
  `\p{Default_Ignorable_Code_Point}` matches the same 4,174).
- **Width forms.** The projection applies NFKC (`String.prototype.normalize`), which folds a fullwidth solidus,
  fullwidth letters and mathematical letters to ASCII.

The rules still run on the body as written too, so the projection only adds catches; clean bodies stay clean,
including #1003's mirror tests and the 19 masked lines. **What the gate guarantees** (with addendum 01 below): no
value spelled with its own characters is published, whatever is inserted between them. **What it does not:** a look-alike that substitutes a
character (a division slash, a Cyrillic letter) rather than inserting one; closing that needs the UTS #39 confusables
data, a P2 follow-up (a skeleton projection).

On Node 24.21, 67 adversarial shapes at the bound each get a verdict within 0.47 s on this 64-CPU host at a load
of about 18 (four runs, worst 0.46, 0.46, 0.45 and 0.47 s), the earlier 52 plus unclosed markup of each kind, attribute runs, reference
runs and width-form runs.

The new tests fail at `e15d1259` (51 failures, 2 errors). Eleven weakened copies were run, and all eleven fail the tests:

- no markup removal; no closing tags; no processing instructions; no CDATA; no placeholder exception; an escaped
  `<` read as markup; unclosed openings rescanned (no verdict within the test's 60 s);
- names of at most 8 letters, as before; the map without `UnderBar`;
- no Default_Ignorable_Code_Point; no NFKC.

Old and new gates give the same outcome on the live description of every open pull request (75) and of the latest
400 in any state, at 2026-10-12T08:21Z; neither names a rule on any of them. Only rule ids were printed.

Boundaries this states: raw HTML inside a code span or block is removed too, though GitHub shows it as text, so such
contrived text can be refused; a value split across a line break, by a carriage return, or under two layers of one
encoding is not joined.

**Addendum 01 (the command center's, at `e15d1259`, from the co-op's GPT read at `30f2e005`):** the placeholder
exception shielded a comment standing between whitespace, so `x Bearer <!--x--> ` followed by a 40-character token
was refused at `260803e1` and accepted at `30f2e005`, while GitHub (cmark-gfm at the pin) hides the comment and shows
the token whole; a tag, a processing instruction or CDATA in the same place passed at both heads. The projection is
now two, as the read proposed and the command center accepted:

- the credential rules (Hugging Face, GitHub, Tavily, API secret, private key, bearer) read the body with every
  raw-HTML construct removed, wherever it stands;
- the home-path rules (personal, Windows, encoded and macOS homes) read the body with every comment, processing
  instruction, declaration and CDATA section removed, and keep only a tag that stands alone between separators, the
  documented placeholder form;
- both still compose with the decoders, and the rules still read the body as written.

Regressions, in both copies: each construct (a comment, an open and a closing tag, `<font>`, `<input>`, a processing
instruction, a declaration, CDATA) between `Bearer` and its token, and at the start of every ported token's value
(`ghp_`, `github_pat_`, `sk-ant-`, `hf_`, `tvly-`); and a comment, a processing instruction, a declaration or CDATA
between the path separators of a Windows profile. The new tests fail at `30f2e005` (12 failures: the 8 bearer forms
and the 4 path forms) and pass here; the placeholder controls pass on both. Three weakened copies (one projection for
every rule; comments and processing instructions kept as placeholders; no placeholder exception) each fail them. AWS
and Slack-style token prefixes (`AKIA`, `xox`) have no ported rule here, as the original scope states, so they are not
among the regressions. On Node 24.21, 70 adversarial shapes at the bound each get a verdict within 0.83 s on this
64-CPU host at a load of about 15 (four runs, worst 0.67, 0.83, 0.63 and 0.65 s); the extra projection costs about a
third more time.

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
