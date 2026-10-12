# Isolated Pi and OpenCode runtime trials

Four profiles provide native Claude Console and OmniRoute routes:
`ns-pi-claude`, `ns-pi-gpt`, `ns-opencode-claude`, `ns-opencode-gpt`.
All remain **trial** until the preregistered comparison selects them.

The renderer in `tools/adoption/runtime_profiles.py` reuses the canonical
Claude MCP renderer and the existing new-WSL wiring map. It installs unchanged
RTK hooks with RTK0.51.0 and Superpowers7.0.0 at its pinned vendor ref. Pi's
package bootstrap re-exposes all15 skills after package filtering; the CC
accepted package-level role scope and requires listing-size measurement.
OpenCode's native `permission.skill` is restricted only when the imported
canonical role explicitly grants Skill. Current imported roles grant Read,
so their native Skill helper stays denied; SKILL.md reads remain available.
Tier1 uses CNP's13-slot input by path, validates its27managed names against
the manifest and preserves its open gaps. Tier2 uses the pinned Skills1.7.0
CLI's unchanged `skills find` path; unset SKILLS_API_URL means skills.sh today.
The future local index can replace that URL through the vendor's documented
seam. A selected skill installs pinned through the existing installer into
the fresh worktree; interactive find installs from a default branch and do
not qualify as pinned Tier2 intake. No copy of CNP's derived input is published.

Existing NAS role texts are translated to native tool grants; review roles
retain their shell/write restrictions. Pi's missing builtin WebSearch remains
an explicit capability omission.

`ns-run <profile> <builder|reviewer|auditor|researcher> <brief.md>` fetches main,
creates a fresh Worktrunk worktree from origin/main, and runs the native client
headlessly. It writes private native events, derived invocation/usage receipts
and a CC handoff. Interactive launchers create fresh worktrees too; native Pi
session files and transient OpenCode exports feed the existing tracker. Counts
represent prompted or unclassified native calls, never organic-use rates.

Claude slots are selected fill-first4/3/2 using the existing no-token health
probe. Only credential_run injects the credential. OpenCode XDG isolation is
applied **after** the loader resolves its normal host store, so no credentials
are copied into a profile. GPT uses `http://127.0.0.1:21128/v1`. The repository's
old20128 template binding is corrected with a fail-before regression.

Profiles bind committed MCP entries and pins. Headroom, Grafana and Hindsight
are excluded under the CC's current ruling. SocratiCode is **pending E1**:
fresh worktrees have no index; path-per-call or incremental indexing needs
measurement. JCodeMunch retains committed stdio. Live version drift is currency
work, not a profile pin promotion.

Pi OTLP comes from the unchanged native `@b1tank/pi-otel@0.5.0` package,
`b1tank/pi-otel@3cd674533a8d24c9b8a2a6a94072eec25466e128`. OpenCode has native
OTLP export and AI SDK span configuration. Both use the committed WSL collector
endpoint21318; all Pi content-capture flags are false before first extension
load. The Pi extension's upstream local-mock integration test passes on both
its locked dependencies and an explicitly recorded Pi1.1.0 dependency override.
This verifies local mock export/redaction, not complete host collector receipt.

The auxiliary trial prefix uses the existing vendor install paths for
Tavily0.1.8, agent-browser0.38.2 and OpenResearch0.2.15. Version/help invocations
prove execution only; browser automation, authenticated search and research
quality require separate receipts. No new model loop, MCP bridge or fork is
introduced.

Evidence stays within its measured scope:

- [Stage A](STAGE-A.md):35candidates,11documentedpassers,169pinnedreferences.
- [Vendor contracts](VENDOR-SOURCES.md): Pi1.1.0 at04566631 and OpenCode1.18.35
  at53d1eabb; current mirror4d9678a7 is2.0.26 and is distinct.
- [W6 registration](W6-PREREGISTRATION.md) and [replay ledger](REPLAY-SOURCES.md):
  no comparative execution or final selection.
- `receipts/`: sanitized derived facts. Private runtime/config/auth/session/lock
  roots are never copied, hashed or published. The historical private lock scan
  finding is resolved by the CC's vendor-source evidence boundary; raw
  historical artifacts stay untouched.

OmniRoute carries the CC label **"pass-through measured 2026-10-12 for the
reads' configuration (instructions present)"**, with these limits verbatim:

- A same-length rewrite is not detected.
- The output side is checked only by the echo canaries.
- Plugins or payload rules that preserve token counts and canaries are not detected.
- The ~8-token no-instruction default is not attributed (OmniRoute or the provider).
- The effort evidence is directional.
- The header evidence is self-reported by OmniRoute.
- The result holds for OmniRoute 3.8.51 and this route. A version or route change needs a re-run (the scripts here
  re-run as-is: `probe2.py cx/gpt-6-astra 3 out.json`, `probe4.py out.json 2 <dir>`).

The measurement used cx/gpt-6-astra; these profiles' GPT model is
cx/gpt-6.1-sol. It does not prove every model/route combination unchanged.

The independent GPT implementation review at58a05d03 reproduced four P2s:
interactive Claude/OpenCode collection lost its XDG isolation after the loader;
the renderer added an ungranted native Skill helper; Unicode line separators
inside valid native JSON erased usage/handoff records; Pi MCP exit0 could mean
empty or disabled servers. The follow-up commit restores the isolated
collection environment, preserves imported grants, uses LF-only JSON framing
and requires each mandatory MCP name to be connected. Regression fixtures fail
at58a05d03 and pass with these fixes. Native historical smokes remain bound to
their original profile generation and main head, not relabeled as new runs.
