# Receipts for the plugin pin record (CPA-V-11 stage 1, 2026-10-13)

Value-free captures behind [the decision record](../../../docs/decisions/2026-10-13-plugin-pins-stage-1.md) and [`adoption/plugins/pins.json`](../../../adoption/plugins/pins.json): documentation lines,
commits, counts and file names only. Nothing here holds an account name, a host name, a home path or a key.

| File | What it shows |
| --- | --- |
| `receipts/docs-excerpts.txt` | the lines of the plugin marketplace reference (the plugin sources' `ref` and `sha`, the marketplace sources' fields without `sha`) and the marketplace guide that cite them, with each page's size and sha256 (fetched 2026-10-13) |
| `receipts/changelog-excerpts.txt` | the three changelog lines of the client at `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` that introduce the commit pin, the archive checksum and the install with a gone `ref` |
| `receipts/tag-resolution.txt` | `git ls-remote` of the three marketplaces' repositories for the tags the templates name (and the newest tag of `context-mode`'s version, and its default branch's tip) |
| `receipts/context-mode-compare.json` | GitHub's compare for `context-mode`: the reviewed commit against the commit the first host installed (21 ahead, `stats.json` only), the tag's commit against the reviewed commit (133 behind, bundled files differ) and against the installed one |
| `receipts/official-marketplace-pins.txt` | the vendor's marketplace at `f359d43b`: 315 entries, the 262 external ones all with `sha` |
| `receipts/observed-registry.json` | the first host's installed commits and versions of the three plugins, from its registry (no install path) |
| `receipts/fail-before.txt` | the test against main at the time of writing, where no record exists, and against this head |
| `receipts/mutants-17.txt` | the 17 mutants of the record, the templates, the guide and the receipts: 17 of 17 killed |
| `receipts/mutants-round1-29.txt` | review round 1: the six mutants of the round (a plugin enabled by a list, by an empty list, in the additions template; a built-in of another marketplace; the pinned commit under a look-alike header and under the repository listed next) over the pushed head's test module (all survive) and this head's (all killed); five controls the client does not enable (green in both); the 17 mutants of the first head (still killed); and the sha predicate on a 41-character value |

The capture script and the mutation driver are scripts of the author's private record; the commands are the receipts' own (`git ls-remote`, `gh api repos/<repo>/compare/<base>...<head>`, `git show`).
The measurements are the author's, taken on one host with one client version; nothing here is a measurement by an independent party.
