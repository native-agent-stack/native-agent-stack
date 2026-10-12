# Refuse email addresses in the publication scan — 2026-10-11

Claude Code adds the signed-in account's email address to every session's context.
Nothing in `scripts/validate.py` refused an address, so a session could carry it into a
public evidence file and CI would pass. `PRIVATE_CONTENT` now has an `email address`
rule. The repository scan (`Validator.scan_publication`), `--scan-file`, the host-receipt scan
in `scripts/host_receipts.py` and every tool that imports `PRIVATE_CONTENT` apply it. Findings name the rule and the path, never the
address.

## The rule

It matches an RFC 5322 3.4.1 `addr-spec` whose local part is a dot-atom: every `atext` character
of 3.2.3 and `.` (rfc5322.txt:679-690). The left boundary refuses the same characters, so a match
never starts inside a longer local part. It ignores case, because DNS names are case-insensitive
(RFC 4343). A local part needs a letter or a digit: one of symbols only (`` `@AGENTS.md` ``, a
quoted `@import`) names no mailbox. That guard is this change's own, added when the wider class
turned 16 code spans of Claude Code imports into matches. It does not match these forms:

- GitHub's `users.noreply.github.com` commit addresses, and the `noreply@` commit
  identities of Anthropic (the Claude Code co-author trailer) and GitHub.
