# Worker SDK release replay — 2026-10-12

The two release clauses in the [retained practice record](2026-10-11-research-convergence-practice.md)
fired: OpenHands SDK/tools 1.53.0 → 1.54.0 and the Python Codex SDK 0.160.0 → 0.162.1.
This change records one qualification per worker and re-pins the existing Codex worker/fixture
script locks. The OpenHands result qualifies a separate isolated 1.54.0 environment with the
unchanged installed dispatcher; selected host environments and persistent units remain untouched.
Publication accepts these bounded replay pins, not a new architecture winner or a live deployment.

The existing predicate is conjunctive: the worker's task oracle passes, model requests are positive,
execution reaches terminal completion, and the foreign scratch sentinel stays unchanged.
Both pass on the actual native candidate runtimes. The [OpenHands record](../../evidence/artifacts/worker-sdk-replay-20261012/openhands-1.54.0.json)
and [Codex record](../../evidence/artifacts/worker-sdk-replay-20261012/codex-0.162.1.json)
retain command identities, exact predicates, counting units, source pins and private capture hashes.

| Worker | Own job oracle | Model requests | Terminal result | Foreign sentinel |
| --- | --- | --- | --- | --- |
| OpenHands SDK/tools 1.54.0 | Compute sum(range(1,11)) and write `55\n` to result.txt; exact bytes match | 3 native combined response-latency entries | finished, success true, idle-scope command rc 0 | seeded bytes equal afterward; metadata predates both jobs |
| Codex Python SDK/native bundle 0.162.1 | Execute `ls examples/omniroute-codex-sdk \| wc -l` and return the actual count; shell rc 0, output/final answer 12 | 2 dedicated reverse-observer request events, two HTTP 200 completed responses | completed turn, idle thread, closed SDK, command rc 0 | same unchanged sibling sentinel |

The Codex task preserves the earlier shell/count contract. The old result 13 came from a different
workspace inventory; it is not a constant expected answer for the new 12-file workspace. The
OpenHands file oracle preserves the dispatcher's arithmetic task. No worker may write the foreign
sibling; the fixture's seeded content and unchanged metadata verify the tested boundary. This is
an observed sentinel invariant, not a claim that all possible foreign writes are prevented.

## Source and installation

The [OpenHands v1.54.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.54.0)
is published at `1d471742ea7be017d013eaaa3080f5d28d5490cb`. Its release-note-required change
is checksum-pinned remote backend artifacts (#5503), and its other notes include typed SDK APIs
and terminal heredoc preservation. The bounded arithmetic replay does not qualify those remote
backend or release-wide behaviors. The supported package install uses `uv venv --python 3.13`
and `uv pip install --python <isolated-runtime>/bin/python openhands-sdk==1.54.0 openhands-tools==1.54.0`.
Installed metadata verifies both at 1.54.0 and the full resolved package inventory is retained.
The isolated environment is also audited against a hash-locked native `uv pip compile` result;
`uv pip install --dry-run --require-hashes` returns 0 with no environment changes required.
Primary source: `OpenHands/software-agent-sdk@1d471742`,
`examples/01_standalone_sdk/01_hello_world.py:9–29` (send/run lifecycle),
`openhands-sdk/openhands/sdk/llm/utils/metrics.py:125–127,171–176` (response latency accounting).

The [Codex rust-v0.162.1 release](https://github.com/openai/codex/releases/tag/rust-v0.162.1)
is `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`. Its release notes fix multiline asynchronous
TUI questions and background-server feature compatibility; neither is a new wrapper feature.
Published `openai-codex==0.162.1` requires `openai-codex-cli-bin==0.162.1`, so the SDK and
bundled native runtime move together through the existing supported PEP 723 `uv lock --script`
and `uv run --locked --script` path. This does not update the independently installed CLI.
Primary source: the pinned central `openai/codex` mirror,
`sdk/python/README.md:6–29`, `sdk/python/src/openai_codex/_run.py:103–135` (completed turn collection)
and `sdk/python/src/openai_codex/async_client.py:93–103` (native start/close).
Source reads use `GIT_NO_LAZY_FETCH=1 GIT_OPTIONAL_LOCKS=0`. The OpenHands mirror still carries
the previous 1.53.0 pin, so its new exact release source was fetched into an owned `/var/tmp`
checkout and the mirror owner was notified of the new pin. No shared mirror was silently changed.

The optional request counter reuses the existing
[mitmproxy observer](../../tools/runtime-worker-evidence/README.md), pin 12.2.3. It observes only
the owned worker through a private loopback port forwarding to 21128; it stores no payload text
or credential values. Two flow-error notices follow completed response events; both native turn
and shell oracle still complete. This receipt makes no general zero-transport-error claim.
The observer is stopped with SIGINT after measurement. Its exit 130 is intentional teardown.

## Retained failures and qualification limits

The first Codex attempt used an absent guessed uv executable and returned 127 before any inference.
The second direct 21128 attempt passed, but lacked an exact request counter; a separately observed
attempt fills that measurement gap. All three command records remain distinct. OpenHands denied
outbound LiteLLM cost-map fetches and fell back to its local backup; those are not model requests.

The existing Codex worker module passes 31 authored native-runtime/loopback integration tests
at the new package pin, with no failures/errors. These tests are distinct from live model tasks.
After the measured run, publication only updates the worker's module source explanation and
the `--codex-bin` help text. The measured source hash stays retained separately; the source AST
is identical after removing that module docstring and argparse help keywords. The record names
both hashes rather than falsely assigning the private run to later documentation bytes.
Only dependency pins, the runtime-version guard and current documentation change; no new custom
agent loop, vendor-feature implementation or behavior fix is introduced, so no new fail-before
bug is claimed. Existing negative controls still exercise version rejection, terminal failure,
deadline cleanup and incomplete streams. Earlier receipts remain byte-identical and historical.
The pin transition has an isolated failing-before check: the existing native lifecycle/resume
oracle fails one test before any inference when the new bundle meets the retained 0.160.0
guard, and passes the same test with the guard updated to 0.162.1. This is compatibility evidence
for the authored pin change, not a claim that the old supported 0.160.0 bundle was broken.

The runs used private homes, separate workspaces and idle-class transient scopes, with all scratch
under `/var/tmp`. The OpenHands process uses the existing per-job srt policy and unchanged worker,
but is not a replay of the existing selected user service's executable. No persistent unit/property,
selected account, protected client configuration or credential was changed or read by this task.

## Follow-ups and reopen condition

- Publish the new OpenHands mirror pin and any selected host deployment through their owners after review; this receipt does not claim installation into the selected host worker environment.
- Worker skill/port documentation drift remains the separately routed #1011 F13 follow-up; historical 20128/1.50.1 records are not rewritten.
- Codex workspace-write and native Claude caller acceptance remain separately gated; read-only shell completion does not close them.

Reopen these bounded qualifications on a new SDK release or a reproduced failure of the conjunctive
job predicate. Candidate-changing comparisons remain in the research convergence queue; this replay
does not adjudicate unresolved Copilot SDK/agentproto survivors or declare either layer FINAL.
The consumed layer inputs are the existing foundation workers/agent-sdks verdicts, the 2026-09-22
verdict-wave index and the latest retained 2026-09-29 sweep/returns. The two releases alone are the
delta assigned by the CC; no broader survey or comparison was dispatched.
