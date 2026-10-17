# EdgarTools 5.62.0 fixture-parser layer screen — 2026-10-15

**SCREEN result:** EdgarTools 5.62.0 passed the supplied bounded native
fixture-parsing screen at
`dgunning/edgartools@5068cc548552fab1fbd061f1b8bccdc4e1677c6f`.
The [sanitized execution supplement](edgartools-562-screen-20261015.json)
is registered through `scripts/catalog_decisions.py` at `#/candidates`.
Its SHA256 is
`7e05517981a151d0a1736b5cd03f823365d93600002aca8e69a4db1c74f7e84b`.

This adds evidence for source-identifiable, reproducible SEC filing parsing
in the US-equities research lane. A screen is not a default selection.
Multi-angle convergence remains the prerequisite for a new default. Existing
runtime pins, layer verdicts, historical acceptance and open data/strategy
gates retain their scopes.

## Recorded execution

The supplement records an isolated CPython 3.12.3 environment, the public
`pip install edgartools==5.62.0` route and the upstream test dependencies.
It reports no new model dependency invoked; the eight selected installed-source
hashes match the pinned upstream tag.

| Observation | Evidence class and scope |
| --- | --- |
| Vendor offline SGML, Form144, 424B and XBRL selection | Retained native execution: 114 tests executed, zero failures/errors/skips; network-marked tests deselected. The broad entity module is not credited as exercised by this run. |
| Targeted EntityFactsParser and XBRL instance selection | Retained native execution: 11 tests executed, zero failures/errors/skips. The XBRL check overlaps the first run; these are per-run executions, not 125 distinct tests. |
| SGML/public-fixture parse and JSON persistence | Retained local integration using the native parser: one 424B5 row, SGML acceptance time converted to UTC, create-only JSON persisted mode 0444, byte-identical reread and JSON equality. |
| Public Form144 XML fixture | Retained native parser execution: two security rows; the XML fixture contains no header acceptance clock. |
| Three launcher attempts before collection | Retained failures: exit 1 and zero tests executed because an isolated interpreter alias symlink was omitted; binding the complete runtime directory corrected the launcher. |

The upstream offline pytest plugin blocked outbound sockets/DNS and cleared
caches. The recorded process additionally ran with network isolation and a
hidden host home. The fixture E2E records zero network calls and zero model
calls. Its execution timestamp is a receipt clock, not original historical
availability.

This registration reuses the supplied execution evidence. The catalog checks
below do not rerun the vendor tests or reproduce that execution environment.
The persistence round trip is local integration around the native parser,
separate from the unchanged vendor pytest selection.

## Public output custody

The screen's `public_fixture_e2e.output_file` now points to the published
[fixture output](edgartools-562-fixture-output-20261015.json). The original
E2E wrote `row.json` inside a temporary directory that was deleted on exit.
Its deterministic public row was reconstructed as
`(json.dumps(row, sort_keys=True) + "\n").encode()`: 255 bytes, SHA256
`fed33d8489d3840ea505d2dfe998fb1c730342184b36b49eba341dabcb334ff7`,
matching the output digest recorded by that run. All six fields describe the
public SEC fixture; the fixture digest binds the upstream file at the source
pin above. Reconstruction is an artifact-custody repair, not a new parser or
E2E execution. The supplement's only content change is its output-file locator.

Before staging or committing the output, this native privacy scan completed
at 2026-10-15T19:17:48Z (UTC tool clock):

```text
$ python3 scripts/validate.py --scan-file catalogs/us-equities/edgartools-562-fixture-output-20261015.json
{"matching_locations": 0, "scanned_files": 1, "source": "host", "status": "passed"}
exit 0
```

