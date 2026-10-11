# Refuse email addresses in the publication scan — 2026-10-11

Claude Code adds the signed-in account's email address to every session's context.
Nothing in `scripts/validate.py` refused an address, so a session could carry it into a
public evidence file and CI would pass. `PRIVATE_CONTENT` now has an `email address`
rule. The repository scan (`Validator.scan_publication`), `--scan-file`, the host-receipt scan
in `scripts/host_receipts.py` and every tool that imports `PRIVATE_CONTENT` apply it. Findings name the rule and the path, never the
address.

## The rule

It matches an RFC 5322 3.4.1 `addr-spec` written in dot-atom characters
(`local-part "@" domain`), ignoring case, because DNS names are case-insensitive
(RFC 4343). It does not match these forms:

- GitHub's `users.noreply.github.com` commit addresses, and the `noreply@` commit
  identities of Anthropic (the Claude Code co-author trailer) and GitHub.
- The RFC 2606 reserved names: `example.com`, `example.net` and `example.org`, and the
  `.test`, `.example`, `.invalid` and `.localhost` TLDs. The command center's request also
  exempts `example.*` under any other TLD (`example.co.uk`); RFC 2606 does not reserve those.
- Beyond the request, four forms that are not addresses or name no person: GitHub's
  `noreply@github.com` committer, the `git@` SSH user of Git hosts
  (GitHub's `ssh -T git@github.com`), a systemd instance unit (`getty@tty1.service`,
  `user@1000.service`), whose last label is a unit type listed in systemd.unit(5) and is not
  a TLD, and a decorator call such as `@app.get(`.

A Claude Code `@path.md` import at the start of a line has no local part and does not match.
`md` is Moldova's TLD, so the rule does not skip it. Three test files hold an import right after
an escaped newline (`\n@…md`), which reads as an address, and they are exempted by path.

Each exemption is anchored at both ends. A longer local part (`xnoreply@…`), a reserved name
used as a subdomain of another domain (`…@example.com.<other>`), and a unit type used as an
inner label are all still refused. Python's `re` lookbehinds must match a fixed width, so the
left boundary is a one-character class.

## Reviewed public paths

A first, case-sensitive candidate matched 658 times in the files the scan reads at main
`eb31d233`. Most matches were systemd instance units and decorator calls. At main `f38116f9`,
the shipped rule matches 426 times in 86 tracked files. Each file was checked from its matched
domains, plus masked context where the domain alone did not settle it; no local part was printed.
Each holds a public upstream or vendor address, or text the rule reads as an address. None holds
an operator's address. `scripts/public_email_paths.json` lists the 86 files in four groups, each
with its reason, and `validate.py` loads it as `PUBLIC_EMAIL_PATHS`:

| Reason | Files |
| --- | ---: |
| Release-signing key or package-maintainer identity, as a signature check or package install printed it | 22 |
| Upstream page, package, repository, tag, advisory or paper capture naming its own public contact or author | 42 |
| Placeholder, upstream test identity, SSH algorithm name, escaped exempt address, or a `@path` import after an escaped newline | 13 |
| URL user information or an agency contact in a test fixture, or an upstream bot's commit identity | 9 |

The waiver covers the email rule only, in the publication scan and in the host-receipt scan (two
receipts are listed). Every other pattern still applies to these files. A
test fails if an entry's file is untracked or no longer matches, so a dead entry cannot later
waive a new address without review. A new file holding an address needs its own entry.

## Consequences

The tools that import `PRIVATE_CONTENT` now apply the rule to what they write. These are the
landscape sweep (`sweep_common.py`; `convert.py` exits 3 on a residue match), the token-stack
`bundle.py` and `counter_readings.py`. An upstream capture that carries a maintainer's or
vendor's contact is refused there until it is reviewed. The PR-body gate (#991) maps nine rules
by name, so it neither breaks nor gains the email rule. Carrying the rule to PR bodies is a
follow-up after #991 lands.

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
- Coverage holds both ways at the head: no tracked file outside `PUBLIC_EMAIL_PATHS` matches,
  and every entry still matches.
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

Revert this change's commit: the rule, `scripts/public_email_paths.json` and its loader, the
waiver in `scan_publication` and in `host_receipts.py`, the tests and this record. No other file depends on them.

## SOTA sources

All sources were read 2026-10-11 at 02:08Z. Each page's sha256 is over the bytes fetched.

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
