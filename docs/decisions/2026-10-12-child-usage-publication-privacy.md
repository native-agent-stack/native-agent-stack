# Child-usage publication privacy correction

The CC's #161 ruling requires private raw-output authentication to remain in
host state. Twelve published child-usage receipts at main
`421bf3f98b631d931838c22a927b4fec246f7df8` contain such a digest. This correction
replaces only their `measurement.raw_output_sha256` values with
`private, not published (host state)`. Measurements, attempts, counters, effort
observations, source tool identities and native history are preserved.

The receipt-set regression fails on the published base receipts and passes on
the corrected set. It does not need a real account, home path or raw transcript,
and it prints no private preimage or original digest.

The supersession writer also used each caller-supplied pair verbatim after
validating its five required fields. An extra field containing a runtime-built
synthetic example.org address reached the output. The landed #995 writer now
publishes only the label and the two agent IDs in either provenance or its
redacted proof preimage; the two native call keys remain local. This sweep retains
the public-CLI regression against that three-field allowlist and makes no writer
change. The regression fails at the original 43f3008e baseline and passes after
the #995 correction. Native proof, contract, journal chronology,
same-label terminal, effort and counter checks remain enforced.

This directly extends the selected native implementation from #995. Sources:

- [#995 writer at 43f3008e](https://github.com/seathatflowsinourveins/native-agent-stack/blob/43f3008e1c6bfe5b8a44ddf10d6c400f823e1cdb/tools/sota-convergence/landscape-sweep/usage_record.py):
  `proven_supersessions`, required pair fields and retained proof projection.
- [Landed #995 writer at 429f0421](https://github.com/seathatflowsinourveins/native-agent-stack/blob/429f0421b8f496257dde3d3792b937820ad2b789/tools/sota-convergence/landscape-sweep/usage_record.py):
  `proven_supersessions` and `public_processing` keep native keys local and
  allowlist the published three-field pair projection.
- [Native JSON writer at 43f3008e](https://github.com/seathatflowsinourveins/native-agent-stack/blob/43f3008e1c6bfe5b8a44ddf10d6c400f823e1cdb/tools/sota-convergence/landscape-sweep/sweep_common.py):
  `json_text` determines the exact published proof bytes and digest.
- [Published-digest precedent at 421bf3f9](https://github.com/seathatflowsinourveins/native-agent-stack/blob/421bf3f98b631d931838c22a927b4fec246f7df8/tests/test_published_digest_privacy.py):
  published-byte authentication is distinct from authentication of a private
  original, including when the private input's literal identity is absent.

## Append-only redaction-supersession binding

Six corrected receipts are `usage_ref` inputs of the append-only saturation
ledger. Before this extension, `scripts/saturation_ledger.py` `Checker.check_sweep`
required their original `usage_sha256` to match current bytes and refused six
mismatches and two dependent lost-worker checks. Re-chaining history would
violate the independent unchanged-prefix check and its regression.

The CC ruled option (b): append a native `redaction-supersession` record for each
of the six inputs. Each binds the original public Git blob at commit
`421bf3f98b631d931838c22a927b4fec246f7df8`, whose digest must equal the stored usage
digest, to the current redacted successor's digest. Reason `#161` and the native
chain link are explicit. Original sweeps, votes, policy and counters are unchanged.

The checker verifies every historical blob and the newest registered successor.
Receipt JSON may differ only by the ruled raw-authentication marker. Tampering
fails even if its registration is refreshed; changing a counter fails even with
a newly declared successor digest. Missing Git objects fail closed. The native
appender accepts a single binding or atomic batch and checks the full proposed
chain; it cannot repair an unrelated broken history or registration.

`--check --base` and the existing re-chained-history regression are unchanged.
The redacted-state regression fails on the old checker and passes after this
extension. Controls cover tampering, missing history, successive bindings and
counter changes. Bindings are inert to saturation derivation. The old raw field
remains in immutable published history, as the CC's ruling notes; no new private
authentication is published. #995 still lands first because it supplies the writer.

## Follow-ups

- Extend the rule-4 published-digest sweep to JSON receipts as well as Markdown,
  through the owning publication-audit lane.
- Keep raw-output, contract and journal authentication in private host evidence
  until a safe publication representation binds only published preimages.
- Qualify the native scanner timeout/resource flake through the co-op's row 44;
  preserve its fail-closed behavior.