The output's bytes were then checked against the recorded digest. The
`tests.test_edgartools_screen_custody` regression failed before publication
because the output artifact was absent; its completed locator-and-digest
check also failed while `output_file` was absent, then passed after the
locator was added. It guards a regular published file and exact hash binding.
The test uses the existing Python unittest harness and stdlib hashlib, not
another execution runner. See [CPython v3.13.16 unittest](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py)
and [hashlib](https://github.com/python/cpython/blob/v3.13.16/Lib/hashlib.py).

## Primary-source verification

The public tag `v5.62.0` resolves to
`5068cc548552fab1fbd061f1b8bccdc4e1677c6f`. Independent source reads at that
commit matched all eight source-file hashes and both public-fixture hashes
in the supplement.

- [Release v5.62.0](https://github.com/dgunning/edgartools/releases/tag/v5.62.0).
- [README install command, line 74](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/README.md#L74).
- [Vendor test dependencies and offline command](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/pyproject.toml#L253).
- [Vendor offline pytest harness](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/tests/_offline_harness.py).
- [SGML header parser](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/edgar/sgml/sgml_header.py#L453) and [SGML clock parser](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/edgar/sgml/sgml_parser.py#L320).
- [Entity parser](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/edgar/entity/parser.py) and [Form144 parser](https://github.com/dgunning/edgartools/blob/5068cc548552fab1fbd061f1b8bccdc4e1677c6f/edgar/ownership/form144.py).

The installation, test commands, returned counts, fixture/output hashes,
source hashes and failed attempts remain in the JSON supplement. It contains
public fixture identifiers only; no private wiring, data or ranking material
is part of this registration.

## Layer-resolution context

The [layer resolution protocol](../../docs/decisions/2026-10-11-layer-resolution-protocol.md)
was applied at repository base `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`.

- [The catalog layer](../landscape/us-equities.json) records
  `market-data-reference` as `keep_but_compare`, with a recorded verdict.
  `data-research` is its broader domain row, not a second independent
  layer verdict. The historical EdgarTools evidence is scoped to earlier
  acquisition/parsing runs.
- [The verdict-wave registry](../sota-convergence/layer-verdict-waves.json)
  points to [the 2026-09-22 wave](../sota-convergence/layer-verdicts-20260922.json),
  SHA256 `2fef6da7468a8e97a319fdc6f75f73374cd34b412bf93de90fd0c2a7504159de`.
- The latest registered sweep for `(us-equities, market-data-reference)`
  in [the saturation ledger](../saturation/ledger.json) is
  `landscape-sweep-20260926`. Its
  [manifest](../sota-convergence/manifest-20260926.json) has SHA256
  `a72177d162f84ba827028a7bff5ebc78ea9195c7a99ed2b411c75f7869b20e0e`;
  the [retained returns](../../evidence/artifacts/landscape-sweep-20260926/returns.json)
  have SHA256
  `ea7e8ed285639a247df91d0c64d9378e080bc820170e9fc773434488397f4600`.
  Databento, Massive, ArcticDB and tiingo-python remain recorded survivors.
  The retained search-cap failures and reopen condition remain unresolved;
  this screen does not adjudicate those alternatives.

The bounded delta is registration of already-completed, sanitized native
fixture evidence at the new pin. It opens no new survey, installs nothing
and makes no FINAL or multi-angle convergence claim. A newer unregistered
sweep, if present, would still require its retained public references before
any future layer-selection work; this registration is not a claim that the
registered ledger exhausts all ongoing research.

## Limits and completeness critic

The SGML acceptance timestamp must come from the SGML clock parser.
At this pin `FilingHeader.parse_submission_format_header` does not populate
`acceptance_datetime`; a submissions JSON timestamp is not a replacement.
The Form144 XML fixture supplies no header clock to certify.

The screen does not establish live SEC availability, original dissemination,
a historically as-known corpus, dataset completeness, predictive quality,
or a broker/order/strategy gate. The retained receipt covers selected
vendor tests and two public fixture types; it is neither the full upstream
suite nor a cross-provider comparison. These missing dimensions remain
inputs to future convergence, rather than being inferred from parser success.

The next layer sweep should consume this pin-specific evidence alongside the
unresolved survivor set and those availability/coverage limits. Registering it
preserves earlier successes and failures and does not silently replace them.

## Registration and verification

Use the maintained offline catalog interface:

```sh
python3 scripts/catalog_decisions.py --write --supplement catalogs/us-equities/edgartools-562-screen-20261015.json#/candidates
python3 scripts/catalog_decisions.py --check
python3 -m unittest tests.test_edgartools_screen_custody tests.test_catalog_decisions tests.test_catalogs tests.test_grand_catalog_counts -q
python3 scripts/validate.py
```

Before publication validation, refresh the evidence-manifest hashes for the
README, decision index, screen files and published fixture output with the existing
`host_receipts.register_file` helper, following the
[hot-file protocol](../../docs/lanes.md#hot-file-protocol). Keep those generated
registrations in the final commit.

The generated union carries the source-declared
`screen_passed_for_native_fixture_parsing` decision. These checks establish
repository consistency and pointer integrity, not a new upstream execution
or authorization to promote the candidate.
