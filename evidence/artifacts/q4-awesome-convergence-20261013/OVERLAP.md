# Raw versus rendered repository-set overlap

The original uniform raw collection finished at 2026-10-13T02:52:35Z. Every selected
list, including the oversized MCP README, used `application/vnd.github.raw`
at its recorded commit. HTML is a cross-check only; it supplies no membership
counts. Each list's media types, refs, file hashes and headings are in
`corpus.json`; the full set differences are in `overlap.json`.

The set identities here are normalized requested owner/repo values. Canonical
GitHub repository identities have not yet been resolved, and no distinct-list
threshold result has been produced.

Remeasurement at the same pins finished at 2026-10-13T03:01:48Z. All nine
supported HTML comparisons now meet 0.95. The MCP source has no HTML
measurement. Original raw byte hashes and URL sets agreed across the
remeasurement; the raw refinement changes section attribution, not targets.

| List | Before Jaccard | After Jaccard | Before → after raw only | Before → after HTML only |
| --- | ---: | ---: | ---: | ---: |
| Shubhamsaboo/awesome-llm-apps | 1.000000 | 1.000000 | 0 → 0 | 0 → 0 |
| avelino/awesome-go | 0.998978 | 0.998978 | 3 → 3 | 0 → 0 |
| awesome-selfhosted/awesome-selfhosted | 1.000000 | 1.000000 | 0 → 0 | 0 → 0 |
| e2b-dev/awesome-ai-agents | **0.862385** | **1.000000** | **15 → 0** | **0 → 0** |
| hesreallyhim/awesome-claude-code | 1.000000 | 1.000000 | 0 → 0 | 0 → 0 |
| ichangyou/awesome-codex | 1.000000 | 1.000000 | 0 → 0 | 0 → 0 |
| kyrolabs/awesome-agents | 0.994624 | 0.994624 | 1 → 1 | 0 → 0 |
| punkpeye/awesome-mcp-servers | Not available | Not available | — | — |
| sindresorhus/awesome | 1.000000 | 1.000000 | 0 → 0 | 0 → 0 |
| vinta/awesome-python | 1.000000 | 1.000000 | 0 → 0 | 0 → 0 |

`e2b-dev/awesome-ai-agents@9596ab1e69fbbb6c95291141c8dab5c181083216`
has 109 raw targets and 94 rendered-link targets: 94 in the intersection,
109 in the union. Its README is the only compared file. The 15 raw-only
targets are:

- assafelovic/gpt-researcher
- biobootloader/mentat
- cpacker/memgpt
- dot-agent/dotagent
- felixbrock/lemon-agent
- jina-ai/dev-gpt
- memfreeme/memfree
- openbmb/agentverse
- paul-gauthier/aider
- pj4533/yourgoal
- rumpfmax/multi-gpt
- seanpixel/teenage-agi
- smol-ai/developer
- team-openpm/workgpt
- topoteretes/promethai-backend

The discrepancy was adjudicated as a defect in the HTML adapter: it skipped
repository anchors inside h1–h6. A native HTML read at the same e2b pin on
2026-10-13T03:01:30Z independently confirmed the Aider anchor inside h2.
The corrected cross-check includes these anchors and omits `a.anchor`/`#`
permalinks. All fifteen former differences disappear. The original measurement
is retained in `overlap-before-heading-fix.json`; `overlap.json` contains the
remeasurement and all remaining differences.

Raw heading entries now retain the full `entry_heading` and use their nearest
preceding higher-level parent as `section`. Two synthetic controls failed
before these fixes (20 tests, two failures) and passed afterward. The suite
then grew to 23 passing controls, including the distinct-list versus
category-support threshold and batched renamed/missing API identities.
These fixtures do not constitute upstream acceptance or verify every live
target's capability.

After the gate cleared, all 9,969 unique raw targets were canonicalized through
the native API; 29 remain unresolvable. The count uses raw source exclusively.
Neither the original failed cross-check nor the corrected HTML supplies list
membership votes.

Publication now stores opaque pins/digests in the name-free `identifiers.json`
registry. `sources.json` resolves list/document IDs to repository/path metadata;
the script resolves the identifier references in all receipts. These structural
references preserve the before/after measurements and source hashes without
mixing repository names and opaque pins in a count file. The final synthetic
suite contains thirty passing controls; staged native Gitleaks reports zero
findings, with scanner and ignore configuration unchanged.
