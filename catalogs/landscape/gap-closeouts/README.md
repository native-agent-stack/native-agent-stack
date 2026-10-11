# Shared gap closeouts

Every layer uses this directory and the single loader in `scripts/component_matrix.py`.
The frozen `catalogs/landscape/gap-crosswalk-92bb279.json` remains the historical
judgment. A closeout records later evidence and review credit; it never edits that
crosswalk, selects a winner, changes a runtime pin or advances a host/trading gate.

Name each record `<layer_id>-YYYY-MM-DD.json`. Set `catalog`, `layer_id`, `date`,
`schema_version: 1`, the historical file's `source_crosswalk_sha256`, and a nonempty
`gaps` array. Each gap names its original `index` and the SHA-256 of its original
UTF-8 text as `source_text_sha256`. Required fields are:

| Field | Meaning |
| --- | --- |
| `status` | `proposed`, `settled`, `residual` or `blocked` |
| `reason` | Nonempty explanation of the actual evidence or remaining boundary |
| `evidence` | Retained `{path, sha256}` references; every file is registered in `manifests/evidence.json` |
| `vendor_paths` | Supported `{repository, pin, path}` sources; optional `command` records the supported invocation |
| `reviews` | Retained `{path, sha256, head, family}` JSON verdict references; `family` is `gpt` or `claude` |
| `category` | Required only for `residual` and `blocked`; uses the crosswalk's existing categories |

Register the closeout itself, every evidence file and every review in the
`files` array of `manifests/evidence.json` with their current SHA-256 and byte length. The loader
checks those registrations against the actual bytes and refuses changed, missing,
unregistered or wrong-scope inputs. The schema lives in `schema.json` and uses
Draft 2020-12; it validates through upstream `jsonschema==4.26.0`, available through
the existing hash-pinned `.github/requirements-ci.txt`. Before loading any
nonempty closeout set, the installed distribution must be exactly 4.26.0;
missing or mismatched versions refuse with the supported install command.
Descriptive `receipts` rows do not supply file registrations. If a receipt
also carries `sha256` and/or `bytes`, each supplied mirror must agree with
the authoritative `files` row; metadata-only rows remain valid. Reading
closeout records requires Python 3.10 or later; the existing no-record path keeps
the broader recording-script compatibility floor.

Each retained review JSON must contain `family`, the exact reviewed `head`, and
`verdict` (`pass` or `changes_requested`). Its family and head must match the
reference. Other report fields may retain detailed findings, source citations and
references to the original review output. Keep the raw verdict as registered
evidence when the reviewer also publishes a Markdown report. A verdict head is
review provenance; runtime/vendor sources and tests use maintained release or
main pins rather than transient PR commits.

Only `settled` removes a historical open gap from the current counts. It requires
both passing independent GPT and Claude PR reads of the same head, with distinct
retained report hashes and no `changes_requested` reference. Missing review credit
must remain `proposed` or `residual`; declaring `settled` without it refuses the
build. The record's disposition is explicit, so review presence does not silently
flip a proposed record. Hashes establish integrity; reviewers judge whether the
run/test/receipt actually closes the stated scope.

`proposed` preserves the prior category and counts. `residual` and `blocked` earn
their explicit category only with both passing family references; otherwise they
record as proposed and leave numeric state unchanged. A reviewed residual stays
open with its remaining login, host, production-data or other boundary. Later
reviewed dated records may supersede a prior disposition, including reopening it;
every older record and its
evidence bindings still validate. Two records cannot give duplicate indices within
one layer/date file. Dates are real ISO calendar dates, and the latest dated entry
with the necessary credit governs the current count.

After publishing a valid record, run the existing supported commands:

```sh
python3 scripts/component_matrix.py --write
python3 scripts/new_host_grand_list.py --write
python3 scripts/validate.py
```

The first loader PR contains no layer closeouts, so all current-main counts and
the generated matrix bytes remain unchanged. Layer PRs conform after this route
lands; earlier bespoke reference fields and recording scripts do not supply
closure credit through this loader.

Primary implementation: [jsonschema v4.26.0](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L307)
(`Draft202012Validator.check_schema`, `iter_errors` and `validate`) and the existing
repository's `scripts/catalog_decisions.py` confined loader and
`scripts/host_receipts.py` evidence registration at main
`9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.
