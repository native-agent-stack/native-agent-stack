---
name: native-stack-research
description: Use for current public facts, source-backed technical research, and comparisons of upstream tools with GPT Researcher. Use DeerFlow when the task requires two independent research outputs.
---

For authorized public research, run the installed GPT Researcher route:

For ecosystem discovery, upstream comparison or layer convergence, first read
`docs/decisions/2026-10-11-research-convergence-practice.md` in the owned source
checkout and the layer's recorded verdict and latest retained sweep, including
pending observations. Research the unresolved delta; a CLOSED practice reopens
on a new practice-tool release or a measured practice failure. If the source
checkout or those inputs are unavailable, obtain their pointers from the research
owner before dispatch. Ordinary public-fact questions use the routes below.

Gathering ends with sources and retained usage/failures. Candidate decisions then
use the existing blind layer-verdict lane; a gatherer's answer is an input to that
lane. FINAL requires verdict, run pin, upstream E2E and measured invoke evidence
or a recorded non-invocation reason. Unsettled layers carry one dated,
preregistered comparison and fixed rule as SCHEDULED; RETIRED carries a reason.
Keep PR review findings within the recorded candidate and the full current-head
Claude/GPT/Codex wave; route other findings to one-line Follow-ups and their
research owner under the decision's rules 1–9.

```bash
bash "${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack/gpt-researcher.sh" "short current-month query"
```

Run the command in the foreground and wait for its final exit. Allow at least
1500 seconds per call; request a 1560000 ms foreground tool timeout when the
tool accepts milliseconds. Native session tools continue with their returned
session id until final exit. The route's 1500-second watchdog owns execution;
preflight alone produces no research report.

When the task requests a second independent output, run the installed DeerFlow
headless route with its native default public configuration:

```bash
bash "${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack/deer-flow-research.sh" "short public research query with source URLs"
```

Apply the same foreground wait and per-call timeout. Each route prints its run
directory. Inspect the GPT Researcher report's References and DeerFlow's
`answer.md`, then verify the claims in the primary sources. Completion requires
the returned command result and a retained report with sources; a completed
session or background start alone is insufficient.

Report the two outputs and each failed attempt separately. The exact DDGS
empty-result outcome records provider availability and leaves the research
answer unqualified. Keep unknown usage unknown and keep account secrets out
of queries, reports and environment files.

Sources: [GPT Researcher CLI](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/cli.py#L336),
[DeerFlow native CLI](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1837),
[DeerFlow model and tools](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L250),
[DDGS adapter](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/community/ddg_search/tools.py#L190).
The installed repository routes supply the default config and per-call watchdog;
`install-plan.json` carries provider custody decisions.
