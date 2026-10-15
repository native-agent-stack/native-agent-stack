# Jev scored-contract correction evidence

This record corrects the three local P2s adjudicated after #1150. It contains
local contract checks and synthetic plumbing only. No model, paid transport,
credential store, environment file or scored inference was used.

| Artifact | Evidence class | Meaning |
| --- | --- | --- |
| `validation.json` | local_integration / synthetic | Named RED/GREEN assertions, frozen-source content reproduction and required repository validation |
| `guard-mutants.json` | synthetic | 113/113 named mutations killed; source bytes preserved; variants reconstruct from the published source and mutation definitions |
| `syn/` | synthetic | Current fake-transport run with both versioned models and retained request/report/receipt bytes |

The original build's `frozen-source-check.json` supplies nine already published
public-dataset-derived content pins. All nine were rechecked against the retained
source bytes. Only the valid-pack and relabel-refusal outcomes are retained here;
dataset text and private provenance fixtures are not published.

Tests and SYN used read-only live mounts, a private `/var/tmp` removed afterward,
fresh `/dev` and `/proc`, and bubblewrap `--unshare-net --die-with-parent`.
The original build's evidence remains historical at its recorded source revision.
This directory supersedes its scored-content, ECE tie and partial-receipt claims.
