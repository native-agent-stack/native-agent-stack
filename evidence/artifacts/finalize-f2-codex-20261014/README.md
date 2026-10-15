# FINALIZE-ALL F2: Codex invocation evidence

Public export of the completed private staging packet. Original staging is retained privately by name; local paths are normalized, recorder roots are portable, and every affected digest binds the public bytes. Measured counts, windows, IDs, versions and dispositions are unchanged. Measured window: 2026-10-13T23:58:06Z inclusive to 2026-10-14T23:58:06Z exclusive. End time is the tool clock recorded at task intake; the interval is exactly 24 hours. The current F2 measurement work falls after that cutoff and is excluded.

Frozen winner inventory and condition-4 reference: native-agent-stack/native-agent-stack commit 252babe4040e39173cc178317c67699371806df6, catalogs/landscape/final-stack.json and scripts/final_stack.py:706-721,818-829. Receipt shape follows tests/test_final_stack.py:1074-1077 and the Claude-side recorder.

The repository's existing counter is run once for the common window. Session stores and the hcom database are read only. Prompts, command arguments, credentials, account names and raw transcripts are not copied into the packet. Counts and non-sensitive identity metadata are retained. No .key files, stage.env, OmniRoute data or Codex configuration file is read.

Completed native counter command (rc 0; its compact stdout is retained in counter-summary.json):

```sh
python3 ~/code/native-agent-stack-ns2604-skills-trials/tools/invocation-monitoring/codex_counter.py --since 2026-10-13T23:58:06Z --until 2026-10-14T23:58:06Z --sessions ~/.codex/sessions --state ~/.local/state/native-agent-stack --hcom-db ~/.hcom/hcom.db
```

Counter source SHA256: 06b569826c76c2dc9455fccd3e004329e71f791483b42b33571fad21910dc8e3. Its completed MCP call counters are measurements of invocation, including failed attempts; its prompt-filtered counts are provisional and are not used as organic-use evidence. Static skill-read sites are not executed skill loads. The CLI supplement will state its narrower executable-attribution rules separately.

Version-only identities are completed through nuvu's local F1 source-pin table, with pending registration stated explicitly. Host/run version drift is kept separate from matching evidence. A pending receipt does not pass the frozen run identity merely because the host has that version installed.

Current primary host observations already show Codex 0.162.1 versus frozen 0.160.0, gh 2.102.0 versus frozen 2.101.0, and uv 0.12.22 versus frozen 0.12.17. No drifted call will be represented as an invocation at the older pin.

Final packet: CODEX-WINNERS.md and winner-decisions.json cover all 57 frozen winner IDs, including explicit reasons for roles owned by other consumers. Eight invocation receipts and 49 non-invocation/identity/attribution reasons are staged. SocratiCode and foundation-socraticode name the same observation; never sum their counts. Four receipts bind the frozen complete pin (Serena, Gitleaks, worktrunk, zizmor). RTK, restic and both SocratiCode alias receipts bind only the prospective completed F1 pins. None is registered as FINAL evidence by this packet.

Completed measurement:

- Native counter: 3948 rollouts / 25 session homes, raw 6273 completed commands and 8573 MCP items. The counter's provisional prompt-filtered totals are retained for transparency and are never claimed organic.
- Final attribution adapter: 3963 metadata-bearing rollouts / 214 native window threads, including 195 not in the current post-restart registry. No cwd-based lane inference. Its native MCP counts match the native counter for Serena (130) and SocratiCode (64).
- Successful parent CLI lower bounds: RTK 1158, Gitleaks 78, worktrunk 5, restic 2, zizmor 1. gh 116, uv 2 and systemd 439 are observed but do not bind their frozen run versions. Nested subprocesses, hook children, multiline commands and unsuccessful parent commands are not credited by the adapter. No zero from this partial CLI view proves non-use.
- Initial native session metadata labels 14846 completed MCP/command attempts as Codex 0.162.1. That header is not a per-call client-version attestation after resume; no old 0.160.0 or separate SDK invocation receipt is inferred.
- The enabled QMD, ai-memory, headroom and promptfoo MCP endpoints have zero completed calls in this native window. Reasons identify the missing Codex dispatcher invocation, with the CC's slot-consumer condition. Hook/service activity is separately unmeasured. Client configuration and role retirement require their owning CC action; no host wiring was changed here.

