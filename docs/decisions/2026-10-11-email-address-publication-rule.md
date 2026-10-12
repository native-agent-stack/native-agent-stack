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
never starts inside a longer local part. It finds matches in any case; the reviewed list compares
the domain without case (DNS names are case-insensitive, RFC 4343) and the local part as written
(RFC 5321 2.4). A local part needs a letter or a digit, and the command center kept that guard:
local parts made only of RFC 5322 atext symbols are not detected, though they are valid (CPython
3.13.16's email parser accepts one); no observed instance is identity-bearing. At main
`900835c6` the rule without its guard, over every tracked blob read as UTF-8, finds 125 such local
parts in 76 files, each a backtick (111), a quote (10), a slash (2) or two of them (2) before an
`@`-name such as `` `@AGENTS.md` `` or a quoted `@import`; none is an address. (The command
center's first figure, 139, came from an ad-hoc search and does not reproduce; its correction
#182.) The guard is this change's own,
added when the wider class turned 16 code spans of Claude Code imports into matches. Until the
GPT read at `51f45b5d` this paragraph said such a local part "names no mailbox", which is false.
It does not match these forms:

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
lists the reviewed matches themselves, each as its reviewed spelling (the local part as written,
the domain in lower case), in four groups, each with its reason;
`validate.py` loads it as `PUBLIC_EMAIL_MATCHES`. After the reads at `e0862d8d` it holds 78
values (it held 64): 19 added and 5 removed. 9 are matches that now start at a delimiter written
before a listed or exempt address (7 listed, 2 noreply trailers); the 5 removed are those matches'
earlier values. 2 are the decorator calls behind the `(` term's 7 tree matches. 7 are texts the
wider class now reads as an address (URL paths, `key=`, a brace, an escaped-newline import). The
last is the URL-userinfo fixture main's #1003 added:

| Reason | Matches |
| --- | ---: |
| Release-signing key or package-maintainer identity, as a signature check or package install printed it | 8 |
| Upstream page, package, repository, tag, advisory or paper capture naming its own public contact or author | 39 |
| Placeholder, upstream test identity, the `git` SSH user of a public Git host, SSH algorithm name, escaped exempt address, a `@path` import or a decorator call after an escaped newline, or a URL path, `key=`, quote or code span written right before an address or an `@`-name | 27 |
| URL user information or an agency contact in a test fixture, or an upstream bot's commit identity | 5 |

A text passes the email rule only when every match in it is listed, so an unreviewed address
beside a listed one is refused. The waiver covers the email rule only, in the publication scan
and in the host-receipt scan, where the raw receipt and each decoded JSON string are judged on
their own. The publication scan reads raw text only, for every rule, so an address a JSON escape
hides in another file meets the same boundary as an escaped home path there; host receipts are
the files that are parsed. Every other pattern still applies. An entry is the reviewed spelling: its
local part as written and its domain in lower case; the loader refuses any other form, or an entry
listed twice. A spelling whose local part differs only in case is another match, with an entry of
its own when a public source carries it (one public agreement carries two). A test fails when an entry no tracked file but the registry carries, so a
dead entry cannot later waive a new address without review; the publication scan already refuses
any match the list lacks, so the list and the tree agree exactly. A match is a whole dot-atom
local part, so a listed address never waives a longer one that ends with it. At `e0862d8d` the rule
matched 499 times in 93 tracked files (435 times in 92 outside the registry). At `51f45b5d` it
matched 532 times in 106 files and 454 times in 105 outside the registry; an earlier version of
this sentence said 533 and 455, measured before that head's last edit. At the head that answers
the GPT read of `51f45b5d`, on main `3a8a8461`, it matches 533 times in 106 files and 454 times
in 105 outside the registry (`git ls-files`, each tracked file read as UTF-8, the rule's
`finditer`).

## Consequences

The tools that import `PRIVATE_CONTENT` now apply the rule to what they write. These are the
landscape sweep (`sweep_common.py`; `convert.py` exits 3 on a residue match), the token-stack
`bundle.py` and `counter_readings.py`. An upstream capture that carries a maintainer's or
vendor's contact is refused there until it is redacted: those strict consumers, like
`--scan-file`, do not read the reviewed list, which waives only the publication scan and the
host-receipt scan. `scripts/native_token_ci.py` keeps its
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

## After the GPT delta read at 51f45b5d (2026-10-12)

The co-op's GPT read of the fix (Astra, CHANGES_REQUESTED) found two P1s and two P2s. The command
center ruled them into one commit:

- **P1-1, split.** The letter-or-digit guard stays, as the command center ruled at 03:26Z: no
  observed symbol-only local part is identity-bearing, and an account name is always alphanumeric.
  The record's and the comment's "names no mailbox" was false: CPython 3.13.16's parser accepts
  such a local part (`Lib/email/_header_value_parser.py:1219`, `:1360`, `:1486`, `:1682` at
  `cbc944f4`). It is restated as the residual above, in `validate.py`, the sanitizer's copy and the
  pull request description.
- **P1-2: a JSON escape hid an address from `Run.clean()`.** An address whose `@` was written
  `\u0040` in a tool's JSON output passed `clean()`, which reads text, and a reader's `json.loads`
  gave it back from the published receipt or artifact. `Run.publish()` now cleans each decoded key
  and string value of JSON or JSON Lines text, nested JSON in a string value too, four levels
  deep, and writes the document again only when a value changed; it serves every published
  command argument, output stream, artifact, MCP request and answer digest. Each digest is of the
  published bytes. `host_receipts.py` judges a receipt's decoded values the same way
  (`:1434`, `:1445`). The mechanism: any character may be written as a `\u` escape (RFC 8259 7,
  rfc8259.txt:433, <https://www.rfc-editor.org/rfc/rfc8259.txt>, read 2026-10-12T06:15:38Z,
  `61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7`), and a decoder gives the
  character back (CPython `cbc944f4` `Lib/json/decoder.py:60`, `_decode_uXXXX`, called at `:118`).
- **P2-3: the waiver lowered the local part.** A reviewed address with one letter of its local
  part in upper case is a different mailbox (RFC 5321 2.4, rfc5321.txt:869: "the local-part of a
  mailbox MUST BE treated as case sensitive"; CPython's `headerregistry.py:50`, `:53`, `:62`,
  `:100` keep and compare it as written), yet it passed as the listed one. `email_key` keeps the
  local part and lowers the domain, in the loader, the dead-entry check and the waiver. The
  registry lists 79 spellings: 7 entries were respelled to the spelling the tree carries, and 1
  was added beside a kept spelling, where one public agreement carries a contact in two spellings.
- **P2-4: the counts** were corrected above.
- **P3s folded:** the strict consumers' wording above, and the receipt's limitation text, which now
  says which digests are of published text. The rest are follow-ups in the pull request.

Each regression fails on `51f45b5d` and passes here:

- a JSON-escaped address, nested JSON too, in a command's output, an artifact and an MCP answer:
  no published value decodes to it, and no digest matches the escaped text;
- a local part's case variant, in the waiver, `validate()` and the dead-entry check, and a loader
  that keeps an entry's spelling.

## After the command center's micro at 4c916e14 (2026-10-12, the terminal commit)

The command center's Claude micro of the second fix closed 21 of 36 encoded leaks it probed at the base; of the 15 that
remain, two are in `Run.publish()`'s own scope, and the command center ruled them in:

- **B1: a Unicode line break split a JSON line.** `publish()` split JSON Lines text with `str.splitlines()`, which
  also breaks at U+2028, U+2029 and U+0085 (CPython `cbc944f4` `Objects/unicodetype_db.h:6418-6430`). RFC 8259 7
  allows those characters raw inside a string (rfc8259.txt:428-431), so such a line was never decoded and its escaped
  address was published. A line now ends only at a line feed, and a trailing carriage return is kept.
- **B2: nesting deeper than four levels passed through.** JSON text nested in string values five to seven levels deep,
  in values, keys, JSON Lines and MCP answers, was published with its escaped address. `publish()` now refuses JSON
  text beyond `PUBLISH_DEPTH` (four) with the fixed `PUBLISH_REFUSED` message, and nothing is published; a command, an
  artifact or an MCP session that meets one fails. Real receipts nest at most two levels.
- **Text:** the registry's spelling (above, 8 entries keep an upper-case local part), the table's second group (39),
  the respelling count (7 respelled and 1 added), the 139 figure (above, now 125 in 76 files, method named), the
  receipt's limitation text, and the escape mechanism's sources.

Each regression fails on `4c916e14` and passes here: a JSON line holding each of the three characters, alone and
among other lines; and five to seven levels in values and keys, alone and among other lines, through `publish()`,
an artifact and a command.

**Addendum (the command center's addendum 01 at 4c916e14, from the GPT read at `4c916e14`):** an object with a
duplicate name hid an earlier member from the sanitizer, since `json.loads` keeps only the last one and an unchanged
document was published as written. RFC 8259 4 says the names within an object SHOULD be unique (rfc8259.txt:322,
read 2026-10-12T06:15:38Z). `publish()` parses through an `object_pairs_hook` that refuses such an object with
`PUBLISH_REFUSED`, so nothing is published; unique-name JSON keeps every byte. Each regression (`publish()`, an
artifact, a command and an MCP answer) fails on `adc2adb2` and passes here.

**Addendum 02 (the command center's micro at `adc2adb2`, N1):** splitting JSON Lines only at a line feed left JSON
beside a lone CR, or after RS, FF, VT, FS, GS, U+0085, U+2028 or U+2029, undecoded, while Python's universal newlines
(`Lib/_pyio.py:153-154` at `cbc944f4`), `str.splitlines()` and `jq` read the escaped address back. Choosing one
splitting always leaves a reader that splits differently (rule 4), so `publish()` now verifies its own output:
`recoverable()` reads the exact text to be published under a line feed, `str.splitlines()` and universal newlines,
decodes every JSON text in each piece as a stream reader does (JSON whitespace and RFC 7464's RS between texts),
reads every member of every object it decodes (one with a duplicate name is refused since addendum 03), and nested
JSON to the same depth, and applies the
sanitizer's rules to each decoded value. Numbers are kept as their text, so the micro's N2 (an integer past CPython's
4,300-digit limit beside the address, which `json.loads` refuses with a plain `ValueError` while jq and Node read
on) is read too. If one of these readers recovers private content, the output is refused with `PUBLISH_REFUSED`
(this said any reader until addendum 04, which lists the readers and refuses what they cannot finish); clean output
keeps every byte. Over the committed native-token receipts, the published streams pass unchanged (the count first given
here, 765, came from a selector that was not recorded and does not reproduce; addendum 04 states its census); a 1.1 MB
JSON
document is verified in 1.6 s. Each regression (the micro's lone-CR, separator, json-seq and long-number shapes,
through `publish()`, an artifact, a command and an MCP answer) fails on `adc2adb2` and passes here; its byte-for-byte
controls pass on both. Forms readable only by a person, such as `\x40`, a fullwidth at sign or `%40`, are follow-ups
for the shared email detector. (Until addendum 03 this sentence also put two values on one line, a BOM, a trailing
comma, a log prefix and duplicate names outside `publish()`'s scope. For an address, the escape projection below reads
all four; the JSON reading takes two values on a line and a trailing comma, and a BOM since addendum 04; a duplicate
name is refused in every JSON text the views read, which a log prefix on the same line is not.)

**Addendum 03 (the command center's, from a shadow review the co-op reproduced at `66036a74`):** the verifier still
depended on framing. A pretty-printed object after a lone CR (a progress line, then JSON), or behind RS framing (RFC 7464
2, rfc7464.txt:119-185, <https://www.rfc-editor.org/rfc/rfc7464.txt>, read 2026-10-12T08:30:42Z,
`a8eadbcdce5fc508b9e014299621562da041232af13848632092164d50b3f482`), was cut by every split view, so its escaped address
went out while readline-then-`json.load` and `jq --seq` read it back. The fourth recurrence of the class, so the
verifier now also reads the output with framing ignored: every RFC 8259 7 string escape (rfc8259.txt:455-475: a
surrogate pair at :455-459, a code unit and the eight short forms at :461-475; a lone surrogate's escape is left as it
is) is decoded across
the whole text, up to `PUBLISH_DEPTH` times over for nested escaping (and refused past that since addendum 04 below),
and the sanitizer's rules run on each projection.
A duplicate name is refused wherever the verifier decodes JSON too, in every framing it reads, numbers kept as text, so
an RS-framed duplicate object or duplicates after a long number are refused as well. Over the committed native-token
receipts, the published streams pass unchanged (the unreproduced 765 again; see addendum 04's census). The regressions
fail on `66036a74` (13 failures: the two framings and a doubly escaped address through `publish()`; the two framings
through an artifact, a command and an MCP answer; three duplicate shapes, one after a lone CR; and the receipt's own
check) and pass here, and escaped text with nothing private keeps every byte. A test of the earlier fix had put the escaped address in
a command's own argv, which is published too; the child now reads it from a file.

The GPT read at `66036a74` (ACK, three P3s) asked to keep the refusal and recovery ordering and to close the MCP
session's pipe handles behind the tests' `ResourceWarning`s: the session now closes the parent's ends of the child's
stdout and stderr once its readers have finished (12 warnings in `tests.test_native_token_ci` before, printed on 24
lines, 0 after): `Popen` closes them only in `__exit__` (python/cpython@`cbc944f4bc59639a444dd971c737788ba2283a91`
`Lib/subprocess.py:1106-1113`), and the session does not use it as a context manager; since addendum 04 a test asserts
both ends are closed. Its other
P3s (retained source captures, and the locator, strict-consumer and hostname follow-ups) are in the pull request's
Follow-ups.

**Addendum 04 (the command center's, from the GPT read and its Claude micro at `6aaa204a`):** more P1s in the class,
each the verifier certifying what it had not finished. An address escaped five or more times, or JSON nested four or
more times in string values, behind a lone CR or RS framing (also an ordinary document whose lower levels are
CR-framed, and an MCP answer one level up) went out, because the escape projection stopped after `PUBLISH_DEPTH` passes
and the record views cut the multiline object, so the depth rule was never reached; and a host receipt's command
`output_excerpt` holding JSON kept its escaped address, because the receipt scan decoded once. The class's fifth
recurrence, so the verifier is one function now, `publication_views()` in `scripts/native_token_ci.py`, shared by
`Run.publish` and the host-receipt scan (which imports it), and it fails closed:

- the views are the text; the text with RFC 8259 7 escapes decoded, pass after pass; and every key and string value of
  every JSON text under each framing the views read: the whole text, a line feed, `str.splitlines()`, universal
  newlines, and records at RS, each whole across its line breaks (RFC 7464 2: a parser SHOULD continue past a
  malformed record, rfc7464.txt:153-155, as jq does at jqlang/jq@`4467af7068b1bcd7f882defff6e7ea674c5357f4`
  `src/jv_parse.c:785-807`). Within each, JSON texts are read in turn, a byte order mark between them is skipped
  (RFC 8259 8.1, rfc8259.txt:494-498, as jq 1.8.1 does), and where none starts, reading resumes at the next line, a
  lone CR included, as readline-then-`json.load` does; a line is decoded alone first, and the text after it only when
  the line ends inside a JSON text, so the reading stays linear. Nested JSON in a string value is read too;
- a check it cannot finish raises `Unverifiable`, which both surfaces refuse: escaping still undone after
  `PUBLISH_DEPTH` passes, JSON nested deeper than `PUBLISH_DEPTH` levels, an object with a duplicate name, or JSON too
  deep for Python's decoder (`RecursionError`). Text past the bound is refused whatever it holds;
- the host-receipt scan judges every view with the reviewed-email waiver applied to each, so JSON held in a string is
  read, and a receipt the views cannot finish is refused.

The function sits in `native_token_ci.py` rather than a module of its own. The push gate's read analysis
(`blueprints/runtime-workers/openhands/resolver/gate_reads.py`, `_executes`) counts a call into a module imported from
outside the standard library as running its argument, so a separate module added an advisory unclassified location at
`Run.publish`; a function in the analyzed file is read instead, and the advisory baseline is unchanged (line moves
only). Because `host_receipts.py` imports it, `native_token_ci.py` joins the verdict-review gate's `TRUST_PATHS`, which
lists every module the validators import (`tests/test_verdict_review_gate.py` derives that set).

`Run.publish` also refuses a rewrite that would merge two names (an escaped address key beside a literal `<EMAIL>` key)
or change a number as written (`1e400` to `Infinity`, a long decimal losing digits, `-0` to `0`, or a non-JSON
constant); with nothing to clean, such a document keeps every byte. It rewrites only JSON it reads whole or by line
feed; JSON in another framing that would need cleaning is refused by the verifier instead (none of the committed
streams below is). JSON too deep for Python's decoder is refused with `PUBLISH_REFUSED` rather than raised. And the
`noreply@` trailer exemption now keeps the local part's case (`(?-i:noreply)`), as RFC 5321 2.4 requires, so
`NoReply@` is detected; only the domain ignores case.

The regressions fail on `6aaa204a` (46 failures and 4 errors across the native-token, host-receipt and validate tests)
and pass here. The command tests now read their payloads from files, so the argv publishes and the refusal is the
output's (the GPT read's P3-6). 14 of 14 weakened copies fail them. A census on both heads
gives the same result. Selector A takes every string under a `stdout` or `stderr` key, at any depth, in the tracked
JSON files whose top-level `kind` is `native_cli_e2e` (26 files, 1,518 strings, 629 non-empty): all are published
unchanged. Selector B takes the same strings in every tracked JSON file (198 files, 4,867 strings): none is refused,
and `clean()` rewrites 17. On inputs of about 1.1 MB, one `publish()` takes at most 1.9 s here (1.65 s at `6aaa204a`).
A truncated pretty document 300 levels deep takes 1.2 s (0.17 s), because each unclosed level is read across lines once.

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
- RFC 8259 7, "Any character may be escaped" (rfc8259.txt:433) and the characters a string may hold raw
  (:428-431), <https://www.rfc-editor.org/rfc/rfc8259.txt> (read 2026-10-12T06:15:38Z;
  `61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7`).
- CPython v3.13.16 (`cbc944f4`): `Lib/json/decoder.py:60` and `:118` (a `\u` escape decoded to its character), and
  `Objects/unicodetype_db.h:6418-6430` (the line breaks `str.splitlines()` honors).
- RFC 5321 2.4, "the local-part of a mailbox MUST BE treated as case sensitive"
  (rfc5321.txt:869), <https://www.rfc-editor.org/rfc/rfc5321.txt> (read 2026-10-12T05:06:37Z;
  `7d560eddff1b213c17d4e1e5f95005728b2f05bc2b3947f0fcc91717c6707634`).
- CPython v3.13.16 (`cbc944f4bc59639a444dd971c737788ba2283a91`, the local upstream mirror):
  `Lib/email/_header_value_parser.py:1219` (`get_atext`), `:1360` (`get_dot_atom_text`), `:1486`
  (`get_local_part`), `:1682` (`get_addr_spec`); `Lib/email/headerregistry.py:50`, `:53`, `:62`,
  `:100` (the local part kept and compared as written).
- Python 3.13 `re`, fixed-length lookbehind and `IGNORECASE`, the installed 3.13.16's
  documentation, <https://docs.python.org/3.13/library/re.html> (242,273 bytes;
  `19195ec76056c9b8088394ba81014ff47e1d4040a8eae092e450412f75f5c378`).
