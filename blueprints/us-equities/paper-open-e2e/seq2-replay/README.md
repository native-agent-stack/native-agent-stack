# Retained seq2 replay sources

These five files are exact copies of the private paper-open-e2e deployment's
main-8c95a50d-sequencing-v2 replay modules. They previously had no git history
and were absent from the predecessor runtime SHA256SUMS. Publishing the bytes
through this reviewed PR establishes a source commit the CC can use for a
separate authenticated replay inventory. It does not retroactively make them
part of the original seq2 seal.

Every file was compared before and after copying. No content, import, path,
line-ending or fixture change was made. The SHA256 values below commit only
to the complete source bytes published alongside this README.

| File | Bytes | Before copy SHA256 | After copy SHA256 |
| --- | ---: | --- | --- |
| test_wiring.py | 12165 | fbeaccb7d6f3a1db4d6856d2f73c9e856b0487f8e5e1088f6e0ea8372a41af64 | fbeaccb7d6f3a1db4d6856d2f73c9e856b0487f8e5e1088f6e0ea8372a41af64 |
| test_go_issuer.py | 7117 | 8067842e690b18a547e331d0e2bdebb07c7c05c574245c52706ad356378f3f6c | 8067842e690b18a547e331d0e2bdebb07c7c05c574245c52706ad356378f3f6c |
| test_sequencing.py | 12330 | 08b6628f6525264afa59173bc84276ca5c9787ddc56487e7054a99c50b9a11bf | 08b6628f6525264afa59173bc84276ca5c9787ddc56487e7054a99c50b9a11bf |
| test_unit_contracts.py | 3805 | 44fd3d7ded879319ab3f1424aa473843a143c9aed3af2babe3cf83d5eacc93cd | 44fd3d7ded879319ab3f1424aa473843a143c9aed3af2babe3cf83d5eacc93cd |
| test_data_wiring.py | 5157 | fedf0e33beb7f7c25f36be739f96759433217195464a9d229ac1a3a073689108 | fedf0e33beb7f7c25f36be739f96759433217195464a9d229ac1a3a073689108 |

The runtime/config source was NAS main
8c95a50d10bd2db0b59058c6827275917ce35aa3. That pin names the frozen engine,
not the original authorship of these deployment-only modules. The new landed
commit, after both-family review, will establish their first git provenance.
The CC's subsequent record must state this distinction.

These are retained replay inputs, not a standalone runnable package. Their
unchanged ROOT and imports expect the sealed bundle's sibling launch.py,
issue_go.py, launch_data.py, data_worker.py, configs and units. They deliberately
live outside ordinary tests/ discovery. An owning deployment evaluator must
bind the landed git bytes and provide the bundle context and SYN isolation;
do not import them directly against the host's installed runtime. No import
rewrite or copied runtime is included here.

Privacy review found no real key/token, non-no-reply email, broker account
number/id, credential content or verbatim owner quote. Named API variables
and synthetic-key/synthetic-secret in the data test are explicitly inert
fixture values. Its date-bearing scan protocol is not an account number.
Machine paths and marker names are retained unchanged under the CC's rule.
The focused gitleaks scan passed with zero findings. No scan rule changed.

Validation for this archival copy is exact byte/hash equality and in-memory
Python syntax compilation for all five files, without imports or execution.
This PR makes no new lifecycle, broker acceptance or deployment claim. The
existing SYN drill's historical results are not repeated as new evidence here.

Source basis: CPython v3.12.3 at
f6650f9ad73359051f3e558c2431a109bc016664,
Lib/unittest/loader.py (loadTestsFromModule) and Lib/unittest/mock.py (patch),
are the maintained discovery/isolation mechanisms these retained modules use.
The selected native engine remains NautilusTrader 2.0.0rc5 at
1b0a49d2792a9432a3aca3fcb617ce7a630d905e; no engine or loader is replaced.

Landing order is #1087's P1-exception, the model-currency incident PR #1101,
then this source-publication PR. Two-family reads (local plus Astra), a landed
source pin and the CC's authenticated replay record are required before seq3
binds these inputs. No seq2 file or seal is edited; no STOP/HOLD, journal,
receipt, service, GO or account operation occurs here.

Follow-ups: bind the landed source in the CC's new inventory and the future
seq3 consumer, then run the strict seal/full SYN/validity workflow. Runtime
consumer changes and the existing #1087 P2s stay outside this copy-only PR.