Host drift: host-versions.json and each winner artifact retain the installed version against the frozen pin. The already authorized nuvu table completes ai-memory 2.6.3 (frozen 2.4.1), promptfoo 0.124.0 (frozen 0.123.1) and SocratiCode 1.16.0 (frozen 1.15.0). ai-memory and promptfoo have no invoke receipt because they have zero endpoint calls. Other drift found: syft 1.54.1 versus 1.54.0, dagu 2.18.2 versus 2.16.6 and systemd 259.5-0ubuntu3.4 versus 255.4-1ubuntu8.17, plus the Codex/gh/uv drift above. These are gaps, not authorized upgrades. Table provenance and its SHA256 are in input-provenance.json; later table changes need a new binding check.

Supported source checks and adapter commands:

```sh
git show 252babe4040e39173cc178317c67699371806df6:catalogs/landscape/final-stack.json
git show 252babe4040e39173cc178317c67699371806df6:scripts/final_stack.py
git show 252babe4040e39173cc178317c67699371806df6:tests/test_final_stack.py
codex --version
codex mcp list --json
python3 measure_cli.py
python3 build_packet.py
python3 check_receipts.py
```

The MCP listing was processed in memory into server names/enabled flags and the relevant executable/package identity, without retaining its raw arguments or environment. Individual version probes used --version, with the supported restic version and dagu version corrections after their --version refusal. Worktrunk's installed identity is verified by mise ls worktrunk --json and the versioned resolved executable directory; its compressed --version output contained no parseable version. No install or workload was launched by these probes.

build_packet.py prints an artifact map; native file edits materialize it. check_receipts.py executes the pinned FINAL parse_pin and complete_final_pin functions and their grammar verbatim from Git, with the pinned timestamp and repository normalizers. Eight receipt predicate checks pass, all 49 reason strings are nonblank, all 57 winners are covered, and 16 missing/wrong commit negative controls reject as expected. This is receipt-predicate validation, not a whole-stack FINAL verdict. Twelve synthetic executable-prefix controls pass and are marked synthetic, never native invocation evidence. Thirteen public upstream tag checks independently match the table/existing complete pins; exact argv, public refs and peeled commits are retained in upstream-tag-verification.json. Serena uses its installed uv-receipt exact Git revision, recorded in its pin binding.

Execution boundaries and supersession:

- The first native-counter attempt through context-mode exceeded the MCP transport's 300-second limit; it delivered no completed report and is not evidence. Its process ended before the supported long-running exec rerun. The rerun completed rc 0 and is the count of record here.
- cli-counts.json is the completed preliminary registered-root lower bound, preserved as historical. Its implementation was superseded by measure_cli.py's final successful-parent/snapshot/prefix rules. Several expanded adapter attempts timed out or were stopped by this lane before the final completed run; none is counted. native-cli-counts.json is the final attribution input.
- The completed native and adapter scans enumerated stores at different times, hence the file counts differ; all selected events use the same fixed 24-hour cutoff. Live appenders cannot extend the final adapter's per-file size snapshot. The collector's historical-owner mapping is limited to retained native parent edges and the current hcom registry; the existing native dedup policy is reused. These counts are completed-item observations, not guaranteed unique underlying operations across every unregistered replay/fork.
- No fresh vendor trial, model/broker call, unit action, GO/STOP/account-state action, held-head movement, commit or registration occurred. Existing #1090 and #1037 holds stand. The co-op registers this staged packet only after the pin-completion PR.

SHA256SUMS covers the staged source, inputs, receipts, reasons and validation artifacts. It excludes itself and Python bytecode caches. The lane's R F2-DONE block binds the SHA256SUMS bytes.

Publication check: installed Gitleaks scanned the staged packet with redaction enabled, rc 0 / zero findings, without scanner configuration, baseline or allowlist changes. publication-scan.json binds the empty native report. The co-op still performs native evidence registration and repository validation when it adopts this packet after F1; no commit or PR was created by this lane for F2.

Publication export: pin-resolution-projection.json retains public source-pin facts only. The source resolver path and digest are omitted. Current publication disposition is in PUBLICATION.md; its OPEN wiring follow-ups supersede the staging wording without claiming a fix or retirement. Historical command lines below are normalized for publication.
