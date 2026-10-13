# Receipts for the sandbox read-deny overlay (CPA route B, 2026-10-13)

Value-free captures behind [the decision record](../../../docs/decisions/2026-10-13-sandbox-readdeny-credentials.md): status words, counts and file names only. The probe ran the installed Claude Code 2.1.296 in
scratch homes with synthetic credential files and a loopback stand-in for the Messages API (no model, no credential, no network beyond 127.0.0.1); nothing here holds an account name, a host name, a path or a key.

| File | What it shows |
| --- | --- |
| `receipts/arms.json` | the six arms of `tools/sandbox-probe/readdeny_probe.py` (no sandbox; sandbox on with nothing denied; sandbox on with the shared template's rules; the overlay's `denyRead` alone; the overlay with the user scope loaded; the overlay under `--setting-sources project,local`), three repeats each, reduced to status words by `tools/sandbox-probe/summarize.py`: the 14 credential files read by a shell loop and by Python, a symlink, a copy, directory listings, the Read tool on a credential and on a decoy, ordinary commands, tool errors and the sandbox's `/proc/<pid>/...` error |
| `receipts/arms-research.json` | the arms of the same method that decided the design (the template's rules with and without the one rule that breaks sandboxed commands; `allowRead` of the `/proc` paths), three repeats each |
| `receipts/docs-excerpts.txt` | the lines of the sandboxing, settings and CLI pages that the record cites (fetched 2026-10-13T23:06Z, with each page's size and sha256) |
| `receipts/mutants-18.txt` | the 18 mutants of the overlay, the shared template's rules, the probe's fixtures and the receipts: 18 of 18 killed (the first run left one, a mutant aimed at the wrong row of the arms receipt, now aimed by arm) |

The probe is part of the change (`tools/sandbox-probe/`); the mutation driver is a script of the author's private record. The measurements are the author's, taken on one host with one client version;
nothing here is a measurement by an independent party.

## Claims of the decision record without a receipt here

- **The text guard's hook and a sandboxed worker's Read tool**: the record says the hook is registered in the user scope, which `--setting-sources project,local` leaves out; that was not measured.
- **macOS and Windows clients** were not run.