- The RFC 2606 reserved names, exactly (rfc2606.txt:106-121): `example.com`, `example.net` and
  `example.org` with their subdomains, and the `.test`, `.example`, `.invalid` and `.localhost`
  TLDs. Until the reads at `e0862d8d`, `example.*` under any other TLD was exempt too (the
  command center's first request), and the exemption chained through further labels, so
  `…@example.com.<letters-only domain>.org` passed. Both are gone.
- Beyond the request, two forms that are not addresses or name no person: GitHub's
  `noreply@github.com` committer, and a systemd instance unit (`getty@tty1.service`,
  `user@1000.service`) whose last label is a unit type listed in systemd.unit(5) that is not
  also a TLD. `target` is both (IANA list 2026101001, line 1111), so it is no longer exempt.
- A `(` after a match exempts nothing. Until the reads at `e0862d8d`, any match followed by `(`
  was exempt, so an address with a parenthesized note passed both scans and `clean()`. The 7
  tree matches that exemption covered, decorator calls after an escaped newline (`\n@app.get(`,
  where the `n` is the escape's), are reviewed entries now.

The last label is letters, or an IDNA A-label: `xn--` followed by at most 59 more characters
(RFC 5890 2.3.2.1). Every TLD in IANA's list is one or the other.

A Claude Code `@path.md` import at the start of a line has no local part and does not match.
`md` is Moldova's TLD, so the rule does not skip it. Three test files hold an import right after
an escaped newline (`\n@…md`), which reads as an address; those matches are reviewed entries.

Each exemption is anchored at both ends. A longer local part (`xnoreply@…`), a reserved name
used as a subdomain of another domain (`…@example.com.<other>`, letters only or not), and a unit
type used as an inner label are all refused. Python's `re` lookbehinds must match a fixed width, so the
left boundary is a one-character class.

## Reviewed public matches

A first, case-sensitive candidate matched 658 times in the files the scan reads at main
`eb31d233`. Most matches were systemd instance units and decorator calls. At main `f38116f9`,
the first shipped rule matched 426 times in 86 tracked files. Each file was checked from its
matched domains, plus masked context where the domain alone did not settle it; no local part
was printed. Each holds a public upstream or vendor address, or text the rule reads as an
address. None holds an operator's address.

The first version waived those 86 files by path. Codex's review showed that a path waiver also
passes any later address added to the file (see below). `scripts/public_email_matches.json` now
lists the reviewed matches themselves, in lower case, in four groups, each with its reason;
`validate.py` loads it as `PUBLIC_EMAIL_MATCHES`. After the reads at `e0862d8d` it holds 78
values (it held 64): 19 added and 5 removed. 9 are matches that now start at a delimiter written
before a listed or exempt address (7 listed, 2 noreply trailers); the 5 removed are those matches'
earlier values. 2 are the decorator calls behind the `(` term's 7 tree matches. 7 are texts the
wider class now reads as an address (URL paths, `key=`, a brace, an escaped-newline import). The
last is the URL-userinfo fixture main's #1003 added:

| Reason | Matches |
| --- | ---: |
| Release-signing key or package-maintainer identity, as a signature check or package install printed it | 8 |
| Upstream page, package, repository, tag, advisory or paper capture naming its own public contact or author | 38 |
| Placeholder, upstream test identity, the `git` SSH user of a public Git host, SSH algorithm name, escaped exempt address, a `@path` import or a decorator call after an escaped newline, or a URL path, `key=`, quote or code span written right before an address or an `@`-name | 27 |
| URL user information or an agency contact in a test fixture, or an upstream bot's commit identity | 5 |

A text passes the email rule only when every match in it is listed, so an unreviewed address
beside a listed one is refused. The waiver covers the email rule only, in the publication scan
and in the host-receipt scan, where the raw receipt and each decoded JSON string are judged on
their own. The publication scan reads raw text only, for every rule, so an address a JSON escape
hides in another file meets the same boundary as an escaped home path there; host receipts are
the files that are parsed. Every other pattern still applies. The loader refuses an entry that is not lower case
or is listed twice. A test fails when an entry no tracked file but the registry carries, so a
dead entry cannot later waive a new address without review; the publication scan already refuses
any match the list lacks, so the list and the tree agree exactly. A match is a whole dot-atom
local part, so a listed address never waives a longer one that ends with it. At `e0862d8d` the rule
matched 499 times in 93 tracked files (435 times in 92 outside the registry). At this head, on main
`3a8a8461`, it matches 533 times in 106 files, and 455 times in 105 outside the registry.

## Consequences

The tools that import `PRIVATE_CONTENT` now apply the rule to what they write. These are the
landscape sweep (`sweep_common.py`; `convert.py` exits 3 on a residue match), the token-stack
`bundle.py` and `counter_readings.py`. An upstream capture that carries a maintainer's or
vendor's contact is refused there until it is reviewed. `scripts/native_token_ci.py` keeps its
own copies of the rules it redacts (`REDACTIONS`), and now redacts addresses as `<EMAIL>`. A
test holds each copy equal to its `validate.py` original. The PR-body gate (#991) maps its
rules by name and, once landed, fails a test when `validate.py` has a rule it does not carry.
#991 lands first, and this change's landing rebase carries the email rule into the gate. The gate
runs without a checkout, so it carries the rule strictly, without the reviewed list: a pull request
description cites no address, not even the `git` SSH user of a Git host.

The list is a JSON file rather than Python literals. The OpenHands push gate
(`blueprints/runtime-workers/openhands/resolver/patch_policy.py`, `python_references`) reads a
path literal in a gate script that loads files by path as a file the script runs. With the list
written into `validate.py`, it protected the listed files as `ci_import`, and three of its
repository tests failed. A copy of `validate.py` without the data file waives nothing, so the
rule then applies everywhere. The landscape sweep's `convert.py` loads a selected checkout's
`validate.py`, and its test copies only that script.

## Verification

- Failing first: on main `f38116f9`, with only the new `tests/test_validate.py`, the module
  ran 90 tests with 4 failures and 2 errors, all in the new email tests. With the fix it ran
  90 tests and passed.
- Twelve weakened copies of the rule each fail the module. Eleven drop case folding, an
  exemption, a boundary, the waiver or the waiver's email-only scope. The twelfth puts `md`
  back among the skipped suffixes.
- Coverage held both ways at `308033f6`: no tracked file outside the path list matched, and
  every listed path still matched. At this head every listed match occurs in the tree, and the
  publication scan passes.
- The whole suite ran as `validate.yml`'s eight shards. The modules that failed were then
  run on the branch and on unchanged main. With the list inline in `validate.py` and no
  host-receipt waiver, the branch failed four tests that main passed: the host-receipt
  validation of the tree, and three OpenHands push-gate and resolver tests. With the data file
  and the waiver, those four modules pass (542 tests). Every other failure in those modules
  fails the same way on main (missing `exchange_calendars`, a cross-device `git clone`).
- After the rebase onto main `65cf2730`, the same comparison found one more test of mine. The
  landscape sweep's selected-checkout test failed because its copy of `validate.py` had no data
  file. Since the data file is optional, it passes. One MCP-lifecycle test failed once on the
  branch, while main passed; it passes when rerun alone. One test errored on main only.

## Inverse

Revert this change's commits: the rule, `scripts/public_email_matches.json` and its loader, the
waiver in `scan_publication` and in `host_receipts.py`, the `REDACTIONS` email entry in
`native_token_ci.py`, the tests and this record. No other file depends on them.

## After Codex's review (2026-10-11)

Codex's GitHub review of `308033f6` (requested at 08:19Z) raised one P1 and three P2 findings:

- **P1: a path waiver passes a later address.** Reproduced at `308033f6`: an operator-shaped
  address appended to one listed file, with the file re-registered, gave no email finding.
  At this head the same edit gives one finding, on that file, without the address. The list
  now holds the reviewed matches, as described above. Compared locally, none of the 63
  values equals a known owner address; 6 are on consumer mail domains, all in
  upstream captures (commit metadata, advisories and package registries).
- **P2: `git@` exempted at any domain.** The rule no longer skips a `git` local part, so
  `git@<company host>` is refused. The public Git-host form the tree carries
  (`git@github.com`, 7 matches in 6 files, 3 of them `git@github.com:` remotes) is a reviewed
  entry instead.
- **P2: internationalized TLDs.** The last label may be an A-label, so `<user>@<company>.xn--p1ai`
  is refused. IANA's TLD list (version 2026101001) has 1,437 entries: each is letters only or
  `XN--` with letters, digits and hyphens, and 151 are `XN--` labels, `XN--P1AI` among them.
- **P2: the native-token sanitizer.** `native_token_ci.py`'s `Run.clean` redacted only the
  UUID and home-path rules, from hand-kept copies. Its copies now sit in `REDACTIONS`, with the
  email rule copied from `validate.py`'s source lines, and a test holds each copy equal to its
  original, pattern and flags.

The new tests fail on `308033f6` (7 failures, 6 errors). Ten weakened copies were written; one
was a no-op and was skipped, and each of the other nine fails the tests:

- any listed match waiving the file;
- a case-sensitive lookup;
- no lower-case or duplicate check;
- the `git@` exemption restored;
- no A-label, or an unbounded one;
- the host-receipt decoded scan decided by the raw text;
- the sanitizer's email copy drifting, or skipped in `clean`.

The host-receipt change has its own test: an address a JSON escape hides in a receipt is
refused even when the raw bytes hold no unreviewed match.

## After the two reads at e0862d8d (2026-10-12)

The co-op's GPT read (Astra) and the command center's Claude read reproduced these defects. The
command center ruled both families' findings into one commit:

- **B1, P1: a `(` after an address exempted it.** The rule's last lookahead refused any match
  followed by `(`, so `<address>(primary)` passed the publication scan, `--scan-file` and the
  host-receipt scan, and `Run.clean()` kept it (RFC 5322 allows a comment after a dot-atom,
  rfc5322.txt:695). The term is gone from the rule and the sanitizer's copy. Its 7 tree matches
  are reviewed entries.
- **B2, P1: a reviewed suffix waived a longer address.** The local part left out 15 `atext`
  characters (`` ! # $ & ' * / = ? ^ ` { | } ~ ``, rfc5322.txt:679-690). In `private!<listed>` the
  rule matched only the listed tail, and the waiver passed an address the list does not name. The
  local part and its left boundary now take every `atext` character, so the match is the whole
  dot-atom and the waiver compares it exactly. The registry was re-reviewed: matches whose value
  now starts at a delimiter (a URL path, `user.email=`, a quote or a code span) are listed as
  they read.
- **B3, P2: the registry proved its own coverage.** The dead-entry check scanned the registry too,
  so every entry found itself. `unoccurring_email_matches` leaves the registry out, and a test
  holds an entry found only there to be dead.
- **B4, P1 (correction #161): published digests confirmed what `clean()` removed.** `raw_sha256`
  (artifacts) and `stdout_raw_sha256` and `stderr_raw_sha256` (commands and the MCP stdio
  session) hashed the bytes before redaction. Anyone with a guess could confirm a removed address
  by hashing it. The receipt now holds digests of the published, sanitized text only
  (`stdout_sha256`, `stderr_sha256`, `retained_sha256`), and an MCP answer's digest is of its
  sanitized form (`response_sha256`). No reader in `scripts/` or `tests/` used the raw fields.
- **C1, P2: the `example` exemption chained** through letters-only labels, as above. It now names
  RFC 2606's three domains exactly.
- **C2: `target` is a TLD**, so the unit-type exemption no longer covers it.
- **C3: the counts** below are measured at this head.

Each regression fails on `e0862d8d` and passes here (exit codes 1 and 0):

- the annotated address, in the rule's cases and in `clean()`;
- each of the 15 glued characters, in the rule, the waiver and `validate()`;
- the registry-only orphan;
- the chained `example` names;
- a `.target` address;
- no published digest, across a command, an artifact and an MCP session, matching the SHA-256
  of a removed address or of the raw output that held it.

Every address in the tests is synthetic and built at test time.

The rule is hand-written, and two rounds of reads found boundary defects in it. The command
center's research-queue row for one maintained, cited detector shared with #1012 covers this
rule too; this change fixes the classes found.

## SOTA sources

All sources were read 2026-10-11 at 02:08Z unless noted. Each page's sha256 is over the bytes
fetched.

- RFC 5890 2.3.2.1, "every A-label will begin with the IDNA ACE prefix, "xn--"" and a maximum of
  59 more ASCII characters, <https://www.rfc-editor.org/rfc/rfc5890.txt> (read 14:22Z;
  `24d27002e26fedaec6c9f6479547e9d0855d952bc47d6ce1000851efd70b7430`).
- IANA, list of top-level domains, version 2026101001,
  <https://data.iana.org/TLD/tlds-alpha-by-domain.txt> (read 14:22Z;
  `34b2cce0a02e96f8a4d2e2aadb10b63aab5e7c053e272aa2c872f0b50ff2b63d`).

- RFC 5322 3.4.1, `addr-spec = local-part "@" domain` and `dot-atom-text`,
  <https://www.rfc-editor.org/rfc/rfc5322.txt> (122,322 bytes;
  `cb459acca15a2aa895863eaeff6f1d5b9c4ca15578ae3e3706f757787a385969`).
- RFC 2606, the reserved `.test`, `.example`, `.invalid` and `.localhost` TLDs and
  `example.com`, `example.net`, `example.org`, <https://www.rfc-editor.org/rfc/rfc2606.txt>
  (8,008 bytes; `b6869c8984701701bc2e6973b6ffc750d497f845cc1a65a106e9301590a13ab0`).
- RFC 4343, DNS names are "case insensitive", <https://www.rfc-editor.org/rfc/rfc4343.txt>
  (22,899 bytes; `bebb8037e4bc6da9ad6691cf2aa2eb955852684c839d8f7dae311683292c1100`).
- systemd.unit(5) (systemd 262), unit types and instance names,
  <https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html> (182,485 bytes;
  `2f78df141d916d973fa189215799e8d26b67a3cf27fee2660a543e5abf3c5009`).
- GitHub Docs, email addresses reference, the `ID+USERNAME@users.noreply.github.com` form,
  <https://docs.github.com/en/account-and-profile/reference/email-addresses-reference>
  (128,589 bytes; `4daa0db9f6e355c6de0d51e556d93968dbd5bd177b159a17ad4cd37ab6f13c25`).
- GitHub Docs, testing your SSH connection, `ssh -T git@github.com`,
  <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/testing-your-ssh-connection>
  (139,432 bytes; `e921eca62b7fcfb982287f952ac3bea0b7770b87d93f836e1eed602b88f44cad`).
- Claude Code docs, memory, the `@path/to/import` syntax, <https://code.claude.com/docs/en/memory>
  (797,902 bytes; `32b6627d64c2f33966e5fd1d27998508a0b8204fe24655680477f6a062da2e67`).
- Python 3.13 `re`, fixed-length lookbehind and `IGNORECASE`, the installed 3.13.16's
  documentation, <https://docs.python.org/3.13/library/re.html> (242,273 bytes;
  `19195ec76056c9b8088394ba81014ff47e1d4040a8eae092e450412f75f5c378`).
