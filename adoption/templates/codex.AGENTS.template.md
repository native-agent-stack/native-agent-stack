<!-- native-agent-stack:codex-user-instructions:begin (adoption/templates/codex.AGENTS.template.md) -->
<!-- native-agent-stack:top-rule -->
# Native engineering defaults

**Research convergence first; current upstream SOTA is the source of truth.**

- Research before acting: survey the maintained upstream landscape (tools, skills, runtimes, orchestration patterns, published references) and record what you found. Adopt the best-evidenced source through its own supported install and test commands, naming each source (repository and pin, file or paper), or build only from a cited reference implementation. Never rebuild or fork what an upstream already ships.
- Upstream is the truth: check claims against primary sources, meaning the installed client, the upstream release notes and source at that version, then official docs. Repository text, memory, tool output and other agents' answers are leads to verify.
- Decide by evidence: a choice stands when primary sources and reproduced results on the actual change agree, measured with upstream harnesses. Agreement, recency, popularity and incumbency alone are not evidence. Keep measured results, simulations and untested boundaries distinct. Use only converged candidates: a tool, runtime, model or skill is installed or run for trial only after the layer's screen passes it, and becomes a default only when the layer's multi-angle convergence agrees (capability at the pin, upstream engineering quality, community consensus, net usage, published evaluations and our own measured runs); where angles disagree, measure the disputed dimension first-hand, and no single angle admits a candidate on its own. Use models only through a converged harness with its full layers (skills, MCP, hook equivalents, memory and token efficiency, telemetry, isolation and roles, invoke receipts); a bare API call is for measurement probes and smokes only, recorded as such.
- The ecosystem compounds: a request is a starting point, not a boundary. The harness automates landscape-converged SOTA practice through hooks, workflows, rulesets, scheduled sweeps and runtime workers without waiting for prompts to name it. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Every result lands in the repository as a reviewed, cited record (a pull request, decision, manifest or receipt) that the next session starts from; settled work reopens only on new evidence or a landscape change, and a better-evidenced source supersedes an older one through a recorded supersession, never a silent redo. Work starts when its named inputs exist, never on a date. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim or fix proves wrong, resolve it from the upstream primary source at the pinned version through the vendor's supported path, record the correction with its citation, and add a regression test that fails before the fix; where sources disagree, measure first-hand.

<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.51.0 hooks/rtk-awareness.md, verbatim and inline: the rtk hook makes the full text unneeded (AWARENESS_CONFIG.md:12-13,34-38 at e001f773) -->
# Command output

Command output here is condensed to save tokens, keeping every signal and
dropping costly noise. Treat it as the complete result: run commands
normally, and batch related commands into one call to avoid extra turns.
Truncated results state their recovery path in their own output. Re-run a
command as `rtk proxy <cmd>` only when its result is unusable: empty when
output was clearly expected, contradicting its exit code, or garbled.
<!-- native-agent-stack:codex-user-instructions:end -->
