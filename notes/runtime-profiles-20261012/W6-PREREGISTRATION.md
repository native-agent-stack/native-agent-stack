# w6-parallel-runtime-readers-20261012

Status: preregistered design, **not executed**. Profiles remain trial. The CC
must see this registration and the sealed input/oracle packet before execution.
The worker wiring smokes are acceptance checks, not comparative observations.

The source and truth ledger is [REPLAY-SOURCES.md](REPLAY-SOURCES.md). It resolves
twelve full defective-head commits: W1 #974/#978/#970/#989/#982/#992, then
#991 B3/B4, #995 digest P1, #1002 B4, #1012 two P1s, #1024 inverted-symlink P1
and #1023 B1/B2. Preserve the exact heads in that ledger. B2 of #1023 is the
adjudicated false-at-head blocker control, not an invented P1/P2. The W1 #989
history case requires a commit graph; a tree archive alone is insufficient.

Before any run, seal a packet of named defective heads, independently labeled
safe changes, common task briefs, required source scopes and oracle labels.
No complete preexisting immutable W1 packet was located. Three retained reviewer
probe payloads remain unlocated; their absence must be resolved or declared
before execution. Source truth exists independently of those scripts. Keep
oracle material outside reader-visible input. Do not publish private input
digests or commit private evidence to the repository.

Arms, fixed before execution:

| Arm | Reader configuration |
| --- | --- |
| A | Current Claude and GPT panel |
| B | Identical panel plus Pi on Claude |
| C | Identical panel plus OpenCode on GPT |
| D | Claude via Pi versus Claude via the Agent SDK, same Console slot and model |

Use the same frozen heads and briefs, the same source access, tool budget and
model settings across matching cells. Freeze and record native model IDs,
effort, slot, runtime version and pin, role configuration and listing size
before dispatch. Order the paired cells by a retained random schedule; do not
tune a prompt after observing an arm's findings. Keep all failed/time-limited
attempts and their cost in the denominator. Do not combine provider families
as if they were independent when they share the same model.

CC clarification (ruling-w6-parallel-runtime-readers-prereg-20261012): B/C
measure harness diversity within those two families, without a third family.
Safe-change controls are landed PRs both families passed and never reopened,
for example #950/#969/#1028/#1029/#1020, labeled before execution by a reader
outside this comparison. The co-op assigns that reader. For the three missing
probe payloads, perform one bounded search; if absent, declare "payload absent"
and score using the adjudication's source truth. Never rebuild a probe after
seeing an arm's output. Execution requires the CC to see the sealed packet
manifest (names and hashes only); approval of this design is not execution GO.

The admission rule is unchanged: a runtime joins only if it blocks at least one
known P1/P2 that **both** families missed, with false blockers no higher than
the panel and at measured cost. A harness swap needs equal recall at lower
cost. Otherwise record a bounded non-result. Report per-case known-finding
recall, false blockers on safe changes, failed attempts, latency, tokens and
native usage-priced cost. Distinguish GPT API-price equivalent from invoices.
Source-review eligibility and successful worker inference do not satisfy this
admission rule.

Step-1 baseline: Console $0.000960; GPT API equivalent $0.002052; combined
$0.003012. Subsequent profile smoke costs are reported separately and the
cumulative total must be delivered to the CC before comparative execution.
No third-family arm is enabled. Crush, goose and Hermes are follow-on clients
only after the initial two pass and the CC routes that work.

The Stage A source screen has 35 rows and 11 documented passers; Stage B worker
selection uses a frozen worker corpus under Harbor or the paired-run harness,
registered separately before it runs. No source-screen passer is final.
