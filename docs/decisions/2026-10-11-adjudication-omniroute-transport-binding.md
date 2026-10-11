# Bind adjudication transport to retained Codex events

Date: 2026-10-11. Correction parent: `cb68e66f3e2e47b1f6ffd6e28898cbcbdb554002`.

The first GPT read reproduced a disclosure downgrade: deleting `provider`, `provider_base_url`
and `pass_through` from saved OmniRoute judgments made assembly count them as native, and native
resume reused them. Checking only the removable fields cannot establish the expected transport.
The exact unchanged parent reproduces both assertion failures in the supplied two-test reproducer.

For OmniRoute only, the runner now writes one `native_agent_stack.transport` JSONL frame before
appending any child stdout. Its schema version is 1; its transport contains the runner-selected
provider, the validated canonical keyless loopback endpoint and the exact existing not-attested
disclosure. The existing per-stage event SHA256 covers the frame and all retained attempt output.
This is private runner metadata, not an upstream Codex event or a claim that the gateway preserved
the prompt or supplied a particular model family.

The loader verifies the existing event digest before deriving transport from those same bytes.
It rejects duplicate/malformed frames, noncanonical endpoints and disagreement between judge and
refuter stages. A bound OmniRoute judgment must contain all three exact disclosure fields. Thus
deleting the fields leaves its independent OmniRoute identity and refuses the vote. Assembly still
copies the accepted provider and disclosure outside common family provenance. Resume compares the
bound saved transport to the requested transport, so a native run reruns both judge/refuter pairs.
Fresh per-call audit and the end summary apply the same binding check against runner configuration.

Native event files keep their empty prefix and unchanged stdout bytes. Native judgment fields and
assembly serialization remain unchanged; native streams require no new marker. Common family
provenance keeps its existing fields and registers the current code digest for both families.
Legacy OmniRoute records declaring transport but lacking a binding are stale and rerun. An older
record that already lost every transport field and has no retained independent binding cannot be
retrospectively identified from that file alone; the changed code provenance invalidates its resume.
This correction relies on the existing retained-event hash trust boundary, not a new signature over
arbitrary replacements of both trusted events and their judgment digest.

## Evidence

The unchanged `cb68e66f` source, compiled in memory, fails 11 assertions across the final eight
focused tests with zero API errors. These cover complete field deletion separately in both orders,
deletion from both unanimous Codex votes, native transport change, legacy unframed OmniRoute resume,
frame integrity/stage agreement and native compatibility. The final corrected source passes all
eight tests. The unmodified supplied reproducer separately fails both tests on the parent and
passes both after correction. Payloads use local fixtures and controlled imports; no live provider
or model call is made.

The native resume control makes four new calls after the transport change, then none on an
unchanged native resume. Native raw event bytes and serialized artifact controls pass. A first
intermediate GREEN run exposed an uninitialized `run_transport` in `judge_pending`; its error logs
are preserved separately and the corrected focused/reproducer results supersede it.

Structured source identities, RED/GREEN log digests and boundaries are recorded in
`tools/sota-convergence/evidence/adjudicate-omniroute-transport-binding-20261011.json`. Required-module
and FULL validation results are retained separately by exact final commit in the lane artifacts and
PR body, so those post-commit checks do not mutate their tested HEAD. No rebase is part of this fix.

## SOTA sources

- [Native Agent Stack at `cb68e66f`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/cb68e66f3e2e47b1f6ffd6e28898cbcbdb554002/tools/sota-convergence/adjudicate.py):
  `usable_judgment:708-720,743-746`, `codex_events_issue:759-779`, `run_codex_call:824-842`,
  resume `:930-934`, retained event hashes `:1079-1081` and assembly `:1581-1584`. Reuse the
  existing hash-bound event mechanism rather than add an unanchored sidecar or another judgment field.
- [openai/codex rust-v0.162.1, `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/exec/src/exec_events.rs):
  `ThreadEvent`, `ThreadStartedEvent` and `TurnCompletedEvent` define the typed exec stream; they
  do not supply the parent runner's selected transport binding. The installed client stays unchanged.
- [CPython v3.13.16, `cbc944f4bc59639a444dd971c737788ba2283a91`](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/json.rst):
  standard `json.dumps`/`json.loads` encode and decode the single runner-owned frame; `hashlib.sha256`
  authenticates the retained bytes through the existing recorded digest. No parser or provider SDK is forked.
- The existing [OmniRoute transport decision](2026-10-10-codex-lane-omniroute.md) supplies endpoint
  validation and the exact disclosure, including the pinned OmniRoute mutation limits. Gateway body
  preservation and upstream family identity remain unmeasured; the not-attested text is unchanged.

A maintained upstream interface that binds runner-selected transport independently of mutable
judgment fields would replace this small retention step once it provides the same refusal and
native compatibility behavior.
