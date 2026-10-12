# Record: installed lane messaging has an unresolved star-audit disposition

**Status:** open audit gap; source review recorded 2026-10-12. This record
does not adjudicate a candidate or change the installed transport.

At repository base `d8f7e2051b61bde6361a85b64f41413798015353`, the installed
lane-messaging tool is **aannoo/hcom 0.7.28**. The native command
`hcom --version --name koda` returned `hcom 0.7.28`. Its reviewed upstream
pin is **v0.7.28**, commit
`b2a7c192003e7fd67ed93265289e4ac36276f965`:
[Cargo.toml:1–9](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/Cargo.toml#L1)
declares that version and repository;
[README.md:13–19](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/README.md#L13)
describes messaging, watching and spawning across agent terminals. Version
output establishes the installed version, not binary/source equivalence or
a fresh runtime-acceptance measurement.

The gap is between these distinct records:

| Record at the base above | What is recorded for hcom |
| --- | --- |
| [Public-star manifest](../../catalogs/convergence-practice/public-starred.json), `#/repositories/15` | `aannoo/hcom`, first observed 2026-10-08; in scope for scheduling-supervision and native-clients; `verdict_refs` is empty |
| [Star convergence manifest](../../catalogs/convergence-practice/starred-convergence-20261010.json), `#/repositories/15` | Metadata review and seed routing; `AWAITING-RECORDED-TIER-VERDICT` for tier-1 and tier-2; no verdict reference |
| [Star seed manifest](../../catalogs/convergence-practice/starred-seeds-20261010.json), `#/seeds/11` and `#/seeds/12` | Scheduling-supervision and native-clients seeds, `runtime_qualified: false` in those seed records |
| [Star decision audit](../../catalogs/us-equities/star-audit.json), `#/entries` | No entry for `aannoo/hcom`; this audit's declared scope is the earlier 357-star snapshot refreshed on 2026-09-24 |

The older audit's scope predates hcom's first observation in the public-star
manifest. Its absence is therefore a **newer-star decision-coverage gap**,
not evidence that the older audit failed to cover its declared snapshot.
The newer metadata seeds also do not supply an adoption or comparative
verdict. Existing adoption history remains separately recorded in
[the agent-messaging row](2026-10-01-new-wsl-definitive-defaults.md): the
dated hcom 0.7.27 cross-client transport decision is not a current pinned
star-audit disposition for 0.7.28.

The bounded next action is to record the missing star disposition through
the existing scheduling-supervision/native-clients convergence path, naming
the installed messaging role, pinned source and applicable adoption evidence,
and link the resulting verdict into the star manifests. Installation and
source metadata alone cannot close `AWAITING-RECORDED-TIER-VERDICT`. The
agent-sdks survivor adjudications assigned elsewhere are separate work.

## Evidence and limits

The CC's 2026-10-12 runtime delta check and Addendum 02 assign this audit gap
to grand-catalog. The primary evidence here is the base's exact JSON records,
the upstream source at the commit above, and the returned native version
line. No dependency install, messaging probe, comparative trial, runtime
configuration change or star-audit verdict mutation was performed.

Completeness check: the installed version, upstream role, newer star intake,
seed routing, missing audit entry and existing dated adoption history are
distinguished. The remaining tier verdict and its evidence links are the
explicit gap; this record does not claim that hcom is absent from all
repository research or that an installed tool is the best available choice.
