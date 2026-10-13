# V2 raw / native HTML cross-check

Count input remains pinned `application/vnd.github.raw`; native Contents HTML is a coverage cross-check. Every measured list meets the unchanged 0.95 gate after correction. The oversized MCP README has no supported HTML measurement and has `jaccard: null` in the current receipt.

The first v2 read of VoltAgent/awesome-claude-code-subagents at its frozen pin measured 11/13 = 0.8461538461538461. Its README line 2 is an image at the reserved GitHub user-attachments surface, not a repository. Line 514 is the codex-link reference definition, which no visible reference link uses; GitHub does not render it. The co-op verified both source locations at that pin. The disagreement was reported before canonicalization or counting.

The revised rule excludes GitHub's reserved nonrepository owner surfaces and counts a reference definition only when a visible full, collapsed or shortcut reference link uses its label. Code-only and image-only reference uses do not qualify a definition. Used definitions keep their source section/line; unused definitions are retained outside counted rows, with per-list counts. This is a recorded refinement of the earlier all-definitions rule. The heading mapping remains unchanged.

Three fixture controls failed before correction (three assertion failures, exit 1, 0.003s) and passed afterward (exit 0, 0.002s). Every list was then re-read at exactly the original v2 pin; every source digest was checked against the first read. The source read completed 2026-10-13T04:47:23Z. Fourteen supported comparisons pass; subagents reaches 1.0. Two unused definitions are audited separately.

| List | Before | After | Raw-only / HTML-only after |
| --- | --- | --- | --- |
| 0xNyk/awesome-hermes-agent | 1.0 | 1.0 | 0 / 0 |
| ComposioHQ/awesome-claude-skills | 0.972973 | 1.0 | 0 / 0 |
| FreedomIntelligence/Awesome-AI4Med | 1.0 | 1.0 | 0 / 0 |
| KarelDO/awesome-codex | 1.0 | 1.0 | 0 / 0 |
| Shubhamsaboo/awesome-llm-apps | 1.0 | 1.0 | 0 / 0 |
| VoltAgent/awesome-claude-code-subagents | 0.846154 | 1.0 | 0 / 0 |
| VoltAgent/awesome-design-md | 1.0 | 1.0 | 0 / 0 |
| WenyuChiou/awesome-agentic-ai-zh | 0.996016 | 0.996016 | 1 / 0 |
| ai-boost/awesome-harness-engineering | 1.0 | 1.0 | 0 / 0 |
| ccplugins/awesome-claude-code-plugins | 1.0 | 1.0 | 0 / 0 |
| e2b-dev/awesome-ai-agents | 1.0 | 1.0 | 0 / 0 |
| hesreallyhim/awesome-claude-code | 1.0 | 1.0 | 0 / 0 |
| jqueryscript/awesome-claude-code | 1.0 | 1.0 | 0 / 0 |
| kyrolabs/awesome-agents | 0.994624 | 0.994624 | 1 / 0 |
| punkpeye/awesome-mcp-servers | Unavailable | Unavailable | 0 / 0 |

Exact values, full two-way differences, media types, pins and paths are in `overlap-before-reference-fix.json` and `overlap.json`; complete before/after source rows are in `raw-before-reference-fix.json` and `raw-progress.json`. The historical first-read receipt used an empty-set Jaccard placeholder of 1.0 for the unavailable MCP render; its status was always not_available, and it supplies no measured overlap. Current unavailable comparisons use null.

The remaining below-perfect differences are retained without method tuning because both pass 0.95. V1's different selection, failures and heading correction remain historical in the separate SUPERSEDED directory. No model is invoked by this counter; these source checks do not establish runtime acceptance or a convergence verdict.
