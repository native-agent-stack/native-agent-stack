# GPT-lane harness bake-off ranking (proposal for the CC, not a default)

Source: SCORES.json (census 2026-10-17T21:08:18Z, 72 listeners, 0 violations). Model cx/gpt-6.1-sol, effort max, via the OmniRoute gateway. Baseline: codex-exec (codex-cli 0.163.0).
Rule: T1 correct = reply cited 76 / actual 77. T2 correct = reply changed_line 77 AND tests_ok true (strict: a reply of 141 counts wrong even where the file and unittest pass).

## 1. Ranking per job class (correctness, then median wall s, then median tokens in+out)

### Code reading (T1), 2 reps each
| # | Harness | Correct | Wall s | Tokens in+out |
|---|---------|---------|--------|---------------|
| 1 | pi | 2/2 | 4.4 | 2,168 |
| 2 | oh-my-pi | 2/2 | 8.6 | 9,977 |
| 3 | deerflow | 2/2 | 11.0 | 26,590 |
| 4 | openhands | 2/2 | 31.1 | 13,124 |
| 5 | codex-exec (baseline) | 2/2 | 59.0 | 31,485 |
| 6 | opencode | 2/2 | 65.9 | 5,075 |
| 7 | kilo | 2/2 | 94.8 | 6,250 |
| 8 | goose | 1/2 | 10.0 | 5,028 (rep 1 unmeasured) |

### Edit and test (T2), 2 reps each (file and unittest ok in 16 of 16 runs: 2/2 for every harness)
| # | Harness | Reply correct | Wall s | Tokens in+out |
|---|---------|---------------|--------|---------------|
| 1 | pi | 2/2 | 46.0 | 17,856 |
| 2 | goose | 2/2 | 55.4 | 82,868 |
| 3 | codex-exec (baseline) | 2/2 | 93.0 | 271,893 |
| 4 | openhands | 1/2 | 61.0 | 128,453 |
| 5 | opencode | 1/2 | 100.1 | 26,053 |
| 6 | deerflow | 0/2 | 50.9 | 104,266 |
| 7 | kilo | 0/2 | 57.8 | 15,624 |
| 8 | oh-my-pi | 0/2 | 59.0 | 33,128 |

Note: the 0/2 and 1/2 rows did the work correctly (file and tests ok); they lost on the reply value (141 instead of 77). That is a reply-format/instruction-following miss, not a wrong edit.

## 2. Harnesses that failed to run
- None failed outright; every harness produced exit 0 runs except goose T1 rep 1 (exit 1, Responses stream-decode error, no usage reported).
- pi first attempt hung 900 s (stdin inherited); fixed with stdin=/dev/null, not counted. pi needed reasoning:true plus thinkingLevelMap in its agent-dir models.json, else max effort was clamped.
- codex-exec: benign ai-memory MCP AuthRequired stderr; no effect on jobs.
- Token counts are not like-for-like (codex-exec in includes cached input; others report uncached separately), so token ranks are indicative only.

## 3. Routing proposal for the GPT lane
A harness replaces codex-exec only where it is at least as correct and faster or cheaper.
- Code reading: pi (2/2, 4.4 s vs 59 s, 2.2k vs 31k tokens) beats the baseline. oh-my-pi, deerflow, openhands also tie on correctness and are faster, but pi dominates them; keep them as untested alternates.
- Edit and test: pi (2/2, 46 s vs 93 s, 17.9k vs 272k) beats the baseline. goose ties on correctness and is faster (55 s) but its T1 stream-decode failure disqualifies it for now.
- Keep codex-exec (codex_call.sh) for: sandbox-governed read-only jobs, output-schema strictness, anything needing its MCP/skills layers (pi ran with --no-extensions --no-mcp --no-skills --no-context-files), and as the fallback.
- No harness other than pi qualifies. Pi's trade: it ran without MCP, skills, and context files, so it lacks the full harness layers the repo's policy requires for a default; adopt it first as a measured fast path for bounded read and edit jobs, pending a layer screen (MCP, skills, telemetry, isolation, receipts) at its pin (v1.3.0).

## 4. Limits of this measurement
- n=2 per task per harness, two tasks (one line-count read, one single-line edit with tests); no confidence interval is meaningful.
- One model (cx/gpt-6.1-sol) at one effort; harness effects are confounded with prompt/tool-schema differences and cache state (codex-exec T1 rep 1 103 s vs rep 2 15 s is cold-cache).
- Strict reply scoring penalises reply-value misses that left correct state.
- Pi's config was adjusted (thinking map) and its run omitted MCP/skills/context; codex-exec T2 was run directly rather than through codex_call.sh (recorded departure).
- Token totals mix cache accounting; wall times are single-machine with a memory gate and varying load.
- Untested: multi-file edits, long tasks, tool-heavy tasks, failure recovery, concurrency, sandbox behaviour.
