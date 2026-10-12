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

## Frozen ledger migration gate

Six corrected receipts are `usage_ref` inputs of the append-only saturation
ledger. Native registration binds their new safe bytes, but
`scripts/saturation_ledger.py` `Validator.check_sweep` still requires their old
`usage_sha256` values. The check therefore refuses six mismatches and two
dependent lost-worker checks. Re-chaining history alone would violate the
independent unchanged-prefix check and its regression.

The ledger is preserved. No integrity check is disabled, no historical counter
or adjudication is rewritten, and no raw private seal is retained to make the
check pass. This draft needs the CC's narrow privacy migration ruling before it
can be accepted: a natively verified privacy-only binding migration with full
semantic-equivalence evidence, or a supported immutable-source binding that
preserves the append-only provenance and validates the safe successor.

`python3 scripts/validate.py` and the refreshed evidence manifest pass. The
native saturation-ledger check is explicitly failing until that migration is
ruled and implemented; the draft is not ready to land. #995 must land first
because the explicit supersession writer does not exist at the main snapshot.

## Follow-ups

- Extend the rule-4 published-digest sweep to JSON receipts as well as Markdown,
  through the owning publication-audit lane.
- Keep raw-output, contract and journal authentication in private host evidence
  until a safe publication representation binds only published preimages.
- Qualify the native scanner timeout/resource flake through the co-op's row 44;
  preserve its fail-closed behavior.
