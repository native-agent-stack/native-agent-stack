# Bind the unchanged NautilusTrader rc5 run to its peeled source commit

Status: source identity only. This supplies the run pin used by FINAL condition
2; it registers no receipt, verdict, invocation, operational acceptance or FINAL
claim. Base: `8dfe8b588de22451364857b4be4683fb35f57a7d`.

## Scope and source

The `nautilus-trader` run comes from the registry package at
`blueprints/us-equities/runtime-2604/trading-2604-runtime/uv.lock#/package/99`.
Its version is `2.0.0rc5`; the unchanged lock records artifact hashes but no
upstream Git commit. At the base, `scripts/final_stack.py:375-403` reads that
highest-precedence source as version-only, so `complete_final_pin` cannot bind
a commit-cited receipt to it.

The narrowed action follows `ROW-cc-20261016T0108Z-new-wsl-gap-routing.md` and
`T1-PROTOCOL-WALK-20261016.md`, with the co-op's subsequent option (b) scope
ruling. These authority records are cited by name. The broad local preparation
is retained separately; its systemd repository change and trust bridge are
excluded, as are version upgrades and other package identities.

Primary upstream: `nautechsystems/nautilus_trader`, tag `v2.0.0rc5`. A fresh
native Git query on 2026-10-16 returned exactly its annotated tag object
`34de0d6f886a9fe8359f9d6590f43f53c86b1d32` and peeled commit
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`:

```text
git ls-remote https://github.com/nautechsystems/nautilus_trader.git refs/tags/v2.0.0rc5 'refs/tags/v2.0.0rc5^{}'
```

The command, exit code and exact output are retained in
`evidence/artifacts/nautilus-run-pin-20261016/tag-resolution.json`, with the
separate tag object and commit also listed in `tags.md`. Git's semantics are
documented at `git/git v2.53.0`, `Documentation/git-ls-remote.adoc`, OUTPUT.
This is a source observation, not a runtime or broker probe.

## Existing parser and exact lock binding

`catalogs/landscape/lockfile-source-identities.json` supplements one exact lock
entry. It binds the lock pointer, normalized package/repository identity,
unchanged version and complete artifact SHA256 set to the peeled commit.
`uv.lock` stays byte-identical. The minimal reader in `final_stack.py` supplies
that commit through the existing `record_pin(version, commit)` API; the run's
display becomes `2.0.0rc5; source 1b0a49d2792a9432a3aca3fcb617ce7a630d905e`.
No installer version, source precedence or FINAL admission rule changes.

The reused parser and receipt-binding mechanisms are
`scripts/final_stack.py:127-129,324-344` and `complete_final_pin` at the base;
the original #1058 contract is pinned at
`252babe4040e39173cc178317c67699371806df6`, lines 127-129 and 706-721.
Adding an exact source supplement fills metadata absent from the registry lock
entry; changing the registry version string or guessing a current HEAD would
change identity. A changed version, package, repository, artifact set or invalid
commit leaves the matched entry unparsed. Duplicate pointers are refused.

## Regression and boundaries

`tests/test_nautilus_run_pin.py` ran before the reader/data change against
unchanged main: four tests, eight assertion/subtest failures, no errors. The
commit-cited receipt failed to bind; the five mismatch controls and duplicate
pointer control also failed behaviorally. The final checks and their counts
are retained separately in the local-integration `controls.json` artifact.
The fixture proves that the same receipt is refused before a supplement and
binds after the exact supplement. The repository check verifies the real rc5
run and rejects a different source commit. Tests use the existing native
`unittest` harness (`python/cpython v3.13.16`, `Lib/unittest/case.py` and
`Lib/unittest/loader.py`); no imported concrete TestCase is rediscovered.

Systemd remains an explicit source-identity gap: its source-package repository
supersession and the catalog trust bridge need the separate PIN-RULES then
PIN-DATA work, with supported verdict-wave custody. This change preserves the
frozen scheduling-supervision row and its wave byte-for-byte. Other version-only
winner pins remain for that separately reviewed batch. No receipt transfers,
installs, source-version upgrades, account operations or broker calls occur.

Ownership update, 2026-10-16: the layer-verdict lane owns the tracked PIN-RULES
then PIN-DATA work, including the systemd source-identity gap, under
`ROW-cc-20261016T0108Z-new-wsl-gap-routing.md` and the subsequent 02:59Z split.
PIN-RULES lands before the separate FINAL-opening work; that opening's owner
keeps qualified admission and refusal paths. This source-pin decision does not
transfer either implementation or broker-operation authority between lanes.

The base-trusted verdict gate must pass without a bypass before this narrowed
PR opens. Publication validation establishes repository integrity; it does not
establish native acceptance at this source or settle any comparison dimension.
Reopen this binding only on retained evidence of a changed tag or lock identity.

## Review micro-fold

The full reads `GPT-VERDICT-1a7917ff9.md` and `MICRO-full-1a7917ff.md` identify
one missed publication consumer and inexpensive provenance corrections. At
reviewed pin `1a7917ff95d9f1d2908c0bd0c3cbf213320fc6d1`,
`tools/local-pages/source_policy.py:284-309` already supports exact, reasoned
landscape supplement exclusions before byte access. The new lock identity file
contains metadata rather than a projected layer collection, so the policy now
excludes that exact path and records its published classification provenance.
No new Architecture read grant or consumer rule is added.

The original Architecture exclusion module reproduced two failures in eight
tests. Adding the new metadata/provenance and run-source assertions before
correction produced six failures in 13 tests. The existing real catalog join
and fail-closed controls remain active. Retained controls distinguish this
micro-fold from the original four-test binding correction.

An accepted run's source now points to its supplement binding; that binding's
source points to the unchanged lock entry. The run definitions name both inputs.
The unread `tag_ref` and `resolution_ref` fields are removed; the independently
recorded tag command/output remains source evidence. An unused repository
fallback is removed because the stack already supplies Nautilus's repository.
The base parser citation is corrected to lines 324-344.

A well-formed but incorrect commit in a supplement is not authenticated against
the upstream tag by this reader. The review's wrong-commit guard is deferred to
the separate PIN-RULES work, alongside the remaining source-identity batch; this
micro-fold does not claim that guard. No FINAL admission rule changes.
