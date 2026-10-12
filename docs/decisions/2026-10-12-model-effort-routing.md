# Decision: each Claude agent definition carries its routed model and effort (2026-10-12)

**Decided by:** the command center's ruling of 2026-10-12 on model and effort routing (audit finding CPA-C-001),
acting on the owner's instruction that day to route work to Haiku and Sonnet where they fit instead of running
everything at the top setting, which restates their 2026-10-11 rule: the cheapest model and effort that holds
quality, `max` only where a protocol or a measurement demands it. Implemented by the api-actions lane, which also
measured what decides a child's effort (below). The command center's addendum 01 to the ruling accepted the
measurement.

**Supersedes,** for effort, [2026-09-23-max-effort-default.md](2026-09-23-max-effort-default.md) (`max` for every
Claude child). Its saved-workflow rule stands: a saved stage still binds `effort: 'max'`. Its agent-definition rule
is replaced by the table below. The coordinator's own effort is not decided here
([2026-09-29-max-default-effort.md](2026-09-29-max-default-effort.md) and the ruling's launcher step).

## Decision

The shipped agent definitions (`adoption/agents/claude/`, byte-identical in `.claude/agents/` and, for the agents
it ships, `examples/claude-native/agents/`) carry the model and effort of the ruling's table:

| Agent | Work class (the ruling's table) | Model, effort |
| --- | --- | --- |
| `source-scout` | exact extraction, inventories, running named acceptance commands | Sonnet, medium |
| `stack-verifier` | command re-runs and claim checks without judgment | Sonnet, medium |
| `stack-researcher` | research and synthesis on named sources | Sonnet, high |
| `isolated-builder` | builders, on gate-relevant code by default | Opus, high |
| `evidence-reviewer`, `security-reviewer`, `semantic-evidence-reviewer` | reviews, security review | Opus, xhigh |
| `blind-lane-reviewer`, `blind-adjudicator`, `blind-judge` | blind protocol roles | Opus, max (their protocol's value) |
| `landscape-sweep-worker` | the landscape sweep's workers | Opus, max (their protocol's value) |

No definition is on Haiku. The one same-packet extraction trial (2026-09-21,
[docs/ultracode-token-routing-20260921.md](../ultracode-token-routing-20260921.md) item 4, line 20) had the Opus
verifier score a Sonnet inventory 14/14 lane rows and a Haiku 4.5 inventory 9/14, one row a quote attributed to a
file that does not hold it; Haiku 5.5 is unmeasured on that task. So `source-scout` stays on Sonnet, and Haiku stays
a per-launch choice for mechanical work, which every spawn honors (below), until a repeat trial on Haiku 5.5 returns
no unanchored citation on two distinct packets (the README's overturn condition).
`isolated-builder` defaults to the gate-code tier; a builder on non-gate code is launched with a per-launch Sonnet.

**Coordinator guidance.** A child launched with `name` (a teammate) runs at its definition's effort, or, when the
definition sets none, at the session's; it drops a per-launch `effort`. To run a child at another effort, launch it
without `name`; the per-launch `model` is honored either way.

## Evidence

Measured on Claude Code 2.1.296 (`claude --version`; every transcript row records `"version": "2.1.296"`), on the
host whose user settings set `effortLevel` and `modelSettings` `effortLevel` to `xhigh` for Opus, Sonnet and Haiku
5.5, with `CLAUDE_CODE_EFFORT_LEVEL` unset in the shell, in the settings' `env` and in every command-center launcher.
Each value is the `effort` field (equal to `perTurnEffort`) of the first assistant row of the native transcript, the
session's or the child's (`<session>/subagents/`).

| # | Where | Session | Child launched as | Child model, effort |
| --- | --- | --- | --- | --- |
| P1 | headless `-p`, bare directory | no `--effort` | (session row) | haiku, xhigh (settings) |
| P2 | headless, bare directory | `--effort low` | (session row) | haiku, low |
| P3 | headless, bare directory | `--effort max` | unnamed; definition `effort: low` | haiku, low |
| P4 | headless, bare directory | `--effort max` | unnamed; no definition effort; per-launch `low` | haiku, low |
| P5 | headless, bare directory | no `--effort` | as P3 | haiku, low |
| P6 | headless, bare directory | no `--effort` | as P4 | haiku, low |
| P7 | headless, a checkout of main | `--effort max` | unnamed `general-purpose`; per-launch haiku, `low` | haiku, low |
| P8 | headless, a checkout of main | no `--effort` | as P7 | haiku, low |
| P9 | headless, a checkout of main | `--effort max` | unnamed `source-scout` (definition `effort: max`); per-launch sonnet, `medium` | sonnet, medium |
| P10 | interactive (session effort xhigh) | — | unnamed `general-purpose`; per-launch haiku, `low` | haiku, low |
| P11 | interactive (xhigh) | — | **named** `general-purpose`; per-launch haiku, `low` | haiku, xhigh |
| P12 | interactive (xhigh) | — | **named** `source-scout` (definition `effort: max`); per-launch haiku, `low` | haiku, max |
| CC | interactive, the command center's session started `--effort max`, 13:28Z to 16:51Z | `--effort max` | 23 **named** children, per-launch effort `low` to `xhigh` | the per-launch model each time; max every time |

What decides a child's effort, then: for an unnamed child, a per-launch `effort`, else its definition's, else the
session's level; for a named child, its definition's, else the session's level. `--effort max` on the session
reaches only the children whose definition sets no effort. The probe scripts, their JSON results and the command
center's transcript scan are kept with the api-actions lane's records (`readers/effort-probes-20261012/`, with a
SHA256SUMS); transcripts hold local session identifiers and paths and are not published.

**Upstream, at this version:**

- [Sub-agents](https://code.claude.com/docs/en/sub-agents.md), read 2026-10-12T17:01:02Z (108,551 bytes, sha256
  `dd3f22aa021a3525f48227321c34eab28b322d7ab77cb3d5fc01ddd048e8f6ea`): line 316, the `effort` field "Overrides the
  session effort level, but not the `CLAUDE_CODE_EFFORT_LEVEL` environment variable"; lines 417-421, a per-invocation
  `effort` parameter for a non-fork subagent "overrides the `effort` field", from 2.1.292. The page does not say what
  a named (teammate) spawn does with the parameter; P11 and P12 measure that it drops it.
- [Model configuration](https://code.claude.com/docs/en/model-config.md), read 2026-10-12T17:01:02Z (116,499 bytes,
  sha256 `8f65d1b1463bc7e24fa0eeeadd290278162b1f26c56be6190a1db510de8d7ca0`): lines 605-609, the session's effort
  resolution order (the environment variable, `--effort` or `/effort`; then settings; then the model's default), and
  line 613 (a top-level user `effortLevel` does not count for Opus 5.5; a per-model level does).
- The client's changelog (anthropics/claude-code `CHANGELOG.md` in the local mirror, 2.1.296 at line 3): line 298,
  2.1.292 "Added an `effort` parameter to the Agent tool"; line 657, a team agent "spawned by name now runs with its
  own prompt, tools, disallowedTools and effort instead of the defaults".

**Tests.** `tests/test_install_claude_profile.py` (`ShippedAgentEffortTests`) holds each shipped definition at its
routed model and one effort line; on main's definitions it fails 7 times, once per rerouted agent. The examples'
static contract (`examples/claude-native/workflows/test-envelope.mjs`) checks each project agent against its routed
effort (`AGENT_EFFORT`) instead of the stage effort, and its mutation suite moves each agent above or below its level
and a blind role off `max`.

## Alternatives considered

- **A per-launch `effort` on every Agent call, definitions unchanged at `max`.** Rejected: a named child drops it (P11,
  P12, and all 23 of the command center's children), so it does not reach the children that carry most of the work.
- **Removing `--effort max` from the launchers only.** Necessary for the sessions themselves and for named children
  whose definition sets no effort, and the ruling does it at each session's next relaunch; it leaves every definition
  that says `max` at `max`.
- **Haiku for `source-scout`.** Not adopted: the only same-packet result (Haiku 4.5, above) failed, and Haiku 5.5 has
  no such result yet; Haiku stays a per-launch choice for mechanical work.

## Comparison that would overturn it

The ruling's reopen rule: a lower tier is raised for a work class when a gate read or the other review family finds a
reproduced miss that the tier's output should have caught, recorded with both records' paths. A client change that
makes a named child honor a per-launch effort reopens the coordinator guidance; it does not change the table.
