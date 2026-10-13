# Receipts for the installer's agents step: links, folders and CLAUDE_CONFIG_DIR (2026-10-13)

Value-free captures behind the measurements of [the decision record](../../../docs/decisions/2026-10-13-installer-agent-links-and-config-dir.md), taken on the first host with Claude Code 2.1.296 (headless
starts in scratch homes with a synthetic key and a loopback base URL nothing listens on, each killed at its system init record: no model call). Nothing here holds an account name, a host name, a home path,
a key or a transcript: definition names, counts and flags only.

| File | What it shows |
| --- | --- |
| `receipts/client-agents-probe.json` | six init-record runs: which `zz-` definitions the client lists with no `CLAUDE_CONFIG_DIR`, with it set to a folder beside the home's own, with a link to a file, with a link to nothing, with an empty value (the client's working directory) and with a relative value (resolved against it) |
| `receipts/docs-excerpts.txt` | the lines of the environment-variable and sub-agents pages (fetched 2026-10-13, with size and sha256) that the decision cites |
| `receipts/fail-before.txt` | the new tests against the sources of the base `329985de1` and against this head |
| `receipts/mutants-installer.txt` | the 15 mutants of the change (link and folder handling, the temporary copy, the variable's reading and normalization): 15 of 15 killed; the first run killed 14 and the survivor is killed by the lexical-collapse assertion of its test |

The probe driver is a script of the author's private record; the method is in the record and in the receipt. The measurements are the author's, taken on one host with one client version; nothing here is a
measurement by an independent party.

## Claims of the decision record without a receipt here

- **The skills and workflows steps' folders under `CLAUDE_CONFIG_DIR`** were not measured; the record lists them as a follow-up.
- **A resume or a project-scope definition** of the same name: the record's decision concerns the user scope only.
